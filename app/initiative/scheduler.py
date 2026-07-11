"""Background scheduler that periodically evaluates initiative candidates.

Runs periodic jobs for:
  - General tick every 15 minutes: daily_greeting, return_after_absence,
    late_night_checkin, prolonged_silence.
  - Memory tick every 4 hours: memory_followup.
  - Context commentary queue every 5 minutes.
  - Avatar ambient life state every minute.
  - Nightly memory consolidation.

Each tick builds candidates through InitiativeService and passes them through
the central gate (can_emit / emit). The gate handles all suppression logic -
quiet hours, DND, daily limits, spacing, mic state, expiry. The scheduler
does not duplicate those checks.

Guard before every tick:
  - Database engine must be ready (ledger needs storage).
  - Both master toggles (enable_proactive_messaging, initiative_enabled) must be on.
  - If either guard fails the tick is skipped silently; the next scheduled run
    will retry.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from app.config import settings

if TYPE_CHECKING:
    from app.avatar.life_state import LifeStateEngine
    from app.api.media_session import MediaSessionStore
    from app.api.realtime import RealtimeEventBus
    from app.initiative.service import InitiativeService
    from app.memory.store import MemoryStore

logger = logging.getLogger(__name__)

_TICK_INTERVAL_MINUTES = 15
_MEMORY_TICK_INTERVAL_HOURS = 4
_CONTEXT_TICK_INTERVAL_MINUTES = 5
_LIFE_STATE_TICK_INTERVAL_MINUTES = 1
_CALENDAR_TICK_INTERVAL_MINUTES = 10
_BOOT_DELAY_SECONDS = 30
_DEFAULT_SESSION = "default"


class InitiativeScheduler:
    """
    Drives periodic evaluation of all initiative candidate types.

    start() / stop() are called from the FastAPI lifespan alongside MqttBridge.
    All failures inside tick functions are caught and logged - they must never
    propagate to the scheduler and kill future ticks.
    """

    def __init__(
        self,
        service: "InitiativeService",
        event_bus: "RealtimeEventBus",
        memory_store: "MemoryStore",
        media_sessions: "MediaSessionStore",
        context_events: Any | None = None,
        life_state_engine: "LifeStateEngine | None" = None,
    ) -> None:
        self._service = service
        self._event_bus = event_bus
        self._memory_store = memory_store
        self._media_sessions = media_sessions
        self._context_events = context_events
        self._life_state_engine = life_state_engine
        self._scheduler: Any = None  # APScheduler AsyncIOScheduler, imported lazily

    # ------------------------------------------------------------------
    # Lifecycle

    async def start(self) -> None:
        """Start the scheduler; individual ticks no-op while initiatives are disabled."""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        first_run = datetime.now(tz=timezone.utc) + timedelta(seconds=_BOOT_DELAY_SECONDS)

        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_job(
            self._general_tick,
            trigger="interval",
            minutes=_TICK_INTERVAL_MINUTES,
            next_run_time=first_run,
            id="initiative_general_tick",
            name="Initiative general tick",
            coalesce=True,
            max_instances=1,
        )
        self._scheduler.add_job(
            self._context_tick,
            trigger="interval",
            minutes=_CONTEXT_TICK_INTERVAL_MINUTES,
            next_run_time=first_run,
            id="context_commentary_tick",
            name="Context commentary queue tick",
            coalesce=True,
            max_instances=1,
        )
        self._scheduler.add_job(
            self._life_state_tick,
            trigger="interval",
            minutes=_LIFE_STATE_TICK_INTERVAL_MINUTES,
            next_run_time=first_run,
            id="avatar_life_state_tick",
            name="Avatar ambient life-state tick",
            coalesce=True,
            max_instances=1,
        )
        self._scheduler.add_job(
            self._memory_tick,
            trigger="interval",
            hours=_MEMORY_TICK_INTERVAL_HOURS,
            next_run_time=first_run,
            id="initiative_memory_tick",
            name="Initiative memory tick",
            coalesce=True,
            max_instances=1,
        )
        self._scheduler.add_job(
            self._calendar_tick,
            trigger="interval",
            minutes=_CALENDAR_TICK_INTERVAL_MINUTES,
            next_run_time=first_run,
            id="initiative_calendar_tick",
            name="Initiative calendar heads-up tick",
            coalesce=True,
            max_instances=1,
        )
        # Nightly memory consolidation ("sleep"). Independent of the initiative
        # toggles — it's memory maintenance, gated only by its own setting — and
        # runs at a fixed local hour via the scheduler's local timezone.
        self._scheduler.add_job(
            self._consolidation_tick,
            trigger="cron",
            hour=settings.memory_consolidation_hour,
            minute=30,
            id="memory_consolidation_tick",
            name="Memory consolidation (sleep)",
            coalesce=True,
            max_instances=1,
        )
        self._scheduler.start()
        logger.info(
            "Initiative scheduler started - general tick every %dm, memory tick every %dh, "
            "first run in %ds",
            _TICK_INTERVAL_MINUTES,
            _MEMORY_TICK_INTERVAL_HOURS,
            _BOOT_DELAY_SECONDS,
        )

    async def stop(self) -> None:
        """Shut down the scheduler cleanly."""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        logger.info("Initiative scheduler stopped")

    # ------------------------------------------------------------------
    # Diagnostics

    def diagnostics(self) -> dict[str, Any]:
        if self._scheduler is None:
            return {"running": False, "jobs": []}
        jobs = []
        for job in self._scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": next_run.isoformat() if next_run else None,
            })
        return {
            "running": self._scheduler.running,
            "jobs": jobs,
        }

    # ------------------------------------------------------------------
    # Tick functions

    async def _general_tick(self) -> None:
        """Evaluate greeting, absence, late-night, and silence candidates."""
        if not self._is_ready():
            return
        session_id = _DEFAULT_SESSION
        media = self._media_sessions.get(session_id)

        for candidate in [
            self._service.build_daily_greeting_candidate(session_id=session_id),
            self._service.build_return_after_absence_candidate(session_id=session_id),
            self._service.build_late_night_checkin_candidate(session_id=session_id),
            self._service.build_prolonged_silence_candidate(session_id=session_id),
        ]:
            await self._evaluate(candidate, media=media)

    async def _memory_tick(self) -> None:
        """Evaluate memory follow-up candidate."""
        if not self._is_ready():
            return
        session_id = _DEFAULT_SESSION
        media = self._media_sessions.get(session_id)
        candidate = self._service.build_memory_followup_candidate(
            session_id=session_id,
            memory_store=self._memory_store,
        )
        await self._evaluate(candidate, media=media)

    async def _calendar_tick(self) -> None:
        """Nudge about the soonest upcoming calendar event in the lead window.

        The candidate builder makes a blocking Google Calendar call, so it runs
        off the event loop. It no-ops when the calendar isn't connected or no
        event falls in the window, and the quality + policy gates govern emission
        (per-event repeat suppression means each event is only surfaced once).
        """
        if not self._is_ready():
            return
        session_id = _DEFAULT_SESSION
        try:
            candidate = await asyncio.to_thread(
                self._service.build_calendar_heads_up_candidate,
                session_id=session_id,
                lead_minutes_min=settings.initiative_calendar_lead_min_minutes,
                lead_minutes_max=settings.initiative_calendar_lead_max_minutes,
            )
        except Exception as exc:
            logger.warning("Calendar heads-up tick failed to build candidate: %s", exc)
            return
        if candidate is None:
            return
        media = self._media_sessions.get(session_id)
        await self._evaluate(candidate, media=media)

    async def _consolidation_tick(self) -> None:
        """Nightly memory consolidation. Independent of initiative toggles."""
        if not settings.memory_consolidation_enabled:
            return
        try:
            from app.memory.consolidation import MemoryConsolidator

            consolidator = MemoryConsolidator(self._memory_store)
            result = await asyncio.to_thread(consolidator.consolidate)
            logger.info(
                "Consolidation tick: status=%s consolidated=%s sources=%s",
                result.get("status"),
                result.get("consolidated"),
                result.get("source_count"),
            )
        except Exception as exc:
            logger.warning("Consolidation tick failed: %s", exc)

    async def _context_tick(self) -> None:
        if not self._is_ready() or self._context_events is None:
            return
        for event in self._context_events.store.pending(limit=5):
            event_id = str(event.get("event_id") or "")
            candidate = self._context_events.build_commentary_candidate(
                event_id,
                claim=True,
            )
            if candidate is None:
                continue
            media = self._media_sessions.get(candidate.session_id)
            try:
                decision = await self._service.emit(
                    candidate,
                    event_bus=self._event_bus,
                    memory_store=self._memory_store,
                    media_session=media,
                )
            except Exception as exc:
                logger.warning("Context commentary delivery failed: %s", exc)
                self._context_events.mark_delivery(
                    event_id,
                    emitted=False,
                    reason="delivery failed; queued for retry",
                    retryable=True,
                )
                continue
            if decision.allowed:
                self._context_events.mark_delivery(event_id, emitted=True)
                continue
            reason = str(decision.suppressed_reason or "suppressed")
            self._context_events.mark_delivery(
                event_id,
                emitted=False,
                reason=reason,
                retryable=self._context_events.is_retryable_suppression(reason),
            )

    async def _life_state_tick(self) -> None:
        """Advance ambient avatar state even when no presence event arrives."""
        if self._life_state_engine is None:
            return
        session_id = _DEFAULT_SESSION
        try:
            new_state = self._life_state_engine.evaluate(
                last_activity_at=self._service.store.last_user_activity_at(),
                absence_started_at=self._service.store.absence_started_at(session_id),
            )
            if new_state is not None:
                await self._event_bus.publish(
                    "avatar.life_state_changed",
                    {"life_state": new_state},
                    session_id=session_id,
                    source="life_state",
                )
        except Exception as exc:
            logger.warning("Life-state tick failed: %s", exc)

    # ------------------------------------------------------------------
    # Internal helpers

    async def _evaluate(self, candidate: Any, *, media: Any) -> None:
        """Run one candidate through the central gate. All exceptions are caught."""
        if candidate is None:
            return
        try:
            decision = await self._service.emit(
                candidate,
                event_bus=self._event_bus,
                memory_store=self._memory_store,
                media_session=media,
            )
            if decision.allowed:
                logger.info(
                    "Initiative emitted by scheduler: type=%s reason=%s",
                    candidate.type,
                    candidate.reason,
                )
            else:
                logger.debug(
                    "Initiative suppressed by scheduler: type=%s suppressed_reason=%s",
                    candidate.type,
                    decision.suppressed_reason,
                )
        except Exception as exc:
            logger.warning(
                "Initiative scheduler error evaluating type=%s: %s",
                getattr(candidate, "type", "unknown"),
                exc,
            )

    def _is_ready(self) -> bool:
        """Lightweight guard: initiatives must be enabled.

        The initiative ledger is a JSON file (InitiativeStore), so ticks must not
        be gated on the optional async Postgres engine — that engine is None in
        the default SQLite setup and previously disabled all proactive behavior.
        """
        if not (settings.enable_proactive_messaging and settings.initiative_enabled):
            logger.debug("Initiative tick skipped: initiatives disabled")
            return False
        return True


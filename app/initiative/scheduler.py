"""Background scheduler that periodically evaluates initiative candidates.

Runs two jobs:
  - General tick every 15 minutes: daily_greeting, return_after_absence,
    late_night_checkin, prolonged_silence.
  - Memory tick every 4 hours: memory_followup.

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

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from app.config import settings

if TYPE_CHECKING:
    from app.api.media_session import MediaSessionStore
    from app.api.realtime import RealtimeEventBus
    from app.initiative.service import InitiativeService
    from app.memory.store import MemoryStore

logger = logging.getLogger(__name__)

_TICK_INTERVAL_MINUTES = 15
_MEMORY_TICK_INTERVAL_HOURS = 4
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
    ) -> None:
        self._service = service
        self._event_bus = event_bus
        self._memory_store = memory_store
        self._media_sessions = media_sessions
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
            self._memory_tick,
            trigger="interval",
            hours=_MEMORY_TICK_INTERVAL_HOURS,
            next_run_time=first_run,
            id="initiative_memory_tick",
            name="Initiative memory tick",
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
        """Lightweight guard: storage must be up and initiatives must be enabled."""
        from app.db import engine as db_engine

        if db_engine is None:
            logger.debug("Initiative tick skipped: database not ready")
            return False
        if not (settings.enable_proactive_messaging and settings.initiative_enabled):
            logger.debug("Initiative tick skipped: initiatives disabled")
            return False
        return True


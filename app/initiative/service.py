from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.initiative.policy import (
    EVENT_DRIVEN_TYPES,
    LATE_NIGHT_TYPES,
    CandidateEvidence,
    InitiativeCandidate,
    InitiativeDecision,
    InitiativePolicy,
    is_quiet_time,
)
from app.initiative.store import InitiativeStore

logger = logging.getLogger("joi.initiative")


class InitiativeService:
    """Builds and gates unsolicited Joi initiative candidates."""

    return_after_absence_threshold_minutes = 45
    late_night_recent_activity_minutes = 120

    def __init__(
        self,
        store: InitiativeStore | None = None,
        outbox: Any | None = None,
        quality_gate: Any | None = None,
    ) -> None:
        self.store = store or InitiativeStore()
        # Optional remote-delivery queue. When set, emitted initiatives that are
        # eligible are also enqueued for the Telegram bridge to pick up. None in
        # tests and any headless use — delivery is a strict add-on to emission.
        self._outbox = outbox
        # Optional Phase 10 quality gate. Only evidence-bound (context-triggered)
        # candidates are scored; timer-driven candidates bypass it entirely.
        self._quality_gate = quality_gate

    def build_daily_greeting_candidate(
        self,
        *,
        session_id: str = "default",
        policy: InitiativePolicy | None = None,
        now: datetime | None = None,
    ) -> InitiativeCandidate | None:
        active_policy = policy or InitiativePolicy.from_settings()
        current = self._policy_now(active_policy, now)
        if not is_quiet_time(
            current,
            active_policy.daily_greeting_start,
            active_policy.daily_greeting_end,
        ):
            return None
        expires_at = (current + timedelta(hours=3)).isoformat()
        return InitiativeCandidate(
            type="daily_greeting",
            priority="low",
            reason="within daily greeting window",
            session_id=session_id,
            message="Morning. Want to ease into the day or jump straight in?",
            expires_at=expires_at,
        )

    def record_user_activity(
        self,
        *,
        session_id: str,
        source: str = "user_activity",
        clear_absence: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = self._policy_now(InitiativePolicy.from_settings(), now)
        return self.store.record_user_activity(
            session_id=session_id,
            source=source,
            observed_at=current,
            clear_absence=clear_absence,
        )

    def record_absence_started(
        self,
        *,
        session_id: str,
        source: str = "presence",
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = self._policy_now(InitiativePolicy.from_settings(), now)
        return self.store.record_absence_started(
            session_id=session_id,
            source=source,
            observed_at=current,
        )

    def clear_absence(self, *, session_id: str) -> None:
        self.store.clear_absence(session_id=session_id)

    def build_return_after_absence_candidate(
        self,
        *,
        session_id: str = "default",
        now: datetime | None = None,
    ) -> InitiativeCandidate | None:
        current = self._policy_now(InitiativePolicy.from_settings(), now)
        absence_started = self._coerce_to_current_zone(
            self.store.absence_started_at(session_id),
            current,
        )
        if absence_started is None:
            return None
        away_minutes = int((current - absence_started).total_seconds() // 60)
        if away_minutes < self.return_after_absence_threshold_minutes:
            return None
        expires_at = (current + timedelta(minutes=30)).isoformat()
        return InitiativeCandidate(
            type="return_after_absence",
            priority="low",
            reason=f"user returned after {away_minutes} minutes away",
            session_id=session_id,
            message="Welcome back. Want to pick up where we left off?",
            expires_at=expires_at,
        )

    def build_late_night_checkin_candidate(
        self,
        *,
        session_id: str = "default",
        policy: InitiativePolicy | None = None,
        now: datetime | None = None,
    ) -> InitiativeCandidate | None:
        active_policy = policy or InitiativePolicy.from_settings()
        current = self._policy_now(active_policy, now)
        if not is_quiet_time(current, active_policy.late_night_start, active_policy.late_night_end):
            return None
        if self.store.absence_started_at(session_id) is not None:
            return None
        last_activity = self._coerce_to_current_zone(
            self.store.last_user_activity_for_session(session_id),
            current,
        )
        if last_activity is None:
            return None
        active_minutes = int((current - last_activity).total_seconds() // 60)
        if active_minutes > self.late_night_recent_activity_minutes:
            return None
        expires_at = (current + timedelta(minutes=90)).isoformat()
        return InitiativeCandidate(
            type="late_night_checkin",
            priority="low",
            reason=f"within late-night window after activity {active_minutes} minutes ago",
            session_id=session_id,
            message="Still up? Just checking in.",
            expires_at=expires_at,
        )

    def build_prolonged_silence_candidate(
        self,
        *,
        session_id: str = "default",
        policy: InitiativePolicy | None = None,
        now: datetime | None = None,
    ) -> InitiativeCandidate | None:
        active_policy = policy or InitiativePolicy.from_settings()
        current = self._policy_now(active_policy, now)
        last_activity = self._coerce_to_current_zone(
            self.store.last_user_activity_for_session(session_id),
            current,
        )
        if last_activity is None:
            return None
        silent_minutes = int((current - last_activity).total_seconds() // 60)
        if silent_minutes < active_policy.silence_threshold_minutes:
            return None
        expires_at = (current + timedelta(minutes=30)).isoformat()
        return InitiativeCandidate(
            type="prolonged_silence",
            priority="low",
            reason=f"user silent for {silent_minutes} minutes",
            session_id=session_id,
            message="You've been quiet for a while. Everything going okay?",
            expires_at=expires_at,
        )

    def build_memory_followup_candidate(
        self,
        *,
        session_id: str = "default",
        memory_store: Any | None = None,
        context_id: str | None = None,
        now: datetime | None = None,
    ) -> InitiativeCandidate | None:
        if memory_store is None:
            return None
        current = self._policy_now(InitiativePolicy.from_settings(), now)
        today = current.date().isoformat()
        # Skip entirely if a memory follow-up already happened today
        if self.store.emitted_type_today("memory_followup", today):
            return None
        if context_id is None and session_id == "default":
            return None
        try:
            if context_id:
                memories = memory_store.recent(context_id, limit=15)
            elif session_id != "default":
                memories = memory_store.recent(session_id, limit=15)
            else:
                memories = memory_store.get_recent_memories(limit=15)
        except Exception:
            return None
        if not memories:
            return None
        for memory in memories:
            created_at = getattr(memory, "created_at", None)
            if created_at is None:
                continue
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except ValueError:
                    continue
            created_at = self._coerce_to_current_zone(created_at, current)
            if created_at is None:
                continue
            age_hours = (current - created_at).total_seconds() / 3600
            # Skip memories too recent (user remembers) or too old (stale)
            if age_hours < 2 or age_hours > 72:
                continue
            text = str(getattr(memory, "text", "") or "").strip()
            if len(text) < 20:
                continue
            summary = text[:120] + "..." if len(text) > 120 else text
            expires_at = (current + timedelta(hours=2)).isoformat()
            memory_id = str(
                getattr(memory, "id", None)
                or getattr(memory, "memory_id", None)
                or ""
            ) or None
            observed_at = created_at.isoformat() if isinstance(created_at, datetime) else None
            evidence = CandidateEvidence(
                source_type="memory",
                excerpt=text,
                source_id=memory_id,
                observed_at=observed_at,
                topic_key=f"memory_followup:{memory_id}" if memory_id else None,
            )
            return InitiativeCandidate(
                type="memory_followup",
                priority="low",
                reason=f"unresolved memory from {age_hours:.0f}h ago",
                session_id=session_id,
                message=f'Earlier you mentioned: "{summary}" - did that go anywhere?',
                expires_at=expires_at,
                evidence=evidence,
            )
        return None

    def build_calendar_heads_up_candidate(
        self,
        *,
        session_id: str = "default",
        events: list[dict[str, Any]] | None = None,
        now: datetime | None = None,
        lead_minutes_min: int = 15,
        lead_minutes_max: int = 90,
    ) -> InitiativeCandidate | None:
        """Evidence-bound heads-up for the soonest calendar event in the lead window.

        Diagnostics-only for now: `calendar_heads_up` is not in the default
        allowed types, so the policy gate suppresses live emission until enabled.
        `events` may be supplied (tests, callers) or fetched from the read-only
        calendar tool when authenticated.
        """
        current = self._policy_now(InitiativePolicy.from_settings(), now)
        if events is None:
            events = self._fetch_calendar_events()
        if not events:
            return None

        soonest: tuple[float, dict[str, Any], datetime] | None = None
        for event in events:
            start = self._parse_event_start(event, current)
            if start is None:
                continue
            minutes_until = (start - current).total_seconds() / 60
            if not (lead_minutes_min <= minutes_until <= lead_minutes_max):
                continue
            if soonest is None or minutes_until < soonest[0]:
                soonest = (minutes_until, event, start)
        if soonest is None:
            return None

        minutes_until, event, start = soonest
        summary = str(event.get("summary") or "").strip() or "an untitled event"
        event_id = str(event.get("id") or "") or None
        rounded = max(5, int(round(minutes_until / 5.0)) * 5)
        evidence = CandidateEvidence(
            source_type="calendar",
            excerpt=f"{summary} at {start.isoformat()}",
            source_id=event_id,
            observed_at=None,  # a future event isn't "stale" evidence; timing governs
            topic_key=f"calendar_heads_up:{event_id}" if event_id else None,
        )
        return InitiativeCandidate(
            type="calendar_heads_up",
            priority="normal",
            reason=f"calendar event in {int(minutes_until)} minutes",
            session_id=session_id,
            message=f"Heads up — \"{summary}\" is coming up in about {rounded} minutes.",
            expires_at=start.isoformat(),
            evidence=evidence,
        )

    def _fetch_calendar_events(self) -> list[dict[str, Any]]:
        """Read upcoming events from the calendar tool, or [] if unavailable."""
        try:
            from app.tools import calendar_gcal

            if not calendar_gcal.is_authenticated():
                return []
            return calendar_gcal.upcoming_events(days=1)
        except Exception as exc:  # noqa: BLE001 - never let a calendar hiccup raise
            logger.warning("Calendar heads-up fetch failed: %s", exc)
            return []

    def _parse_event_start(
        self, event: dict[str, Any], current: datetime
    ) -> datetime | None:
        """Parse a Google Calendar event's timed start; skip all-day entries."""
        start = event.get("start")
        if not isinstance(start, dict):
            return None
        raw = start.get("dateTime")  # all-day events use "date" (no time) — skip
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            return None
        return self._coerce_to_current_zone(parsed, current)

    def register_user_reply(
        self, session_id: str, *, now: datetime | None = None
    ) -> list[dict[str, Any]]:
        """Resolve pending evidence-bound initiative feedback on a user message.

        Called from the chat path: a reply shortly after an evidence-bound
        initiative marks it engaged; stale unanswered ones age out to ignored.
        No-op when the quality gate isn't configured.
        """
        if self._quality_gate is None:
            return []
        try:
            return self._quality_gate.register_feedback(session_id, now=now)
        except Exception as exc:  # noqa: BLE001 - feedback must never break chat
            logger.warning("Initiative feedback registration failed: %s", exc)
            return []

    def _quality_gate_active(self) -> bool:
        """Whether the quality gate is configured and enabled by settings."""
        if self._quality_gate is None:
            return False
        from app.config import settings

        return bool(getattr(settings, "initiative_quality_gate_enabled", True))

    def _quality_evaluate(self, candidate: InitiativeCandidate, now: datetime) -> Any | None:
        """Score an evidence-bound candidate, or None if the gate doesn't apply.

        Timer-driven candidates (no evidence) and a disabled/absent gate return
        None so the policy gate alone governs — preserving legacy behavior.
        """
        if candidate.evidence is None or not self._quality_gate_active():
            return None
        return self._quality_gate.evaluate(candidate, now=now)

    def _policy_decision(
        self,
        candidate: InitiativeCandidate,
        *,
        active_policy: InitiativePolicy,
        media_session: dict[str, Any] | None,
        current: datetime,
    ) -> InitiativeDecision:
        reason = self._suppression_reason(
            candidate,
            policy=active_policy,
            media_session=media_session or {},
            now=current,
        )
        if reason is not None:
            self.store.record_suppressed(
                initiative_type=candidate.type,
                session_id=candidate.session_id,
                reason=reason,
                checked_at=current,
            )
            return InitiativeDecision(False, candidate, reason)
        return InitiativeDecision(True, candidate)

    def can_emit(
        self,
        candidate: InitiativeCandidate,
        *,
        policy: InitiativePolicy | None = None,
        media_session: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> InitiativeDecision:
        active_policy = policy or InitiativePolicy.from_settings()
        current = self._policy_now(active_policy, now)
        quality = self._quality_evaluate(candidate, current)
        if quality is not None and not quality.passed:
            reason = f"quality gate: {quality.hard_reason or 'suppressed'}"
            self.store.record_suppressed(
                initiative_type=candidate.type,
                session_id=candidate.session_id,
                reason=reason,
                checked_at=current,
            )
            return InitiativeDecision(False, candidate, reason)
        return self._policy_decision(
            candidate,
            active_policy=active_policy,
            media_session=media_session,
            current=current,
        )

    async def emit(
        self,
        candidate: InitiativeCandidate,
        *,
        event_bus: Any,
        memory_store: Any | None = None,
        policy: InitiativePolicy | None = None,
        media_session: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> InitiativeDecision:
        active_policy = policy or InitiativePolicy.from_settings()
        current = self._policy_now(active_policy, now)

        quality = self._quality_evaluate(candidate, current)
        if quality is not None and not quality.passed:
            reason = f"quality gate: {quality.hard_reason or 'suppressed'}"
            self.store.record_suppressed(
                initiative_type=candidate.type,
                session_id=candidate.session_id,
                reason=reason,
                checked_at=current,
            )
            decision = InitiativeDecision(False, candidate, reason)
            await event_bus.publish(
                "initiative.suppressed",
                decision.to_dict(),
                session_id=candidate.session_id,
                source="initiative",
            )
            return decision

        decision = self._policy_decision(
            candidate,
            active_policy=active_policy,
            media_session=media_session,
            current=current,
        )
        if not decision.allowed:
            await event_bus.publish(
                "initiative.suppressed",
                decision.to_dict(),
                session_id=candidate.session_id,
                source="initiative",
            )
            return decision

        record = self.store.record_emitted(
            initiative_type=candidate.type,
            session_id=candidate.session_id,
            message=candidate.message,
            reason=candidate.reason,
            emitted_at=current,
        )
        if memory_store is not None:
            memory_store.add_chat_message(candidate.session_id, "assistant", candidate.message)
        if quality is not None and self._quality_gate is not None:
            # Persist for repeat suppression only after the candidate truly emits.
            self._quality_gate.record_emission(candidate, quality, now=current)

        await event_bus.publish(
            "initiative.emitted",
            {
                **decision.to_dict(),
                "emission": record,
            },
            session_id=candidate.session_id,
            source="initiative",
        )
        self._deliver_remote(candidate, current)
        await self._notify_native(candidate)
        return decision

    def _deliver_remote(self, candidate: InitiativeCandidate, now: datetime) -> None:
        """Enqueue an emitted initiative for remote delivery when eligible.

        A best-effort add-on: remote delivery must never break local emission,
        so any queue failure is swallowed and logged.
        """
        if self._outbox is None:
            return
        try:
            from app.integrations.outbox import initiative_is_deliverable

            if not initiative_is_deliverable(candidate):
                return
            # Evidence-bound types (calendar heads-ups) key on the specific event
            # so two events on the same day each deliver; ambient types keep the
            # once-per-day key so a retry storm can't spam the remote surface.
            if candidate.evidence and candidate.evidence.topic_key:
                dedup_key = f"initiative:{candidate.evidence.topic_key}"
            else:
                dedup_key = f"{candidate.type}:{candidate.session_id}:{now.date().isoformat()}"
            self._outbox.enqueue(
                text=candidate.message,
                kind=f"initiative:{candidate.type}",
                dedup_key=dedup_key,
                expires_at=candidate.expires_at,
            )
        except Exception as exc:  # noqa: BLE001 - delivery is non-critical
            logger.warning("Remote initiative delivery failed: %s", exc)

    @staticmethod
    async def _notify_native(candidate: InitiativeCandidate) -> None:
        import asyncio
        import os

        if os.environ.get("JOI_NATIVE_NOTIFICATIONS") != "1":
            return
        try:
            from desktop.tray_app import send_notification

            await asyncio.to_thread(send_notification, "Joi", candidate.message)
        except Exception:
            return

    def diagnostics(
        self,
        *,
        policy: InitiativePolicy | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        active_policy = policy or InitiativePolicy.from_settings()
        current = self._policy_now(active_policy, now)
        snapshot = self.store.snapshot(current)
        return {
            "enabled": active_policy.enabled,
            "daily_limit": active_policy.daily_limit,
            "daily_count": snapshot["daily_count"],
            "remaining_today": max(0, active_policy.daily_limit - snapshot["daily_count"]),
            "timezone": active_policy.timezone,
            "daily_greeting": {
                "start": active_policy.daily_greeting_start,
                "end": active_policy.daily_greeting_end,
                "active": is_quiet_time(
                    current,
                    active_policy.daily_greeting_start,
                    active_policy.daily_greeting_end,
                ),
            },
            "quiet_hours": {
                "start": active_policy.quiet_hours_start,
                "end": active_policy.quiet_hours_end,
                "active": is_quiet_time(
                    current,
                    active_policy.quiet_hours_start,
                    active_policy.quiet_hours_end,
                ),
            },
            "focus_mode": active_policy.focus_mode,
            "do_not_disturb": active_policy.do_not_disturb,
            "last_emitted_at": snapshot["last_emitted_at"],
            "last_suppressed": snapshot["last_suppressed"],
            "last_user_activity": snapshot["last_user_activity"],
            "absence_started_at": snapshot["absence_started_at"],
            "return_after_absence_threshold_minutes": self.return_after_absence_threshold_minutes,
            "allowed_types": list(active_policy.allowed_types),
            "late_night": {
                "start": active_policy.late_night_start,
                "end": active_policy.late_night_end,
                "active": is_quiet_time(
                    current,
                    active_policy.late_night_start,
                    active_policy.late_night_end,
                ),
            },
            "silence_threshold_minutes": active_policy.silence_threshold_minutes,
            "quality_gate": self._quality_diagnostics(),
            "remote_delivery": self._remote_delivery_diagnostics(),
        }

    def _remote_delivery_diagnostics(self) -> dict[str, Any]:
        """Read-only view of proactive Telegram delivery for the diagnostics surface."""
        from app.config import settings

        enabled = bool(getattr(settings, "telegram_proactive_enabled", False))
        block: dict[str, Any] = {
            "enabled": enabled,
            "types": sorted(settings.telegram_proactive_type_set),
        }
        if self._outbox is not None:
            try:
                block["pending"] = self._outbox.pending_count()
            except Exception as exc:  # noqa: BLE001 - diagnostics must never raise
                block["pending"] = None
                block["error"] = str(exc)
        return block

    def _quality_diagnostics(self) -> dict[str, Any]:
        """Read-only view of the Phase 10 quality gate for the diagnostics surface."""
        from app.config import settings

        enabled = self._quality_gate is not None and bool(
            getattr(settings, "initiative_quality_gate_enabled", True)
        )
        block: dict[str, Any] = {"enabled": enabled}
        if self._quality_gate is not None:
            from app.initiative.quality import DEFAULT_THRESHOLD, SAFETY_FLOOR, WEIGHTS

            block.update(
                {
                    "threshold": DEFAULT_THRESHOLD,
                    "safety_floor": SAFETY_FLOOR,
                    "weights": WEIGHTS,
                    "recent_decisions": self._quality_gate.recent_decisions(limit=10),
                    "recent_emissions": self._quality_gate.recent_emissions(limit=10),
                }
            )
        return block

    def _policy_now(self, policy: InitiativePolicy, now: datetime | None = None) -> datetime:
        timezone = self._timezone(policy.timezone)
        if now is None:
            return datetime.now(timezone)
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone)
        return now.astimezone(timezone)

    @staticmethod
    def _timezone(name: str) -> ZoneInfo:
        try:
            return ZoneInfo(name)
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")

    @staticmethod
    def _coerce_to_current_zone(value: datetime | None, current: datetime) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=current.tzinfo)
        if current.tzinfo is None:
            return value.replace(tzinfo=None)
        return value.astimezone(current.tzinfo)

    def _suppression_reason(
        self,
        candidate: InitiativeCandidate,
        *,
        policy: InitiativePolicy,
        media_session: dict[str, Any],
        now: datetime,
    ) -> str | None:
        if not policy.enabled:
            return "initiative disabled"
        if candidate.type not in policy.allowed_types:
            return f"initiative type disabled: {candidate.type}"
        if policy.do_not_disturb:
            return "do not disturb enabled"
        if policy.focus_mode:
            return "focus mode enabled"
        # late_night_checkin bypasses quiet hours because its window is the point.
        if is_quiet_time(now, policy.quiet_hours_start, policy.quiet_hours_end):
            if candidate.type not in LATE_NIGHT_TYPES:
                return "quiet hours active"
        if self.store.daily_count(now.date().isoformat()) >= policy.daily_limit:
            return "daily limit reached"

        # Event-driven types (calendar heads-ups) are deduped per-event by the
        # quality gate, so they skip the coarse per-type-per-day and spacing
        # throttles. The per-day skip is guarded on the gate actually being
        # active — without that per-event dedup we fall back to one-per-day so a
        # 10-minute tick can't repeat the same event.
        event_driven = candidate.type in EVENT_DRIVEN_TYPES
        per_event_deduped = event_driven and self._quality_gate_active()
        if not per_event_deduped and self.store.emitted_type_today(
            candidate.type, now.date().isoformat()
        ):
            return f"{candidate.type} already emitted today"

        if not event_driven:
            last_emitted = self.store.last_emitted_at()
            if last_emitted is not None:
                last_emitted = self._coerce_to_current_zone(last_emitted, now)
                elapsed = now - last_emitted
                if elapsed < timedelta(minutes=policy.min_spacing_minutes):
                    return "minimum initiative spacing active"

        mic_state = str(media_session.get("mic_state") or "idle")
        speaking_state = str(media_session.get("speaking_state") or "idle")
        if mic_state != "idle":
            return f"mic state is {mic_state}"
        if speaking_state in {"queued", "playing"}:
            return f"speaking state is {speaking_state}"

        if candidate.expires_at:
            try:
                if now > datetime.fromisoformat(candidate.expires_at):
                    return "candidate expired"
            except ValueError:
                return "candidate expiry invalid"

        return None

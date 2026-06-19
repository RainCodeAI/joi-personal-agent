from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.initiative.policy import (
    LATE_NIGHT_TYPES,
    InitiativeCandidate,
    InitiativeDecision,
    InitiativePolicy,
    is_quiet_time,
)
from app.initiative.store import InitiativeStore


class InitiativeService:
    """Builds and gates unsolicited Joi initiative candidates."""

    return_after_absence_threshold_minutes = 45
    late_night_recent_activity_minutes = 120

    def __init__(self, store: InitiativeStore | None = None) -> None:
        self.store = store or InitiativeStore()

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
            return InitiativeCandidate(
                type="memory_followup",
                priority="low",
                reason=f"unresolved memory from {age_hours:.0f}h ago",
                session_id=session_id,
                message=f'Earlier you mentioned: "{summary}" - did that go anywhere?',
                expires_at=expires_at,
            )
        return None

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
        decision = self.can_emit(
            candidate,
            policy=active_policy,
            media_session=media_session,
            now=current,
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

        await event_bus.publish(
            "initiative.emitted",
            {
                **decision.to_dict(),
                "emission": record,
            },
            session_id=candidate.session_id,
            source="initiative",
        )
        await self._notify_native(candidate)
        return decision

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
        }

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
        if self.store.emitted_type_today(candidate.type, now.date().isoformat()):
            return f"{candidate.type} already emitted today"

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

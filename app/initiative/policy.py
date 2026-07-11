from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Literal

from app.config import settings


InitiativeType = Literal[
    "daily_greeting",
    "return_after_absence",
    "late_night_checkin",
    "prolonged_silence",
    "memory_followup",
    "context_commentary",
]

InitiativePriority = Literal["low", "normal", "high"]

ALLOWED_INITIATIVE_TYPES: tuple[InitiativeType, ...] = (
    "daily_greeting",
    "return_after_absence",
    "late_night_checkin",
    "prolonged_silence",
    "memory_followup",
    "context_commentary",
)

# Types that are gated by the late-night window rather than quiet hours.
# They bypass quiet-hours suppression because the late-night window IS their purpose.
LATE_NIGHT_TYPES: frozenset[InitiativeType] = frozenset({"late_night_checkin"})


@dataclass(frozen=True)
class InitiativePolicy:
    enabled: bool
    daily_limit: int
    timezone: str
    daily_greeting_start: str
    daily_greeting_end: str
    quiet_hours_start: str
    quiet_hours_end: str
    focus_mode: bool
    do_not_disturb: bool
    allowed_types: tuple[InitiativeType, ...] = ALLOWED_INITIATIVE_TYPES
    min_spacing_minutes: int = 240
    late_night_start: str = "22:00"
    late_night_end: str = "01:00"
    silence_threshold_minutes: int = 90

    @classmethod
    def from_settings(cls) -> "InitiativePolicy":
        raw = str(getattr(settings, "initiative_allowed_types", "daily_greeting"))
        parsed: tuple[InitiativeType, ...] = tuple(
            t  # type: ignore[misc]
            for t in (piece.strip() for piece in raw.split(","))
            if t in ALLOWED_INITIATIVE_TYPES
        )
        allowed_values = list(parsed if parsed else ("daily_greeting",))
        if (
            bool(getattr(settings, "context_commentary_enabled", False))
            and "context_commentary" not in allowed_values
        ):
            allowed_values.append("context_commentary")
        allowed = tuple(allowed_values)
        return cls(
            enabled=bool(settings.enable_proactive_messaging and settings.initiative_enabled),
            daily_limit=max(0, min(int(settings.initiative_daily_limit), 3)),
            timezone=settings.initiative_timezone,
            daily_greeting_start=settings.initiative_daily_greeting_start,
            daily_greeting_end=settings.initiative_daily_greeting_end,
            quiet_hours_start=settings.initiative_quiet_hours_start,
            quiet_hours_end=settings.initiative_quiet_hours_end,
            focus_mode=bool(settings.initiative_focus_mode),
            do_not_disturb=bool(settings.initiative_do_not_disturb),
            allowed_types=allowed,
            late_night_start=settings.initiative_late_night_start,
            late_night_end=settings.initiative_late_night_end,
            silence_threshold_minutes=int(settings.initiative_silence_threshold_minutes),
        )


@dataclass(frozen=True)
class CandidateEvidence:
    """Attributable source backing a context-triggered initiative (Phase 10).

    Timer-driven candidates (daily greeting, absence return, etc.) carry no
    evidence and bypass the quality gate. Context-triggered candidates must
    reference a concrete, attributable source so the gate can judge relevance,
    recency, and novelty.
    """

    source_type: str
    excerpt: str
    source_id: str | None = None
    observed_at: str | None = None
    topic_key: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "source_type": self.source_type,
            "excerpt": self.excerpt,
            "source_id": self.source_id,
            "observed_at": self.observed_at,
            "topic_key": self.topic_key,
        }


@dataclass(frozen=True)
class InitiativeCandidate:
    type: InitiativeType
    priority: InitiativePriority
    reason: str
    session_id: str
    message: str
    expires_at: str | None = None
    context_event_id: str | None = None
    evidence: CandidateEvidence | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "priority": self.priority,
            "reason": self.reason,
            "session_id": self.session_id,
            "message": self.message,
            "expires_at": self.expires_at,
            "context_event_id": self.context_event_id,
            "evidence": self.evidence.to_dict() if self.evidence else None,
        }


@dataclass(frozen=True)
class InitiativeDecision:
    allowed: bool
    candidate: InitiativeCandidate
    suppressed_reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "candidate": self.candidate.to_dict(),
            "suppressed_reason": self.suppressed_reason,
        }


def is_quiet_time(now: datetime, start_value: str, end_value: str) -> bool:
    start = _parse_hhmm(start_value)
    end = _parse_hhmm(end_value)
    current = now.time()
    if start == end:
        return False
    if start < end:
        return start <= current < end
    return current >= start or current < end


def _parse_hhmm(value: str) -> time:
    try:
        hour, minute = value.split(":", 1)
        return time(hour=int(hour), minute=int(minute))
    except Exception:
        return time(0, 0)

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4


ContextSensitivity = Literal["public", "private", "sensitive"]
ContextCategory = Literal[
    "work_activity",
    "wellbeing",
    "appearance",
    "entertainment",
    "reminders",
    "social_app_activity",
]


@dataclass(frozen=True)
class ContextEvent:
    source: str
    kind: str
    category: ContextCategory
    confidence: float
    sensitivity: ContextSensitivity
    observed_at: str
    expires_at: str
    session_id: str = "default"
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    dedup_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ContextDecision:
    accepted: bool
    event: ContextEvent
    reason: str
    commentary_eligible: bool = False
    queued: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "commentary_eligible": self.commentary_eligible,
            "queued": self.queued,
            "event": self.event.to_dict(),
        }

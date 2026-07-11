"""Durable record of emitted context-triggered initiatives (Phase 10).

Repeat suppression needs to know what Joi has already said and about what. This
store keeps one record per emitted evidence-bound initiative, keyed by a
``topic_key`` so the quality gate can suppress a near-duplicate within a window,
and tracks the user's response so future scoring can learn from ignored or
unwelcome topics.

Timer-driven initiatives (daily greeting, absence return, etc.) are *not*
recorded here — their recurrence is intentional and handled by the existing
InitiativeStore's per-day checks.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Sequence

from app.persistence import read_json, write_json_atomic

_MAX_RECORDS = 500
_VALID_RESPONSES = {"engaged", "ignored", "negative", "unknown"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class InitiativeEmissionMemory:
    """Persisted history of evidence-bound initiative emissions."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("data/initiative_emissions.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._records: list[dict[str, Any]] = self._load()

    def record(
        self,
        *,
        initiative_type: str,
        topic_key: str,
        message: str,
        quality_score: float,
        source_ids: Sequence[str] | None = None,
        emitted_at: datetime | None = None,
    ) -> dict[str, Any]:
        record = {
            "id": str(uuid.uuid4()),
            "type": initiative_type,
            "topic_key": topic_key,
            "source_ids": list(source_ids or []),
            "message": message,
            "quality_score": round(float(quality_score), 4),
            "emitted_at": (emitted_at or _utc_now()).isoformat(),
            "user_response": "unknown",
        }
        with self._lock:
            self._records.append(record)
            if len(self._records) > _MAX_RECORDS:
                self._records = self._records[-_MAX_RECORDS:]
            self._persist()
        return dict(record)

    def seen_topic_within(
        self,
        topic_key: str,
        *,
        since_days: int = 7,
        now: datetime | None = None,
    ) -> bool:
        """True if this topic was emitted within the window (novelty suppression)."""
        if not topic_key:
            return False
        current = now or _utc_now()
        cutoff = current - timedelta(days=since_days)
        with self._lock:
            for record in self._records:
                if record.get("topic_key") != topic_key:
                    continue
                emitted = _parse_dt(record.get("emitted_at"))
                if emitted is not None and emitted >= cutoff:
                    return True
        return False

    def set_response(self, record_id: str, response: str) -> bool:
        """Record the user's reaction to an emitted initiative (feedback loop)."""
        if response not in _VALID_RESPONSES:
            raise ValueError(f"invalid response: {response}")
        with self._lock:
            for record in self._records:
                if record.get("id") == record_id:
                    record["user_response"] = response
                    self._persist()
                    return True
        return False

    def recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(record) for record in self._records[-max(1, limit):][::-1]]

    def _load(self) -> list[dict[str, Any]]:
        data = read_json(self.path, [])
        if isinstance(data, list):
            return [record for record in data if isinstance(record, dict) and record.get("id")]
        return []

    def _persist(self) -> None:
        write_json_atomic(self.path, self._records)

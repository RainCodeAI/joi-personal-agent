from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any


class InitiativeStore:
    """Small persisted ledger for unsolicited initiative decisions."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("data/initiative_state.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._state = self._load()

    def record_emitted(
        self,
        *,
        initiative_type: str,
        session_id: str,
        message: str,
        reason: str,
        emitted_at: datetime,
    ) -> dict[str, Any]:
        record = {
            "type": initiative_type,
            "session_id": session_id,
            "message": message,
            "reason": reason,
            "emitted_at": emitted_at.isoformat(),
        }
        with self._lock:
            self._state.setdefault("emissions", []).append(record)
            self._state["last_emitted_at"] = record["emitted_at"]
            self._persist()
        return record

    def record_suppressed(
        self,
        *,
        initiative_type: str,
        session_id: str,
        reason: str,
        checked_at: datetime,
    ) -> dict[str, Any]:
        record = {
            "type": initiative_type,
            "session_id": session_id,
            "reason": reason,
            "checked_at": checked_at.isoformat(),
        }
        with self._lock:
            self._state["last_suppressed"] = record
            self._persist()
        return record

    def record_user_activity(
        self,
        *,
        session_id: str,
        source: str,
        observed_at: datetime,
        clear_absence: bool = False,
    ) -> dict[str, Any]:
        record = {
            "session_id": session_id,
            "source": source,
            "observed_at": observed_at.isoformat(),
        }
        with self._lock:
            self._state["last_user_activity"] = record
            per_session = self._state.setdefault("last_user_activity_by_session", {})
            if isinstance(per_session, dict):
                per_session[session_id] = record
            if clear_absence:
                legacy = self._state.get("absence_started_at")
                if isinstance(legacy, dict) and legacy.get("session_id") == session_id:
                    self._state.pop("absence_started_at", None)
                absence_by_session = self._state.get("absence_started_by_session")
                if isinstance(absence_by_session, dict):
                    absence_by_session.pop(session_id, None)
            self._persist()
        return record

    def record_absence_started(
        self,
        *,
        session_id: str,
        source: str,
        observed_at: datetime,
    ) -> dict[str, Any]:
        record = {
            "session_id": session_id,
            "source": source,
            "observed_at": observed_at.isoformat(),
        }
        with self._lock:
            self._state["absence_started_at"] = record
            per_session = self._state.setdefault("absence_started_by_session", {})
            if isinstance(per_session, dict):
                per_session[session_id] = record
            self._persist()
        return record

    def clear_absence(self, *, session_id: str) -> None:
        with self._lock:
            legacy = self._state.get("absence_started_at")
            if isinstance(legacy, dict) and legacy.get("session_id") == session_id:
                self._state.pop("absence_started_at", None)
            per_session = self._state.get("absence_started_by_session")
            if isinstance(per_session, dict):
                per_session.pop(session_id, None)
            self._persist()

    def last_user_activity_at(self) -> datetime | None:
        """Return the timestamp of the most recent recorded user activity, regardless of session."""
        with self._lock:
            record = self._state.get("last_user_activity")
        if not isinstance(record, dict):
            return None
        try:
            return datetime.fromisoformat(str(record.get("observed_at", "")))
        except ValueError:
            return None

    def last_user_activity_for_session(self, session_id: str) -> datetime | None:
        with self._lock:
            per_session = self._state.get("last_user_activity_by_session")
            record = per_session.get(session_id) if isinstance(per_session, dict) else None
            if not isinstance(record, dict):
                legacy = self._state.get("last_user_activity")
                record = legacy if isinstance(legacy, dict) and legacy.get("session_id") == session_id else None
        if not isinstance(record, dict):
            return None
        try:
            return datetime.fromisoformat(str(record.get("observed_at", "")))
        except ValueError:
            return None

    def absence_started_at(self, session_id: str) -> datetime | None:
        with self._lock:
            per_session = self._state.get("absence_started_by_session")
            record = per_session.get(session_id) if isinstance(per_session, dict) else None
            if not isinstance(record, dict):
                record = self._state.get("absence_started_at")
        if not isinstance(record, dict) or record.get("session_id") != session_id:
            return None
        try:
            return datetime.fromisoformat(str(record.get("observed_at")))
        except ValueError:
            return None

    def daily_count(self, day: str) -> int:
        with self._lock:
            return sum(
                1
                for record in self._state.get("emissions", [])
                if str(record.get("emitted_at", "")).startswith(day)
            )

    def emitted_type_today(self, initiative_type: str, day: str) -> bool:
        with self._lock:
            return any(
                record.get("type") == initiative_type
                and str(record.get("emitted_at", "")).startswith(day)
                for record in self._state.get("emissions", [])
            )

    def last_emitted_at(self) -> datetime | None:
        with self._lock:
            raw = self._state.get("last_emitted_at")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw))
        except ValueError:
            return None

    def snapshot(self, now: datetime) -> dict[str, Any]:
        day = now.date().isoformat()
        with self._lock:
            last_suppressed = self._state.get("last_suppressed")
            last_emitted_at = self._state.get("last_emitted_at")
            last_user_activity = self._state.get("last_user_activity")
            absence_started_at = self._state.get("absence_started_at")
        return {
            "daily_count": self.daily_count(day),
            "day": day,
            "last_emitted_at": last_emitted_at,
            "last_suppressed": last_suppressed,
            "last_user_activity": last_user_activity,
            "absence_started_at": absence_started_at,
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"emissions": []}
        try:
            data = json.loads(self.path.read_text())
            if not isinstance(data, dict):
                return {"emissions": []}
            data.setdefault("emissions", [])
            return data
        except Exception:
            return {"emissions": []}

    def _persist(self) -> None:
        self.path.write_text(json.dumps(self._state, indent=2, sort_keys=True))

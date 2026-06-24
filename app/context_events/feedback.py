from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.persistence import read_json, write_json_atomic


class ContextFeedbackStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()
        loaded = read_json(path, {})
        self._state: dict[str, Any] = loaded if isinstance(loaded, dict) else {}
        self._state.setdefault("records", [])
        self._state.setdefault("blocked_kinds", [])
        self._state.setdefault("category_cooldowns", {})

    def record(
        self,
        *,
        event_id: str,
        kind: str,
        category: str,
        action: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        current = now or datetime.now(timezone.utc)
        record = {
            "event_id": event_id,
            "kind": kind,
            "category": category,
            "action": action,
            "created_at": current.isoformat(),
        }
        with self._lock:
            records = self._state.setdefault("records", [])
            records.append(record)
            self._state["records"] = records[-500:]
            if action == "never_comment":
                blocked = set(self._state.setdefault("blocked_kinds", []))
                blocked.add(kind)
                self._state["blocked_kinds"] = sorted(blocked)
            elif action == "too_much":
                cooldowns = self._state.setdefault("category_cooldowns", {})
                cooldowns[category] = (current + timedelta(hours=24)).isoformat()
            self._persist_locked()
        return record

    def kind_blocked(self, kind: str) -> bool:
        with self._lock:
            return kind in set(self._state.get("blocked_kinds", []))

    def category_cooldown_active(
        self,
        category: str,
        *,
        now: datetime | None = None,
    ) -> bool:
        current = now or datetime.now(timezone.utc)
        with self._lock:
            raw = self._state.get("category_cooldowns", {}).get(category)
        if not raw:
            return False
        try:
            until = datetime.fromisoformat(str(raw))
            if until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
        except ValueError:
            return False
        return until > current

    def diagnostics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "feedback_records": len(self._state.get("records", [])),
                "blocked_kinds": list(self._state.get("blocked_kinds", [])),
                "category_cooldowns": dict(self._state.get("category_cooldowns", {})),
            }

    def find_record(self, event_id: str) -> dict[str, Any] | None:
        with self._lock:
            for record in reversed(self._state.get("records", [])):
                if record.get("event_id") == event_id:
                    return dict(record)
        return None

    def _persist_locked(self) -> None:
        write_json_atomic(self.path, self._state)

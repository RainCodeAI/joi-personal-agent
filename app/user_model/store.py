from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any


class UserModelCorrectionStore:
    """Durable JSON store for user model corrections.

    This is intentionally small while Phase 9 is contract-first. It gives the
    user persistent veto/edit/add behavior without introducing a DB migration.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("data/user_model_corrections.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._state = self._load()

    def record(
        self,
        *,
        user_id: str,
        section_key: str,
        action: str,
        item_id: str | None = None,
        label: str | None = None,
        value: str | None = None,
        note: str | None = None,
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        timestamp = (created_at or datetime.utcnow()).isoformat()
        correction_id = str(uuid.uuid4())
        resolved_item_id = item_id
        if action == "add" and not resolved_item_id:
            resolved_item_id = f"{section_key}:user:{correction_id}"
        record = {
            "id": correction_id,
            "user_id": user_id,
            "section_key": section_key,
            "action": action,
            "item_id": resolved_item_id,
            "label": label,
            "value": value,
            "note": note,
            "created_at": timestamp,
        }
        with self._lock:
            self._state.setdefault("corrections", []).append(record)
            self._persist()
        return record

    def list_for_user(self, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            self._state = self._load()
            records = [
                dict(record)
                for record in self._state.get("corrections", [])
                if isinstance(record, dict) and record.get("user_id") == user_id
            ]
        return sorted(records, key=lambda record: str(record.get("created_at") or ""))

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"corrections": []}
        try:
            data = json.loads(self.path.read_text())
            if not isinstance(data, dict):
                return {"corrections": []}
            corrections = data.get("corrections")
            if not isinstance(corrections, list):
                data["corrections"] = []
            return data
        except Exception:
            return {"corrections": []}

    def _persist(self) -> None:
        self.path.write_text(json.dumps(self._state, indent=2, sort_keys=True))

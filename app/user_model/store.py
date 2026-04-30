from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from app.user_model.synthesis import SynthesisCandidate


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


class UserModelSynthesisRecordStore:
    """Durable JSON audit store for synthesis dry-run candidates.

    Records are diagnostic only. They do not represent user-model writes and
    should not be used as trusted profile data.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("data/user_model_synthesis_records.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._state = self._load()

    def record_candidates(
        self,
        *,
        user_id: str,
        session_id: str,
        method: str,
        candidates: list[SynthesisCandidate],
        dry_run: bool = True,
        created_at: datetime | None = None,
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []

        timestamp = (created_at or datetime.utcnow()).isoformat()
        run_id = str(uuid.uuid4())
        records = [
            self._record_for_candidate(
                candidate,
                user_id=user_id,
                session_id=session_id,
                method=method,
                run_id=run_id,
                dry_run=dry_run,
                created_at=timestamp,
            )
            for candidate in candidates
        ]
        with self._lock:
            self._state.setdefault("records", []).extend(records)
            self._persist()
        return records

    def list_records(
        self,
        *,
        user_id: str | None = None,
        session_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._lock:
            self._state = self._load()
            records = [
                dict(record)
                for record in self._state.get("records", [])
                if isinstance(record, dict)
            ]

        if user_id is not None:
            records = [record for record in records if record.get("user_id") == user_id]
        if session_id is not None:
            records = [record for record in records if record.get("session_id") == session_id]

        records.sort(key=lambda record: str(record.get("created_at") or ""), reverse=True)
        return records[: max(0, limit)]

    def _record_for_candidate(
        self,
        candidate: SynthesisCandidate,
        *,
        user_id: str,
        session_id: str,
        method: str,
        run_id: str,
        dry_run: bool,
        created_at: str,
    ) -> dict[str, Any]:
        skipped_reason = ""
        if candidate.blocked_by_correction:
            skipped_reason = "blocked_by_correction"
        elif candidate.duplicate_of_existing:
            skipped_reason = "duplicate_of_existing"

        skipped = bool(skipped_reason)
        written = False if dry_run else not skipped
        if skipped:
            status = "skipped"
        elif written:
            status = "written"
        else:
            status = "dry_run"

        return {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "user_id": user_id,
            "session_id": session_id,
            "candidate_id": candidate.candidate_id,
            "section_key": candidate.section_key,
            "label": candidate.label,
            "method": method,
            "evidence_excerpt": candidate.source_excerpt,
            "confidence": candidate.confidence,
            "status": status,
            "skipped": skipped,
            "skipped_reason": skipped_reason,
            "written": written,
            "dry_run": dry_run,
            "source_message_role": candidate.source_message_role,
            "source_message_index": candidate.source_message_index,
            "created_at": created_at,
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"records": []}
        try:
            data = json.loads(self.path.read_text())
            if not isinstance(data, dict):
                return {"records": []}
            records = data.get("records")
            if not isinstance(records, list):
                data["records"] = []
            return data
        except Exception:
            return {"records": []}

    def _persist(self) -> None:
        self.path.write_text(json.dumps(self._state, indent=2, sort_keys=True))

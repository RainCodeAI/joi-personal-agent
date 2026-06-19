"""Backend-owned human approval queue for sensitive local actions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import RLock
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.orchestrator.policies import DESTRUCTIVE_TOOLS
from app.persistence import read_json, write_json_atomic


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


@dataclass
class PendingApproval:
    """One queued approval request.

    Approvals are intentionally local-only and in-memory for the first web flow.
    Future desktop actions can reuse the same explicit queue before execution.
    """

    id: str
    tool_name: str
    args: Dict[str, Any]
    session_id: Optional[str] = None
    local_only: bool = True
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    resolved_at: Optional[str] = None


class ToolApprovalManager:
    """Manages explicit approval decisions for the FastAPI runtime."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._store: Dict[str, PendingApproval] = {}
        self._lock = RLock()
        self._load()

    @staticmethod
    def needs_approval(tool_name: str) -> bool:
        """Check whether a tool requires user confirmation before execution."""

        return tool_name in DESTRUCTIVE_TOOLS

    def request_approval(
        self,
        tool_name: str,
        args: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> str:
        """Queue a new approval request. Returns the pending ID."""

        pending = PendingApproval(
            id=str(uuid.uuid4()),
            tool_name=tool_name,
            args=args,
            session_id=session_id,
        )
        with self._lock:
            self._store[pending.id] = pending
            self._persist()
        return pending.id

    def approve(self, pending_id: str) -> Optional[PendingApproval]:
        """Mark a pending request as approved."""

        with self._lock:
            pending = self._store.get(pending_id)
            if pending is None or pending.status != ApprovalStatus.PENDING:
                return None
            pending.status = ApprovalStatus.APPROVED
            pending.resolved_at = datetime.utcnow().isoformat()
            self._persist()
            return pending

    def deny(self, pending_id: str) -> Optional[PendingApproval]:
        """Mark a pending request as denied."""

        with self._lock:
            pending = self._store.get(pending_id)
            if pending is None or pending.status != ApprovalStatus.PENDING:
                return None
            pending.status = ApprovalStatus.DENIED
            pending.resolved_at = datetime.utcnow().isoformat()
            self._persist()
            return pending

    def check_approval(self, pending_id: str) -> Optional[bool]:
        """Return True if approved, False if denied, None if still pending."""

        with self._lock:
            approval = self._store.get(pending_id)
        if approval is None:
            return None
        if approval.status == ApprovalStatus.APPROVED:
            return True
        if approval.status == ApprovalStatus.DENIED:
            return False
        return None

    def get_pending(self, session_id: Optional[str] = None) -> List[PendingApproval]:
        """Return all unresolved approval requests."""

        with self._lock:
            return [
                approval
                for approval in self._store.values()
                if approval.status == ApprovalStatus.PENDING
                and (session_id is None or approval.session_id == session_id)
            ]

    def get(self, pending_id: str) -> Optional[PendingApproval]:
        """Return a pending or resolved approval by ID."""

        with self._lock:
            return self._store.get(pending_id)

    def clear_resolved(self) -> int:
        """Remove resolved approval entries. Returns count removed."""

        with self._lock:
            resolved_ids = [
                pending_id
                for pending_id, approval in self._store.items()
                if approval.status != ApprovalStatus.PENDING
            ]
            for pending_id in resolved_ids:
                del self._store[pending_id]
            self._persist()
            return len(resolved_ids)

    def _load(self) -> None:
        if self.path is None:
            return
        raw = read_json(self.path, [])
        if not isinstance(raw, list):
            return
        for item in raw:
            try:
                approval = PendingApproval(
                    id=str(item["id"]),
                    tool_name=str(item["tool_name"]),
                    args=dict(item.get("args") or {}),
                    session_id=item.get("session_id"),
                    local_only=bool(item.get("local_only", True)),
                    status=ApprovalStatus(str(item.get("status", "pending"))),
                    created_at=str(item.get("created_at") or datetime.utcnow().isoformat()),
                    resolved_at=item.get("resolved_at"),
                )
            except (KeyError, TypeError, ValueError):
                continue
            self._store[approval.id] = approval

    def _persist(self) -> None:
        if self.path is None:
            return
        write_json_atomic(
            self.path,
            [
                {
                    "id": approval.id,
                    "tool_name": approval.tool_name,
                    "args": approval.args,
                    "session_id": approval.session_id,
                    "local_only": approval.local_only,
                    "status": approval.status.value,
                    "created_at": approval.created_at,
                    "resolved_at": approval.resolved_at,
                }
                for approval in self._store.values()
            ],
        )

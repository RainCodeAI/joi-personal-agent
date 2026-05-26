"""Backend-owned human approval queue for sensitive local actions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import RLock
from typing import Any, Dict, List, Optional

from app.orchestrator.policies import DESTRUCTIVE_TOOLS


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

    def __init__(self, store: Optional[Dict[str, PendingApproval]] = None) -> None:
        self._store: Dict[str, PendingApproval] = store if store is not None else {}
        self._lock = RLock()

    @classmethod
    def from_session_state(cls, session_state) -> "ToolApprovalManager":
        """Legacy adapter for the temporary Streamlit client.

        The primary runtime path uses ``app.api.state.approval_manager``.
        """

        key = "_tool_approval_store"
        if key not in session_state:
            session_state[key] = {}
        return cls(store=session_state[key])

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
        return pending.id

    def approve(self, pending_id: str) -> Optional[PendingApproval]:
        """Mark a pending request as approved."""

        with self._lock:
            pending = self._store.get(pending_id)
            if pending is None or pending.status != ApprovalStatus.PENDING:
                return None
            pending.status = ApprovalStatus.APPROVED
            pending.resolved_at = datetime.utcnow().isoformat()
            return pending

    def deny(self, pending_id: str) -> Optional[PendingApproval]:
        """Mark a pending request as denied."""

        with self._lock:
            pending = self._store.get(pending_id)
            if pending is None or pending.status != ApprovalStatus.PENDING:
                return None
            pending.status = ApprovalStatus.DENIED
            pending.resolved_at = datetime.utcnow().isoformat()
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

    def get_pending(self) -> List[PendingApproval]:
        """Return all unresolved approval requests."""

        with self._lock:
            return [
                approval
                for approval in self._store.values()
                if approval.status == ApprovalStatus.PENDING
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
            return len(resolved_ids)

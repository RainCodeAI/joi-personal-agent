"""ToolApprovalManager — Human-in-the-Loop confirmation for destructive actions.

Integrates with Streamlit ``st.session_state`` so the Chat page can render
confirm / deny buttons before any write operation executes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from app.orchestrator.policies import DESTRUCTIVE_TOOLS


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


@dataclass
class PendingApproval:
    """One queued approval request."""
    id: str
    tool_name: str
    args: Dict[str, Any]
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    resolved_at: Optional[str] = None


class ToolApprovalManager:
    """Manages pending approvals via an in-memory dict (backed by session state).

    Typical flow::

        mgr = ToolApprovalManager.from_session_state(st.session_state)

        if mgr.needs_approval("send_email"):
            pending_id = mgr.request_approval("send_email", {"to": "x@y.com"})
            # UI renders confirm / deny buttons keyed by pending_id
            return  # don't execute yet

        # Later, after user clicks "Approve":
        mgr.approve(pending_id)
        if mgr.check_approval(pending_id):
            execute_tool(...)
    """

    def __init__(self, store: Optional[Dict[str, PendingApproval]] = None) -> None:
        self._store: Dict[str, PendingApproval] = store or {}

    # ── session-state integration ─────────────────────────────────────────

    @classmethod
    def from_session_state(cls, session_state) -> "ToolApprovalManager":
        """Create / retrieve the manager from Streamlit session state."""
        key = "_tool_approval_store"
        if key not in session_state:
            session_state[key] = {}
        return cls(store=session_state[key])

    # ── public API ────────────────────────────────────────────────────────

    @staticmethod
    def needs_approval(tool_name: str) -> bool:
        """Check whether a tool requires user confirmation before execution."""
        return tool_name in DESTRUCTIVE_TOOLS

    def request_approval(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Queue a new approval request.  Returns the pending ID."""
        pending = PendingApproval(
            id=str(uuid.uuid4()),
            tool_name=tool_name,
            args=args,
        )
        self._store[pending.id] = pending
        return pending.id

    def approve(self, pending_id: str) -> None:
        """Mark a pending request as approved."""
        if pending_id in self._store:
            self._store[pending_id].status = ApprovalStatus.APPROVED
            self._store[pending_id].resolved_at = datetime.utcnow().isoformat()

    def deny(self, pending_id: str) -> None:
        """Mark a pending request as denied."""
        if pending_id in self._store:
            self._store[pending_id].status = ApprovalStatus.DENIED
            self._store[pending_id].resolved_at = datetime.utcnow().isoformat()

    def check_approval(self, pending_id: str) -> Optional[bool]:
        """Return True if approved, False if denied, None if still pending."""
        pa = self._store.get(pending_id)
        if pa is None:
            return None
        if pa.status == ApprovalStatus.APPROVED:
            return True
        if pa.status == ApprovalStatus.DENIED:
            return False
        return None  # still pending

    def get_pending(self) -> List[PendingApproval]:
        """Return all unresolved approval requests."""
        return [
            pa for pa in self._store.values()
            if pa.status == ApprovalStatus.PENDING
        ]

    def clear_resolved(self) -> int:
        """Remove resolved (approved + denied) entries.  Returns count removed."""
        resolved_ids = [
            pid for pid, pa in self._store.items()
            if pa.status != ApprovalStatus.PENDING
        ]
        for pid in resolved_ids:
            del self._store[pid]
        return len(resolved_ids)

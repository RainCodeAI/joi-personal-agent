"""Backend-owned, proposal-bound approval queue for sensitive local actions."""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

from app.orchestrator.policies import DESTRUCTIVE_TOOLS
from app.persistence import read_json, write_json_atomic
from app.tools.types import (
    ApprovedToolExecution,
    ToolOperation,
    ToolPreview,
    ToolProposal,
    fingerprint_tool_arguments,
)

_APPROVAL_TTL_MINUTES = 15


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    INVALID = "invalid"


class ApprovalResolutionError(ValueError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass
class PendingApproval:
    id: str
    tool_name: str
    args: Dict[str, Any]
    session_id: Optional[str] = None
    local_only: bool = True
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: str = field(default_factory=lambda: _utc_now().isoformat())
    resolved_at: Optional[str] = None
    proposal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    operation: str = ToolOperation.WRITE.value
    preview: Dict[str, Any] = field(default_factory=dict)
    redacted_preview: Dict[str, Any] = field(default_factory=dict)
    args_fingerprint: str = ""
    expires_at: str = ""
    consumed_at: Optional[str] = None
    idempotency_key: str = ""

    def __post_init__(self) -> None:
        if not self.args_fingerprint:
            self.args_fingerprint = fingerprint_tool_arguments(
                proposal_id=self.proposal_id,
                tool_name=self.tool_name,
                operation=self.operation,
                arguments=self.args,
            )
        if not self.expires_at:
            self.expires_at = (
                _parse_datetime(self.created_at) + timedelta(minutes=_APPROVAL_TTL_MINUTES)
            ).isoformat()
        if not self.idempotency_key:
            self.idempotency_key = self.proposal_id


class ToolApprovalManager:
    """Persists exact previews and emits one-use approved execution capabilities."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._store: Dict[str, PendingApproval] = {}
        self._lock = RLock()
        self._load()

    @staticmethod
    def needs_approval(tool_name: str) -> bool:
        return tool_name in DESTRUCTIVE_TOOLS

    def request_proposal(
        self,
        proposal: ToolProposal,
        *,
        preview: ToolPreview,
        redacted_preview: ToolPreview,
        session_id: Optional[str] = None,
    ) -> str:
        if preview.proposal_id != proposal.proposal_id:
            raise ValueError("preview does not belong to proposal")
        if preview.arguments_sha256 != redacted_preview.arguments_sha256:
            raise ValueError("preview fingerprints do not match")
        pending = PendingApproval(
            id=str(uuid.uuid4()),
            proposal_id=proposal.proposal_id,
            tool_name=proposal.tool_name,
            operation=proposal.operation.value,
            args=copy.deepcopy(proposal.arguments),
            preview=preview.model_dump(mode="json"),
            redacted_preview=redacted_preview.model_dump(mode="json"),
            args_fingerprint=preview.arguments_sha256,
            idempotency_key=proposal.idempotency_key or proposal.proposal_id,
            session_id=session_id,
        )
        with self._lock:
            self._store[pending.id] = pending
            self._persist()
        return pending.id

    def request_approval(
        self,
        tool_name: str,
        args: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> str:
        """Migration helper for older callers; new code should request a proposal."""
        proposal_id = str(uuid.uuid4())
        operation = ToolOperation.WRITE
        fingerprint = fingerprint_tool_arguments(
            proposal_id=proposal_id,
            tool_name=tool_name,
            operation=operation,
            arguments=args,
        )
        preview = {
            "proposal_id": proposal_id,
            "tool_name": tool_name,
            "operation": operation.value,
            "summary": f"Run {tool_name} with the displayed arguments.",
            "arguments": copy.deepcopy(args),
            "sensitive_fields_redacted": False,
            "arguments_sha256": fingerprint,
        }
        pending = PendingApproval(
            id=str(uuid.uuid4()),
            proposal_id=proposal_id,
            tool_name=tool_name,
            operation=operation.value,
            args=copy.deepcopy(args),
            preview=preview,
            redacted_preview={**preview, "arguments": {}},
            args_fingerprint=fingerprint,
            idempotency_key=proposal_id,
            session_id=session_id,
        )
        with self._lock:
            self._store[pending.id] = pending
            self._persist()
        return pending.id

    def approve_for_execution(
        self,
        pending_id: str,
        *,
        proposal_id: str,
        now: datetime | None = None,
    ) -> ApprovedToolExecution:
        current = (now or _utc_now()).astimezone(timezone.utc)
        with self._lock:
            pending = self._require_pending(pending_id, proposal_id=proposal_id, now=current)
            actual_fingerprint = fingerprint_tool_arguments(
                proposal_id=pending.proposal_id,
                tool_name=pending.tool_name,
                operation=pending.operation,
                arguments=pending.args,
            )
            if actual_fingerprint != pending.args_fingerprint:
                pending.status = ApprovalStatus.INVALID
                pending.resolved_at = current.isoformat()
                self._persist()
                raise ApprovalResolutionError(
                    "Approval arguments changed after preview",
                    code="arguments_changed",
                )
            pending.status = ApprovalStatus.APPROVED
            pending.resolved_at = current.isoformat()
            pending.consumed_at = current.isoformat()
            execution = ApprovedToolExecution(
                approval_id=pending.id,
                proposal_id=pending.proposal_id,
                tool_name=pending.tool_name,
                operation=ToolOperation(pending.operation),
                arguments=copy.deepcopy(pending.args),
                arguments_sha256=pending.args_fingerprint,
                idempotency_key=pending.idempotency_key,
            )
            self._persist()
            return execution

    def approve(self, pending_id: str, *, proposal_id: str) -> PendingApproval:
        """Resolve approval without executing; retained for status-oriented callers."""
        self.approve_for_execution(pending_id, proposal_id=proposal_id)
        approval = self.get(pending_id)
        if approval is None:  # pragma: no cover - guarded by approve_for_execution
            raise ApprovalResolutionError("Approval not found", code="not_found")
        return approval

    def deny(
        self,
        pending_id: str,
        *,
        proposal_id: str,
        now: datetime | None = None,
    ) -> PendingApproval:
        current = (now or _utc_now()).astimezone(timezone.utc)
        with self._lock:
            pending = self._require_pending(pending_id, proposal_id=proposal_id, now=current)
            pending.status = ApprovalStatus.DENIED
            pending.resolved_at = current.isoformat()
            self._persist()
            return pending

    def _require_pending(
        self,
        pending_id: str,
        *,
        proposal_id: str,
        now: datetime,
    ) -> PendingApproval:
        pending = self._store.get(pending_id)
        if pending is None:
            raise ApprovalResolutionError("Approval not found", code="not_found")
        if pending.status != ApprovalStatus.PENDING:
            raise ApprovalResolutionError("Approval was already resolved", code="already_resolved")
        if pending.proposal_id != proposal_id:
            raise ApprovalResolutionError("Approval proposal does not match", code="proposal_mismatch")
        if _parse_datetime(pending.expires_at) <= now:
            pending.status = ApprovalStatus.EXPIRED
            pending.resolved_at = now.isoformat()
            self._persist()
            raise ApprovalResolutionError("Approval expired", code="expired")
        return pending

    def check_approval(self, pending_id: str) -> Optional[bool]:
        with self._lock:
            approval = self._store.get(pending_id)
        if approval is None or approval.status == ApprovalStatus.PENDING:
            return None
        if approval.status == ApprovalStatus.APPROVED:
            return True
        return False

    def get_pending(self, session_id: Optional[str] = None) -> List[PendingApproval]:
        with self._lock:
            current = _utc_now()
            changed = False
            for approval in self._store.values():
                if (
                    approval.status == ApprovalStatus.PENDING
                    and _parse_datetime(approval.expires_at) <= current
                ):
                    approval.status = ApprovalStatus.EXPIRED
                    approval.resolved_at = current.isoformat()
                    changed = True
            if changed:
                self._persist()
            return [
                approval
                for approval in self._store.values()
                if approval.status == ApprovalStatus.PENDING
                and (session_id is None or approval.session_id == session_id)
            ]

    def get(self, pending_id: str) -> Optional[PendingApproval]:
        with self._lock:
            return self._store.get(pending_id)

    def clear_resolved(self) -> int:
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
                    proposal_id=str(item.get("proposal_id") or f"legacy:{item['id']}"),
                    tool_name=str(item["tool_name"]),
                    operation=str(item.get("operation") or ToolOperation.WRITE.value),
                    args=dict(item.get("args") or {}),
                    session_id=item.get("session_id"),
                    local_only=bool(item.get("local_only", True)),
                    status=ApprovalStatus(str(item.get("status", "pending"))),
                    created_at=str(item.get("created_at") or _utc_now().isoformat()),
                    resolved_at=item.get("resolved_at"),
                    preview=dict(item.get("preview") or {}),
                    redacted_preview=dict(item.get("redacted_preview") or {}),
                    args_fingerprint=str(item.get("args_fingerprint") or ""),
                    expires_at=str(item.get("expires_at") or ""),
                    consumed_at=item.get("consumed_at"),
                    idempotency_key=str(item.get("idempotency_key") or ""),
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
                    "proposal_id": approval.proposal_id,
                    "tool_name": approval.tool_name,
                    "operation": approval.operation,
                    "args": approval.args,
                    "preview": approval.preview,
                    "redacted_preview": approval.redacted_preview,
                    "args_fingerprint": approval.args_fingerprint,
                    "session_id": approval.session_id,
                    "local_only": approval.local_only,
                    "status": approval.status.value,
                    "created_at": approval.created_at,
                    "expires_at": approval.expires_at,
                    "resolved_at": approval.resolved_at,
                    "consumed_at": approval.consumed_at,
                    "idempotency_key": approval.idempotency_key,
                }
                for approval in self._store.values()
            ],
        )

from __future__ import annotations

from pathlib import Path

from app.api.media_session import MediaSessionStore
from app.orchestrator.security.approval import ApprovalStatus, ToolApprovalManager


def test_approval_queue_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "approvals.json"
    first = ToolApprovalManager(path)
    approval_id = first.request_approval(
        "send_email",
        {"to": "person@example.com", "subject": "Hello", "body": "Body"},
        session_id="session-1",
    )

    restored = ToolApprovalManager(path)
    approval = restored.get(approval_id)

    assert approval is not None
    assert approval.status == ApprovalStatus.PENDING
    assert restored.get_pending("session-1")[0].id == approval_id

    restored.deny(approval_id)
    denied = ToolApprovalManager(path).get(approval_id)
    assert denied is not None
    assert denied.status == ApprovalStatus.DENIED


def test_media_session_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "media.json"
    first = MediaSessionStore(path)
    first.update(
        "session-1",
        mic_state="idle",
        speaking_state="interrupted",
        interruption_count=2,
    )

    restored = MediaSessionStore(path).get("session-1")

    assert restored["speaking_state"] == "interrupted"
    assert restored["interruption_count"] == 2

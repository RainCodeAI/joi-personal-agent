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
        assistant_turn_id="turn-7",
        voice_mode="conversation",
        turn_state="interrupted",
        mic_state="idle",
        speaking_state="interrupted",
        speech_detected=True,
        speech_duration_ms=640,
        interruption_count=2,
    )

    restored = MediaSessionStore(path).get("session-1")

    assert restored["assistant_turn_id"] == "turn-7"
    assert restored["voice_mode"] == "conversation"
    assert restored["turn_state"] == "interrupted"
    assert restored["speaking_state"] == "interrupted"
    assert restored["speech_detected"] is True
    assert restored["speech_duration_ms"] == 640
    assert restored["interruption_count"] == 2


def test_media_session_backfills_voice_state_fields(tmp_path: Path) -> None:
    path = tmp_path / "media.json"
    path.write_text(
        '{"legacy-session":{"session_id":"legacy-session","mic_state":"idle"}}',
        encoding="utf-8",
    )

    restored = MediaSessionStore(path).get("legacy-session")

    assert restored["voice_mode"] == "push_to_talk"
    assert restored["turn_state"] == "idle"
    assert restored["assistant_turn_id"] is None
    assert restored["speech_detected"] is False

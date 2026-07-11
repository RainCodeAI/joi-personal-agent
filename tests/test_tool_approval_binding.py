"""Write execution is bound to one exact, expiring, one-use proposal."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.orchestrator.agents.executor import ExecutorAgent
from app.orchestrator.security.approval import (
    ApprovalResolutionError,
    ApprovalStatus,
    ToolApprovalManager,
)
from app.tools.registry import tool_registry


EMAIL_ARGS = {
    "to": "rain@example.com",
    "subject": "Status",
    "body": "The build passed.",
}


def request_email(manager: ToolApprovalManager):
    proposal = tool_registry.create_proposal("send_email", EMAIL_ARGS)
    preview = tool_registry.build_preview(proposal, redact_sensitive=False)
    redacted = tool_registry.build_preview(proposal, redact_sensitive=True)
    approval_id = manager.request_proposal(
        proposal,
        preview=preview,
        redacted_preview=redacted,
        session_id="telegram:111",
    )
    return proposal, approval_id


def test_exact_and_redacted_previews_share_the_bound_fingerprint():
    manager = ToolApprovalManager()
    proposal, approval_id = request_email(manager)
    approval = manager.get(approval_id)

    assert approval is not None
    assert approval.proposal_id == proposal.proposal_id
    assert approval.preview["arguments"] == EMAIL_ARGS
    assert approval.redacted_preview["arguments"] == {
        "to": "[redacted]",
        "subject": "Status",
        "body": "[redacted]",
    }
    assert approval.preview["arguments_sha256"] == approval.args_fingerprint
    assert approval.redacted_preview["arguments_sha256"] == approval.args_fingerprint


@patch("app.tools.email_gmail", create=True)
def test_consumed_approval_executes_exact_email_once(mock_gmail):
    mock_gmail.is_authenticated.return_value = True
    mock_gmail.send_message.return_value = {"id": "message-1"}
    mock_gmail.verify_sent_message.return_value = {
        "verified": True,
        "provider_id": "message-1",
    }
    manager = ToolApprovalManager()
    proposal, approval_id = request_email(manager)

    execution = manager.approve_for_execution(
        approval_id,
        proposal_id=proposal.proposal_id,
    )
    result = ExecutorAgent().run_approved_tool(execution)

    assert result.status == "success"
    assert result.result["status"] == "Email sent"
    mock_gmail.send_message.assert_called_once_with(
        to="rain@example.com",
        subject="Status",
        body="The build passed.",
        idempotency_key=execution.idempotency_key,
    )
    mock_gmail.verify_sent_message.assert_called_once_with(
        "message-1",
        execution.idempotency_key,
    )
    assert result.result["verification"]["verified"] is True
    with pytest.raises(ApprovalResolutionError, match="already resolved"):
        manager.approve_for_execution(approval_id, proposal_id=proposal.proposal_id)
    mock_gmail.send_message.assert_called_once()


def test_wrong_proposal_id_cannot_consume_approval():
    manager = ToolApprovalManager()
    _, approval_id = request_email(manager)

    with pytest.raises(ApprovalResolutionError) as exc:
        manager.approve_for_execution(approval_id, proposal_id="different-proposal")

    assert exc.value.code == "proposal_mismatch"
    assert manager.get(approval_id).status == ApprovalStatus.PENDING


@patch("app.tools.email_gmail", create=True)
def test_argument_tampering_invalidates_without_calling_provider(mock_gmail):
    manager = ToolApprovalManager()
    proposal, approval_id = request_email(manager)
    approval = manager.get(approval_id)
    assert approval is not None
    approval.args["body"] = "Tampered body"

    with pytest.raises(ApprovalResolutionError) as exc:
        manager.approve_for_execution(approval_id, proposal_id=proposal.proposal_id)

    assert exc.value.code == "arguments_changed"
    assert approval.status == ApprovalStatus.INVALID
    mock_gmail.send_message.assert_not_called()


def test_expired_approval_cannot_be_consumed():
    manager = ToolApprovalManager()
    proposal, approval_id = request_email(manager)
    approval = manager.get(approval_id)
    assert approval is not None
    after_expiry = datetime.fromisoformat(approval.expires_at) + timedelta(seconds=1)

    with pytest.raises(ApprovalResolutionError) as exc:
        manager.approve_for_execution(
            approval_id,
            proposal_id=proposal.proposal_id,
            now=after_expiry.astimezone(timezone.utc),
        )

    assert exc.value.code == "expired"
    assert approval.status == ApprovalStatus.EXPIRED


def test_dispatcher_rejects_forged_argument_change_after_consumption():
    manager = ToolApprovalManager()
    proposal, approval_id = request_email(manager)
    execution = manager.approve_for_execution(
        approval_id,
        proposal_id=proposal.proposal_id,
    )
    forged = execution.model_copy(
        update={"arguments": {**execution.arguments, "body": "Changed after approval"}}
    )

    result = ExecutorAgent().run_approved_tool(forged)

    assert result.status == "blocked"
    assert "does not match" in result.result["error"] or "fingerprint" in result.result["error"]


def test_direct_malformed_write_returns_blocked_instead_of_raising():
    result = ExecutorAgent().run_tool("send_email", {"to": "rain@example.com"})

    assert result.status == "blocked"
    assert "registry validation" in result.result["error"]
    assert "subject" in result.result["details"]


@patch("app.tools.email_gmail", create=True)
def test_provider_success_is_reported_as_error_when_readback_fails(mock_gmail):
    mock_gmail.is_authenticated.return_value = True
    mock_gmail.send_message.return_value = {"id": "message-1"}
    mock_gmail.verify_sent_message.return_value = {
        "verified": False,
        "provider_id": "message-1",
    }
    manager = ToolApprovalManager()
    proposal, approval_id = request_email(manager)
    execution = manager.approve_for_execution(
        approval_id,
        proposal_id=proposal.proposal_id,
    )

    result = ExecutorAgent().run_approved_tool(execution)

    assert result.status == "error"
    assert result.result["verification"]["status"] == "failed"
    assert "could not be verified" in result.result["error"]

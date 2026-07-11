"""Typed tool registry contracts and safety invariants."""

import pytest
from pydantic import ValidationError

from app.api.models import ToolSpec as ApiToolSpec
from app.orchestrator.agents.executor import ExecutorAgent
from app.tools.registry import ToolRegistry, tool_registry
from app.tools.types import (
    ToolCategory,
    ToolExecutionResult,
    ToolOperation,
    ToolProposal,
    ToolRiskLevel,
    ToolSpec,
    ToolVerificationResult,
)


EXPECTED_TOOLS = {
    "calendar_upcoming",
    "create_event",
    "email_summarize_threads",
    "ingest_files",
    "memory_search",
    "open_url",
    "search_files",
    "send_email",
    "show_notification",
    "web_search",
}


def test_default_registry_has_stable_unique_schema_contracts():
    specs = tool_registry.all()

    assert {spec.name for spec in specs} == EXPECTED_TOOLS
    assert [spec.name for spec in specs] == sorted(EXPECTED_TOOLS)
    for spec in specs:
        assert spec.input_schema["type"] == "object"
        assert spec.output_schema["type"] == "object"
        assert spec.description.strip()


def test_every_mutating_tool_requires_approval():
    for spec in tool_registry.all():
        if spec.operation in {ToolOperation.WRITE, ToolOperation.DESTRUCTIVE}:
            assert spec.requires_approval is True, spec.name


def test_local_desktop_and_file_writes_are_explicitly_local_only():
    for name in {"ingest_files", "open_url", "show_notification"}:
        spec = tool_registry.require(name)
        assert spec.local_only is True
        assert spec.requires_approval is True


def test_unsafe_write_spec_is_rejected_at_construction():
    with pytest.raises(ValidationError, match="must require approval"):
        ToolSpec(
            name="unsafe_write",
            description="An invalid write contract.",
            category=ToolCategory.SYSTEM,
            operation=ToolOperation.WRITE,
            risk_level=ToolRiskLevel.HIGH,
            requires_approval=False,
        )


def test_destructive_spec_requires_high_or_critical_risk():
    with pytest.raises(ValidationError, match="high or critical risk"):
        ToolSpec(
            name="delete_something",
            description="An invalid destructive contract.",
            category=ToolCategory.SYSTEM,
            operation=ToolOperation.DESTRUCTIVE,
            risk_level=ToolRiskLevel.MEDIUM,
            requires_approval=True,
        )


def test_registry_rejects_duplicates_and_unknown_names():
    spec = tool_registry.require("memory_search")
    registry = ToolRegistry([spec])

    with pytest.raises(ValueError, match="already registered"):
        registry.register(spec)
    with pytest.raises(KeyError, match="Unknown tool"):
        registry.require("not_registered")


def test_proposal_validation_checks_operation_required_and_unknown_fields():
    proposal = ToolProposal(
        tool_name="send_email",
        operation=ToolOperation.READ,
        arguments={"to": "rain@example.com", "unexpected": True},
    )

    errors = tool_registry.validate_proposal(proposal)

    assert "operation mismatch: expected write, got read" in errors
    assert "missing required fields: subject, body" in errors
    assert "unknown fields: unexpected" in errors


def test_complete_proposal_validates_cleanly():
    proposal = ToolProposal(
        tool_name="create_event",
        operation=ToolOperation.WRITE,
        arguments={
            "summary": "Planning",
            "start_time": "2026-07-11T10:00:00-04:00",
            "duration_minutes": 30,
        },
    )

    assert tool_registry.validate_proposal(proposal) == []


def test_review_execution_and_verification_contracts_are_strict():
    proposal = ToolProposal(
        tool_name="send_email",
        operation=ToolOperation.WRITE,
        arguments={"to": "rain@example.com", "subject": "Hi", "body": "Hello"},
    )
    preview = tool_registry.build_preview(proposal, redact_sensitive=True)
    result = ToolExecutionResult(
        proposal_id=proposal.proposal_id,
        tool_name=proposal.tool_name,
        status="success",
        data={"message_id": "123"},
    )
    verification = ToolVerificationResult(
        tool_name=proposal.tool_name,
        status="verified",
        verified=True,
        details={"message_id": "123"},
    )

    assert preview.sensitive_fields_redacted is True
    assert result.status == "success"
    assert verification.verified is True
    with pytest.raises(ValidationError):
        ToolExecutionResult(
            tool_name="send_email",
            status="success",
            invented_field=True,
        )


def test_api_reexports_canonical_tool_spec_and_parameters_alias():
    assert ApiToolSpec is ToolSpec
    spec = tool_registry.require("memory_search")
    assert spec.parameters is spec.input_schema


def test_keyword_executor_outputs_only_registered_tools(monkeypatch):
    executor = ExecutorAgent()
    monkeypatch.setattr(executor, "_handle_email_read", lambda: [])

    calls = executor.execute_tools(
        'send email to rain@example.com subject "Hi" body "Hello"',
        "session",
    )

    assert calls
    assert all(executor.registry.get(call.tool_name) is not None for call in calls)

"""Typed contracts shared by tool planning, review, execution, and verification."""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Any, Dict, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolCategory(str, Enum):
    EMAIL = "email"
    CALENDAR = "calendar"
    MEMORY = "memory"
    FILES = "files"
    DESKTOP = "desktop"
    WEB = "web"
    SYSTEM = "system"


class ToolOperation(str, Enum):
    READ = "read"
    DRAFT = "draft"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class ToolRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ToolSpec(BaseModel):
    """Stable metadata and JSON-schema contract for one registered tool."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(min_length=1)
    category: ToolCategory
    operation: ToolOperation
    input_schema: Dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    output_schema: Dict[str, Any] = Field(default_factory=lambda: {"type": "object"})
    risk_level: ToolRiskLevel = ToolRiskLevel.LOW
    requires_approval: bool = False
    local_only: bool = False
    sensitive_fields: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_safety_contract(self) -> "ToolSpec":
        if self.input_schema.get("type") != "object":
            raise ValueError("tool input_schema must describe an object")
        if self.output_schema.get("type") != "object":
            raise ValueError("tool output_schema must describe an object")
        if self.operation in {ToolOperation.WRITE, ToolOperation.DESTRUCTIVE}:
            if not self.requires_approval:
                raise ValueError("write and destructive tools must require approval")
        if self.operation == ToolOperation.DESTRUCTIVE and self.risk_level not in {
            ToolRiskLevel.HIGH,
            ToolRiskLevel.CRITICAL,
        }:
            raise ValueError("destructive tools must be high or critical risk")
        return self

    @property
    def parameters(self) -> Dict[str, Any]:
        """Compatibility alias for the original prototype contract."""
        return self.input_schema


class ToolProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str = Field(default_factory=lambda: str(uuid4()))
    tool_name: str
    operation: ToolOperation
    arguments: Dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    status: Literal["proposed", "needs_input"] = "proposed"
    missing_fields: list[str] = Field(default_factory=list)
    idempotency_key: str | None = None


class ToolPreview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_id: str
    tool_name: str
    operation: ToolOperation
    summary: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    sensitive_fields_redacted: bool = False
    arguments_sha256: str


class ApprovedToolExecution(BaseModel):
    """One-use execution capability emitted only by the approval manager."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    approval_id: str
    proposal_id: str
    tool_name: str
    operation: ToolOperation
    arguments: Dict[str, Any]
    arguments_sha256: str
    idempotency_key: str


class ToolVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    status: Literal["verified", "failed", "not_supported"]
    verified: bool = False
    details: Dict[str, Any] = Field(default_factory=dict)
    error: str = ""


class ToolExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    proposal_id: str | None = None
    approval_id: str | None = None
    status: Literal["success", "blocked", "error"]
    data: Any = None
    error: str = ""
    verification: ToolVerificationResult | None = None


class ToolResult(BaseModel):
    """Backward-compatible result used by existing direct tool functions."""

    ok: bool
    data: Any = None
    error: str = ""


def fingerprint_tool_arguments(
    *,
    proposal_id: str,
    tool_name: str,
    operation: ToolOperation | str,
    arguments: Dict[str, Any],
) -> str:
    """Stable digest binding a proposal to its exact operation and arguments."""
    operation_value = operation.value if isinstance(operation, ToolOperation) else str(operation)
    payload = json.dumps(
        {
            "proposal_id": proposal_id,
            "tool_name": tool_name,
            "operation": operation_value,
            "arguments": arguments,
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

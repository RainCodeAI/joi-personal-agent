"""Canonical registry of Joi tool capabilities and safety contracts."""

from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime
from urllib.parse import urlparse
from typing import Any
from uuid import uuid4

from app.tools.types import (
    ToolCategory,
    ToolOperation,
    ToolProposal,
    ToolRiskLevel,
    ToolSpec,
    ToolPreview,
    fingerprint_tool_arguments,
)


class ToolRegistry:
    def __init__(self, specs: Iterable[ToolSpec] = ()) -> None:
        self._specs: dict[str, ToolSpec] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._specs:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._specs[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def require(self, name: str) -> ToolSpec:
        spec = self.get(name)
        if spec is None:
            raise KeyError(f"Unknown tool: {name}")
        return spec

    def all(self) -> tuple[ToolSpec, ...]:
        return tuple(self._specs[name] for name in sorted(self._specs))

    def validate_proposal(self, proposal: ToolProposal) -> list[str]:
        """Validate planner output against registered operation and input schema."""
        spec = self.get(proposal.tool_name)
        if spec is None:
            return [f"unknown tool: {proposal.tool_name}"]

        errors: list[str] = []
        if proposal.operation != spec.operation:
            errors.append(
                f"operation mismatch: expected {spec.operation.value}, got {proposal.operation.value}"
            )

        required = spec.input_schema.get("required", [])
        if isinstance(required, list):
            missing = [
                str(field)
                for field in required
                if not _has_value(proposal.arguments.get(str(field)))
            ]
            if missing:
                errors.append(f"missing required fields: {', '.join(missing)}")

        if spec.input_schema.get("additionalProperties") is False:
            properties = spec.input_schema.get("properties", {})
            allowed = set(properties) if isinstance(properties, dict) else set()
            unknown = sorted(set(proposal.arguments) - allowed)
            if unknown:
                errors.append(f"unknown fields: {', '.join(unknown)}")
        properties = spec.input_schema.get("properties", {})
        if isinstance(properties, dict):
            for field, value in proposal.arguments.items():
                field_schema = properties.get(field)
                if isinstance(field_schema, dict):
                    errors.extend(_validate_value(field, value, field_schema))
        return errors

    def create_proposal(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        rationale: str = "",
        proposal_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> ToolProposal:
        spec = self.require(tool_name)
        resolved_proposal_id = proposal_id or str(uuid4())
        proposal = ToolProposal(
            proposal_id=resolved_proposal_id,
            tool_name=tool_name,
            operation=spec.operation,
            arguments=deepcopy(arguments),
            rationale=rationale,
            idempotency_key=(
                idempotency_key or resolved_proposal_id
                if spec.requires_approval
                else None
            ),
        )
        errors = self.validate_proposal(proposal)
        if errors:
            raise ValueError("; ".join(errors))
        return proposal

    def build_preview(
        self,
        proposal: ToolProposal,
        *,
        redact_sensitive: bool,
    ) -> ToolPreview:
        spec = self.require(proposal.tool_name)
        arguments = deepcopy(proposal.arguments)
        if redact_sensitive:
            for field in spec.sensitive_fields:
                if field in arguments:
                    arguments[field] = "[redacted]"
        return ToolPreview(
            proposal_id=proposal.proposal_id,
            tool_name=proposal.tool_name,
            operation=proposal.operation,
            summary=_preview_summary(proposal),
            arguments=arguments,
            sensitive_fields_redacted=redact_sensitive,
            arguments_sha256=fingerprint_tool_arguments(
                proposal_id=proposal.proposal_id,
                tool_name=proposal.tool_name,
                operation=proposal.operation,
                arguments=proposal.arguments,
            ),
        )


def _has_value(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _validate_value(field: str, value: Any, schema: dict[str, Any]) -> list[str]:
    expected = schema.get("type")
    valid_type = True
    if expected == "string":
        valid_type = isinstance(value, str)
    elif expected == "integer":
        valid_type = isinstance(value, int) and not isinstance(value, bool)
    elif expected == "boolean":
        valid_type = isinstance(value, bool)
    elif expected == "object":
        valid_type = isinstance(value, dict)
    elif expected == "array":
        valid_type = isinstance(value, list)
    if not valid_type:
        return [f"invalid type for {field}: expected {expected}"]
    errors: list[str] = []
    if isinstance(value, str):
        if len(value) < int(schema.get("minLength", 0)):
            errors.append(f"{field} is too short")
        if "maxLength" in schema and len(value) > int(schema["maxLength"]):
            errors.append(f"{field} is too long")
        if schema.get("format") == "email" and (
            "@" not in value or value.startswith("@") or value.endswith("@")
        ):
            errors.append(f"{field} is not a valid email address")
        if schema.get("format") == "uri":
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append(f"{field} is not an HTTP(S) URL")
        if schema.get("format") == "date-time":
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"{field} is not a valid ISO date-time")
    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < int(schema["minimum"]):
            errors.append(f"{field} is below minimum")
        if "maximum" in schema and value > int(schema["maximum"]):
            errors.append(f"{field} is above maximum")
    return errors


def _preview_summary(proposal: ToolProposal) -> str:
    args = proposal.arguments
    if proposal.tool_name == "send_email":
        return f"Send email to {args.get('to')} with subject {args.get('subject')!r}."
    if proposal.tool_name == "create_event":
        return f"Create calendar event {args.get('summary')!r} at {args.get('start_time')}."
    return f"Run {proposal.tool_name} with the displayed arguments."


def _object_schema(
    properties: dict[str, Any],
    *,
    required: tuple[str, ...] = (),
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = list(required)
    return schema


def build_default_registry() -> ToolRegistry:
    specs = [
        ToolSpec(
            name="email_summarize_threads",
            description="Read and summarize recent Gmail threads.",
            category=ToolCategory.EMAIL,
            operation=ToolOperation.READ,
            input_schema=_object_schema(
                {"max_results": {"type": "integer", "minimum": 1, "maximum": 20}}
            ),
            output_schema=_object_schema({"summary": {"type": "string"}}),
        ),
        ToolSpec(
            name="send_email",
            description="Send an email with an explicit recipient, subject, and body.",
            category=ToolCategory.EMAIL,
            operation=ToolOperation.WRITE,
            input_schema=_object_schema(
                {
                    "to": {"type": "string", "format": "email"},
                    "subject": {"type": "string", "minLength": 1},
                    "body": {"type": "string", "minLength": 1},
                },
                required=("to", "subject", "body"),
            ),
            output_schema=_object_schema(
                {"status": {"type": "string"}, "details": {"type": "object"}}
            ),
            risk_level=ToolRiskLevel.HIGH,
            requires_approval=True,
            local_only=True,
            sensitive_fields=("to", "body"),
        ),
        ToolSpec(
            name="calendar_upcoming",
            description="Read upcoming Google Calendar events.",
            category=ToolCategory.CALENDAR,
            operation=ToolOperation.READ,
            input_schema=_object_schema(
                {"days": {"type": "integer", "minimum": 1, "maximum": 31}}
            ),
            output_schema=_object_schema({"events": {"type": "array"}}),
        ),
        ToolSpec(
            name="create_event",
            description="Create a calendar event from explicit title and time fields.",
            category=ToolCategory.CALENDAR,
            operation=ToolOperation.WRITE,
            input_schema=_object_schema(
                {
                    "summary": {"type": "string", "minLength": 1},
                    "start_time": {"type": "string", "format": "date-time"},
                    "duration_minutes": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1440,
                    },
                },
                required=("summary", "start_time"),
            ),
            output_schema=_object_schema(
                {"status": {"type": "string"}, "link": {"type": ["string", "null"]}}
            ),
            risk_level=ToolRiskLevel.HIGH,
            requires_approval=True,
            local_only=True,
        ),
        ToolSpec(
            name="memory_search",
            description="Search Joi's memory for relevant stored context.",
            category=ToolCategory.MEMORY,
            operation=ToolOperation.READ,
            input_schema=_object_schema(
                {
                    "query": {"type": "string", "minLength": 1},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                required=("query",),
            ),
            output_schema=_object_schema({"items": {"type": "array"}}),
            sensitive_fields=("query",),
        ),
        ToolSpec(
            name="search_files",
            description="Search indexed files under configured local roots.",
            category=ToolCategory.FILES,
            operation=ToolOperation.READ,
            input_schema=_object_schema(
                {
                    "query": {"type": "string", "minLength": 1},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                required=("query",),
            ),
            output_schema=_object_schema({"items": {"type": "array"}}),
            risk_level=ToolRiskLevel.MEDIUM,
            local_only=True,
            sensitive_fields=("query",),
        ),
        ToolSpec(
            name="ingest_files",
            description="Index text files from an explicitly allowed local path.",
            category=ToolCategory.FILES,
            operation=ToolOperation.WRITE,
            input_schema=_object_schema(
                {"path": {"type": "string", "minLength": 1}}, required=("path",)
            ),
            output_schema=_object_schema({"ingested": {"type": "integer"}}),
            risk_level=ToolRiskLevel.MEDIUM,
            requires_approval=True,
            local_only=True,
            sensitive_fields=("path",),
        ),
        ToolSpec(
            name="open_url",
            description="Open an explicit HTTP or HTTPS URL on the local desktop.",
            category=ToolCategory.DESKTOP,
            operation=ToolOperation.WRITE,
            input_schema=_object_schema(
                {"url": {"type": "string", "format": "uri"}}, required=("url",)
            ),
            output_schema=_object_schema(
                {"opened": {"type": "boolean"}, "summary": {"type": "string"}}
            ),
            risk_level=ToolRiskLevel.MEDIUM,
            requires_approval=True,
            local_only=True,
            sensitive_fields=("url",),
        ),
        ToolSpec(
            name="show_notification",
            description="Show a bounded native notification on the local desktop.",
            category=ToolCategory.DESKTOP,
            operation=ToolOperation.WRITE,
            input_schema=_object_schema(
                {
                    "title": {"type": "string", "maxLength": 120},
                    "message": {"type": "string", "minLength": 1, "maxLength": 500},
                },
                required=("message",),
            ),
            output_schema=_object_schema({"summary": {"type": "string"}}),
            risk_level=ToolRiskLevel.MEDIUM,
            requires_approval=True,
            local_only=True,
            sensitive_fields=("message",),
        ),
        ToolSpec(
            name="web_search",
            description="Search the web when network search is explicitly available.",
            category=ToolCategory.WEB,
            operation=ToolOperation.READ,
            input_schema=_object_schema(
                {"query": {"type": "string", "minLength": 1}}, required=("query",)
            ),
            output_schema=_object_schema({"items": {"type": "array"}}),
            risk_level=ToolRiskLevel.MEDIUM,
            sensitive_fields=("query",),
        ),
    ]
    return ToolRegistry(specs)


tool_registry = build_default_registry()

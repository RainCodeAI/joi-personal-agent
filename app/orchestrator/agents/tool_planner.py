"""Constrained LLM planner that can only emit registry-valid tool proposals."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from app.tools.registry import ToolRegistry, tool_registry
from app.tools.types import ToolProposal
from services.ai_router import route_request

RouteFn = Callable[[str, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolPlan:
    proposals: list[ToolProposal] = field(default_factory=list)
    valid: bool = True
    error: str = ""


class LLMToolPlanner:
    _INTENT = re.compile(
        r"\b(email|mail|calendar|meeting|event|schedule|memory|remember|file|"
        r"folder|web|search|url|website|notification|notify)\b",
        re.IGNORECASE,
    )

    def __init__(
        self,
        registry: ToolRegistry | None = None,
        route_fn: RouteFn = route_request,
    ) -> None:
        self.registry = registry or tool_registry
        self.route_fn = route_fn

    def is_candidate(self, user_message: str) -> bool:
        return bool(self._INTENT.search(user_message))

    def plan(self, user_message: str) -> ToolPlan:
        try:
            routed = self.route_fn(self._prompt(user_message), {"task": "tool_planning"})
            if routed.get("model_used") == "none":
                return ToolPlan(valid=False, error="tool planning provider failed")
            payload = self._parse_json(str(routed.get("response") or ""))
            return self._validate_payload(payload)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return ToolPlan(valid=False, error=str(exc))

    def _prompt(self, user_message: str) -> str:
        tools = [
            {
                "name": spec.name,
                "description": spec.description,
                "operation": spec.operation.value,
                "input_schema": spec.input_schema,
            }
            for spec in self.registry.all()
        ]
        return (
            "You are Joi's tool planner. Return JSON only, with exactly this shape: "
            '{"proposals":[{"tool_name":"name","arguments":{},"rationale":"reason"}]}. '
            "Use only listed tools and only information explicitly supplied by the user. "
            "Do not guess missing values; omit them. Return an empty proposals list when no "
            "tool is appropriate. Tools: "
            + json.dumps(tools, separators=(",", ":"))
            + "\nUser request: "
            + user_message
        )

    @staticmethod
    def _parse_json(text: str) -> Any:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.I)
        return json.loads(stripped)

    def _validate_payload(self, payload: Any) -> ToolPlan:
        if not isinstance(payload, dict) or set(payload) != {"proposals"}:
            raise ValueError("planner output must contain only proposals")
        items = payload["proposals"]
        if not isinstance(items, list):
            raise ValueError("proposals must be a list")
        proposals: list[ToolProposal] = []
        for item in items:
            if not isinstance(item, dict) or not set(item) <= {
                "tool_name", "arguments", "rationale"
            } or not {"tool_name", "arguments"} <= set(item):
                raise ValueError("proposal has missing or unknown fields")
            tool_name = item["tool_name"]
            arguments = item["arguments"]
            if not isinstance(tool_name, str) or not isinstance(arguments, dict):
                raise ValueError("proposal tool_name/arguments have invalid types")
            spec = self.registry.get(tool_name)
            if spec is None:
                raise ValueError(f"unknown tool: {tool_name}")
            rationale = item.get("rationale", "")
            if not isinstance(rationale, str):
                raise ValueError("proposal rationale must be a string")
            required = spec.input_schema.get("required", [])
            missing = [
                str(name) for name in required
                if not arguments.get(str(name))
            ]
            if missing:
                proposal = ToolProposal(
                    tool_name=tool_name,
                    operation=spec.operation,
                    arguments=arguments,
                    rationale=rationale,
                    status="needs_input",
                    missing_fields=missing,
                )
                validation = [
                    error for error in self.registry.validate_proposal(proposal)
                    if not error.startswith("missing required fields:")
                ]
                if validation:
                    raise ValueError("; ".join(validation))
                proposals.append(proposal)
                continue
            proposals.append(
                self.registry.create_proposal(tool_name, arguments, rationale=rationale)
            )
        return ToolPlan(proposals=proposals)

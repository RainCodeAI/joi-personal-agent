"""ExecutorAgent — Tool dispatch (email, calendar, file ops, web search).

Routes tool invocations based on user intent, enforces policy checks,
and returns structured ToolCall results.
"""

from __future__ import annotations

import re
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.api.models import ToolCall

from app.api.models import ToolCall as ToolCallModel
from app.tools.dispatcher import ToolDispatcher
from app.tools.registry import ToolRegistry, tool_registry
from app.tools.types import ApprovedToolExecution, ToolExecutionResult, ToolProposal


class ExecutorAgent:
    """Dispatches tool calls based on user message keywords and policy rules."""

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        # Keyword detection remains the deterministic fallback. The canonical
        # registry is now available for the later typed-planner migration.
        self.registry = registry or tool_registry
        self.dispatcher = ToolDispatcher(self.registry)

    # ── public API ────────────────────────────────────────────────────────

    def execute_tools(
        self, user_msg: str, session_id: str
    ) -> List[ToolCallModel]:
        """Detect tool intents in the message and execute allowed tools.

        Returns a list of ToolCall results (possibly empty).
        """
        tool_calls: List[ToolCallModel] = []
        lower = user_msg.lower()

        # Read-only tools (safe context)
        if "check email" in lower or "read email" in lower:
            tool_calls.extend(self._handle_email_read())
        elif "check calendar" in lower or "what's on my calendar" in lower:
            tool_calls.extend(self._handle_calendar_read())
            
        # Write tools are proposals only. Never invent recipients, content, titles,
        # or dates just to make a request look executable. Complete proposals are
        # returned with status="pending" so the API layer queues them for explicit
        # user approval (see ToolApprovalManager); they are never executed here.
        if "send email" in lower:
            args = self._extract_email_args(user_msg)
            missing = [field for field in ("to", "subject", "body") if not args.get(field)]
            if missing:
                tool_calls.append(
                    ToolCallModel(
                        tool_name="send_email",
                        args=args,
                        status="needs_input",
                        result={
                            "error": "Email details are incomplete.",
                            "missing_fields": missing,
                        },
                    )
                )
            else:
                tool_calls.append(
                    ToolCallModel(
                        tool_name="send_email",
                        args=args,
                        status="pending",
                        result={"status": "Awaiting user approval before sending."},
                    )
                )
        if "schedule" in lower and "meeting" in lower:
            args = self._extract_event_args(user_msg)
            missing = [field for field in ("summary", "start_time") if not args.get(field)]
            if missing:
                tool_calls.append(
                    ToolCallModel(
                        tool_name="create_event",
                        args=args,
                        status="needs_input",
                        result={
                            "error": "Calendar event details are incomplete.",
                            "missing_fields": missing,
                        },
                    )
                )
            else:
                tool_calls.append(
                    ToolCallModel(
                        tool_name="create_event",
                        args=args,
                        status="pending",
                        result={"status": "Awaiting user approval before creating the event."},
                    )
                )

        return tool_calls

    @staticmethod
    def _extract_email_args(user_msg: str) -> dict:
        """Extract explicit email fields; only quoted subject/body count as provided."""
        args: dict = {}
        recipients = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", user_msg)
        if recipients:
            args["to"] = recipients[0]
        subject = re.search(r'subject\s*[:\-]?\s*"([^"]+)"', user_msg, re.IGNORECASE)
        if subject:
            args["subject"] = subject.group(1).strip()
        body = re.search(r'(?:saying|body|message)\s*[:\-]?\s*"([^"]+)"', user_msg, re.IGNORECASE)
        if body:
            args["body"] = body.group(1).strip()
        return args

    @staticmethod
    def _extract_event_args(user_msg: str) -> dict:
        """Extract explicit event fields; requires a quoted title and an ISO-style time."""
        args: dict = {}
        summary = re.search(r'"([^"]+)"', user_msg)
        if summary:
            args["summary"] = summary.group(1).strip()
        start = re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?", user_msg)
        if start:
            args["start_time"] = start.group(0).replace(" ", "T")
        return args

    def run_tool(self, tool_name: str, args: dict) -> ToolCallModel:
        """Execute read tools; mutating tools are blocked without a consumed approval."""
        spec = self.registry.get(tool_name)
        if spec is None:
            return ToolCallModel(
                tool_name=tool_name,
                args=args,
                result={"error": f"Unknown tool: {tool_name}"},
                status="error",
            )
        try:
            proposal = self.registry.create_proposal(tool_name, args)
        except ValueError as exc:
            return ToolCallModel(
                tool_name=tool_name,
                args=args,
                result={
                    "error": "Tool arguments failed registry validation",
                    "details": str(exc),
                },
                status="blocked",
            )
        return self._legacy_tool_call(
            proposal.arguments,
            self.dispatcher.execute(proposal),
        )

    def execute_proposals(self, proposals: list[ToolProposal]) -> List[ToolCallModel]:
        """Execute validated reads and surface writes as exact approval proposals."""
        calls: List[ToolCallModel] = []
        for proposal in proposals:
            common = {
                "tool_name": proposal.tool_name,
                "args": proposal.arguments,
                "proposal_id": proposal.proposal_id,
                "operation": proposal.operation.value,
                "idempotency_key": proposal.idempotency_key,
            }
            if proposal.status == "needs_input":
                calls.append(ToolCallModel(
                    **common,
                    status="needs_input",
                    result={
                        "error": "Tool details are incomplete.",
                        "missing_fields": proposal.missing_fields,
                    },
                ))
                continue
            spec = self.registry.require(proposal.tool_name)
            if spec.requires_approval:
                calls.append(ToolCallModel(
                    **common,
                    status="pending",
                    result={"status": "Awaiting user approval."},
                ))
                continue
            execution = self.dispatcher.execute(proposal)
            call = self._legacy_tool_call(proposal.arguments, execution)
            calls.append(call.model_copy(update={
                "proposal_id": proposal.proposal_id,
                "operation": proposal.operation.value,
                "idempotency_key": proposal.idempotency_key,
            }))
        return calls

    def run_approved_tool(self, approval: ApprovedToolExecution) -> ToolCallModel:
        try:
            proposal = self.registry.create_proposal(
                approval.tool_name,
                approval.arguments,
            ).model_copy(
                update={
                    "proposal_id": approval.proposal_id,
                    "idempotency_key": approval.idempotency_key,
                }
            )
        except (KeyError, ValueError) as exc:
            return ToolCallModel(
                tool_name=approval.tool_name,
                args=approval.arguments,
                result={
                    "error": "Approved arguments failed registry validation",
                    "details": str(exc),
                },
                status="blocked",
            )
        result = self.dispatcher.execute(proposal, approval=approval)
        return self._legacy_tool_call(proposal.arguments, result)

    @staticmethod
    def _legacy_tool_call(
        args: dict,
        execution: ToolExecutionResult,
    ) -> ToolCallModel:
        payload = dict(execution.data) if isinstance(execution.data, dict) else {}
        if execution.error:
            payload["error"] = execution.error
        if execution.verification is not None:
            payload["verification"] = execution.verification.model_dump(mode="json")
        return ToolCallModel(
            tool_name=execution.tool_name,
            args=args,
            result=payload,
            status=execution.status,
        )

    # ── private helpers ───────────────────────────────────────────────────

    def _handle_email_read(self) -> List[ToolCallModel]:
        return [self.run_tool("email_summarize_threads", {})]

    def _handle_calendar_read(self) -> List[ToolCallModel]:
        return [self.run_tool("calendar_upcoming", {"days": 1})]

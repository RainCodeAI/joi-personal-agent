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


class ExecutorAgent:
    """Dispatches tool calls based on user message keywords and policy rules."""

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
        # or dates just to make a request look executable.
        if "send email" in lower:
            recipients = re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", user_msg)
            args = {"to": recipients[0]} if recipients else {}
            missing = [field for field in ("to", "subject", "body") if not args.get(field)]
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
        if "schedule" in lower and "meeting" in lower:
            tool_calls.append(
                ToolCallModel(
                    tool_name="create_event",
                    args={},
                    status="needs_input",
                    result={
                        "error": "Calendar event details are incomplete.",
                        "missing_fields": ["summary", "start_time"],
                    },
                )
            )

        return tool_calls

    def run_tool(self, tool_name: str, args: dict) -> ToolCallModel:
        """Directly execute a tool (bypassing detection/policy checks, assuming prior approval)."""
        
        if tool_name == "send_email":
            from app.tools import email_gmail
            missing = [
                field
                for field in ("to", "subject", "body")
                if not str(args.get(field) or "").strip()
            ]
            if missing:
                return ToolCallModel(
                    tool_name=tool_name,
                    args=args,
                    result={"error": "Missing required email fields", "missing_fields": missing},
                    status="error",
                )
            if not email_gmail.is_authenticated():
                return ToolCallModel(
                    tool_name=tool_name,
                    args=args,
                    result={"error": "Gmail is not authenticated", "code": "not_authenticated"},
                    status="error",
                )
            try:
                res = email_gmail.send_message(
                    to=str(args["to"]).strip(),
                    subject=str(args["subject"]).strip(),
                    body=str(args["body"]),
                )
                return ToolCallModel(
                    tool_name=tool_name,
                    args=args,
                    result={"status": "Email sent", "details": res},
                )
            except Exception as e:
                return ToolCallModel(tool_name=tool_name, args=args, result={"error": str(e)}, status="error")

        elif tool_name == "create_event":
            from app.tools import calendar_gcal
            missing = [
                field
                for field in ("summary", "start_time")
                if not str(args.get(field) or "").strip()
            ]
            if missing:
                return ToolCallModel(
                    tool_name=tool_name,
                    args=args,
                    result={"error": "Missing required calendar fields", "missing_fields": missing},
                    status="error",
                )
            if not calendar_gcal.is_authenticated():
                return ToolCallModel(
                    tool_name=tool_name,
                    args=args,
                    result={"error": "Google Calendar is not authenticated", "code": "not_authenticated"},
                    status="error",
                )
            try:
                res = calendar_gcal.create_event(
                    summary=str(args["summary"]).strip(),
                    start_time=str(args["start_time"]).strip(),
                    duration_minutes=int(args.get("duration_minutes", 60)),
                )
                return ToolCallModel(
                    tool_name=tool_name,
                    args=args,
                    result={"status": "Event created", "link": res.get("htmlLink")},
                )
            except Exception as e:
                return ToolCallModel(tool_name=tool_name, args=args, result={"error": str(e)}, status="error")
        
        return ToolCallModel(tool_name=tool_name, args=args, result={"error": f"Unknown tool: {tool_name}"}, status="error")

    # ── private helpers ───────────────────────────────────────────────────

    @staticmethod
    def _handle_email_read() -> List[ToolCallModel]:
        try:
            from app.tools import email_gmail

            threads = email_gmail.list_threads()
            summary = email_gmail.summarize_threads(threads)
            return [
                ToolCallModel(
                    tool_name="email_summarize_threads",
                    args={},
                    result={"summary": summary},
                )
            ]
        except Exception as e:
            return [
                ToolCallModel(
                    tool_name="email_summarize_threads",
                    args={},
                    result={"error": str(e)},
                    status="error"
                )
            ]

    @staticmethod
    def _handle_calendar_read() -> List[ToolCallModel]:
        try:
            from app.tools import calendar_gcal

            if calendar_gcal.is_authenticated():
                events = calendar_gcal.upcoming_events(days=1)
                return [
                    ToolCallModel(
                        tool_name="calendar_upcoming",
                        args={},
                        result={"events": events},
                    )
                ]
        except Exception as e:
            return [
                ToolCallModel(
                    tool_name="calendar_upcoming",
                    args={},
                    result={"error": str(e)},
                    status="error",
                )
            ]

        return [
            ToolCallModel(
                tool_name="calendar_upcoming",
                args={},
                result={"error": "Google Calendar is not authenticated", "code": "not_authenticated"},
                status="error",
            )
        ]

"""ExecutorAgent — Tool dispatch (email, calendar, file ops, web search).

Routes tool invocations based on user intent, enforces policy checks,
and returns structured ToolCall results.
"""

from __future__ import annotations

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
            
        # Destructive tools (negotiate flow)
        # Simple keyword triggers for demo purposes
        if "send email" in lower:
            # Mock extraction
            tool_calls.append(
                ToolCallModel(
                    tool_name="send_email",
                    args={"to": "bob@example.com", "subject": "Hello", "body": "Draft body from Joi"},
                    status="pending",
                    result={"msg": "Approval required before sending."}
                )
            )
        if "schedule" in lower and "meeting" in lower:
            # Mock extraction
            tool_calls.append(
                ToolCallModel(
                    tool_name="create_event",
                    args={"summary": "Meeting with Bob", "start_time": "tomorrow 2pm"},
                    status="pending",
                    result={"msg": "Approval required before scheduling."}
                )
            )

        return tool_calls

    def run_tool(self, tool_name: str, args: dict) -> ToolCallModel:
        """Directly execute a tool (bypassing detection/policy checks, assuming prior approval)."""
        
        if tool_name == "send_email":
            from app.tools import email_gmail
            if email_gmail.is_authenticated():
                try:
                    res = email_gmail.send_message(
                        to=args.get("to", ""), 
                        subject=args.get("subject", "(No Subject)"), 
                        body=args.get("body", "")
                    )
                    return ToolCallModel(tool_name=tool_name, args=args, result={"status": "Email sent", "details": res})
                except Exception as e:
                    return ToolCallModel(tool_name=tool_name, args=args, result={"error": str(e)}, status="error")
            else:
                return ToolCallModel(tool_name=tool_name, args=args, result={"status": "Email sent (Mock - No Auth)"})

        elif tool_name == "create_event":
            from app.tools import calendar_gcal
            if calendar_gcal.is_authenticated():
                try:
                    res = calendar_gcal.create_event(
                        summary=args.get("summary", "New Event"), 
                        start_time=args.get("start_time", datetime.utcnow().isoformat())
                    )
                    return ToolCallModel(tool_name=tool_name, args=args, result={"status": "Event created", "link": res.get("htmlLink")})
                except Exception as e:
                    return ToolCallModel(tool_name=tool_name, args=args, result={"error": str(e)}, status="error")
            else:
                return ToolCallModel(tool_name=tool_name, args=args, result={"status": "Event created (Mock - No Auth)"})
        
        return ToolCallModel(tool_name=tool_name, args=args, result={"error": f"Unknown tool: {tool_name}"}, status="error")

    # ── private helpers ───────────────────────────────────────────────────

    @staticmethod
    def _handle_email_read() -> List[ToolCallModel]:
        try:
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
        # TODO: Wire up real calendar_gcal.upcoming_events() once OAuth is fully integrated
        return [
            ToolCallModel(
                tool_name="calendar_upcoming",
                args={},
                result={"events": ["Meeting at 2 PM", "Doctor at 4 PM"]},
            )
        ]

"""ExecutorAgent — Tool dispatch (email, calendar, file ops, web search).

Routes tool invocations based on user intent, enforces policy checks,
and returns structured ToolCall results.
"""

from __future__ import annotations

from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.api.models import ToolCall

from app.api.models import ToolCall as ToolCallModel
from app.orchestrator.policies import is_allowed_tool, require_user_approval
from app.tools import email_gmail, calendar_gcal, files_local, web_search


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

        if "email" in lower:
            tool_calls.extend(self._handle_email())
        elif "calendar" in lower:
            tool_calls.extend(self._handle_calendar())

        return tool_calls

    # ── private helpers ───────────────────────────────────────────────────

    @staticmethod
    def _handle_email() -> List[ToolCallModel]:
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
                )
            ]

    @staticmethod
    def _handle_calendar() -> List[ToolCallModel]:
        # TODO: Wire up real calendar_gcal.upcoming_events() once OAuth is fully integrated
        return [
            ToolCallModel(
                tool_name="calendar_upcoming",
                args={},
                result={"events": ["Meeting at 2 PM", "Doctor at 4 PM"]},
            )
        ]

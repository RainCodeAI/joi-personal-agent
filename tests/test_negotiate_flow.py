import os
import sys
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))

from app.orchestrator.agents.executor import ExecutorAgent


class TestNegotiateFlow:
    @patch("app.tools.email_gmail", create=True)
    def test_executor_detects_destructive_intent(self, mock_gmail):
        calls = ExecutorAgent().execute_tools(
            "Please send email to bob@example.com",
            "session_1",
        )

        assert len(calls) == 1
        call = calls[0]
        assert call.tool_name == "send_email"
        assert call.status == "needs_input"
        assert call.args == {"to": "bob@example.com"}
        assert set(call.result["missing_fields"]) == {"subject", "body"}
        mock_gmail.send_message.assert_not_called()

    @patch("app.tools.email_gmail", create=True)
    def test_executor_allows_read_intent(self, mock_gmail):
        mock_gmail.list_threads.return_value = []
        mock_gmail.summarize_threads.return_value = "No emails"

        calls = ExecutorAgent().execute_tools("check email", "session_1")

        assert calls[0].tool_name == "email_summarize_threads"
        assert calls[0].result["summary"] == "No emails"
        mock_gmail.list_threads.assert_called()

    @patch("app.tools.email_gmail", create=True)
    def test_run_tool_blocks_write_without_consumed_approval(self, mock_gmail):
        mock_gmail.is_authenticated.return_value = True
        mock_gmail.send_message.return_value = "message_id_123"

        res = ExecutorAgent().run_tool(
            "send_email",
            {"to": "bob@example.com", "subject": "Hello", "body": "hi"},
        )

        assert res.status == "blocked"
        assert "consumed approval" in res.result["error"]
        mock_gmail.send_message.assert_not_called()

    @patch("app.tools.email_gmail", create=True)
    def test_run_tool_never_reports_mock_email_success(self, mock_gmail):
        mock_gmail.is_authenticated.return_value = False

        res = ExecutorAgent().run_tool(
            "send_email",
            {"to": "bob@example.com", "subject": "Hello", "body": "hi"},
        )

        assert res.status == "blocked"
        mock_gmail.send_message.assert_not_called()

    @patch("app.tools.calendar_gcal", create=True)
    def test_calendar_read_never_returns_demo_events(self, mock_calendar):
        mock_calendar.is_authenticated.return_value = False

        calls = ExecutorAgent().execute_tools(
            "what's on my calendar",
            "session_1",
        )

        assert calls[0].status == "error"
        assert calls[0].result["code"] == "not_authenticated"

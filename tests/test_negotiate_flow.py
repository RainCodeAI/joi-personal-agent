
import pytest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from unittest.mock import MagicMock, patch
from app.orchestrator.agents.executor import ExecutorAgent
from app.api.models import ToolCall

class TestNegotiateFlow:
    @patch("app.tools.email_gmail")
    def test_executor_detects_destructive_intent(self, mock_gmail):
        # Setup
        executor = ExecutorAgent()
        
        # Test destructive intent
        calls = executor.execute_tools("Please send email to bob@example.com", "session_1")
        
        assert len(calls) == 1
        call = calls[0]
        assert call.tool_name == "send_email"
        assert call.status == "pending"
        assert "Approval required" in call.result["msg"]
        
        # Ensure underlying tool was NOT called (Executor just returns proposal)
        # Note: execute_tools doesn't import or call email_gmail for destructive tools,
        # it just returns the proposal.
        mock_gmail.send_message.assert_not_called()

    @patch("app.tools.email_gmail")
    def test_executor_allows_read_intent(self, mock_gmail):
        # Setup mocks
        mock_gmail.list_threads.return_value = []
        mock_gmail.summarize_threads.return_value = "No emails"
        
        executor = ExecutorAgent()
        
        # Test read intent
        calls = executor.execute_tools("check email", "session_1")
        
        assert len(calls) >= 1
        call = calls[0]
        assert call.tool_name == "email_summarize_threads"
        # Status defaults to success if not specified, but let's check result
        assert call.result["summary"] == "No emails"
        
        # Ensure underlying tool WAS called
        mock_gmail.list_threads.assert_called()

    @patch("app.tools.email_gmail")
    def test_run_tool_executes_directly(self, mock_gmail):
        # Setup mock to simulate auth
        mock_gmail.is_authenticated.return_value = True
        mock_gmail.send_message.return_value = "message_id_123"

        executor = ExecutorAgent()
        
        # Test direct execution (post-approval)
        res = executor.run_tool("send_email", {"to": "bob", "body": "hi"})
        
        assert res.tool_name == "send_email"
        assert res.status == "success" # Status set by run_tool on success
        assert res.result["details"] == "message_id_123"
        
        # Verify it called the real tool logic (which is mocked here)
        mock_gmail.send_message.assert_called_with(to="bob", subject="(No Subject)", body="hi")

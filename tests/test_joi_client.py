"""Contract tests for the Telegram bridge's local Joi API client."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.integrations.joi_client import JoiApiError, JoiClient


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


def test_pending_approvals_scopes_and_encodes_session_id():
    client = JoiClient("http://127.0.0.1:8000", "token")
    client._request = AsyncMock(return_value=FakeResponse({"approvals": [{"id": "one"}]}))

    approvals = asyncio.run(client.pending_approvals("telegram:111/thread"))

    assert approvals == [{"id": "one"}]
    client._request.assert_awaited_once_with(
        "GET", "/api/v2/approvals?session_id=telegram%3A111%2Fthread"
    )


def test_recent_messages_preserves_backend_failure_for_user_facing_handler():
    client = JoiClient("http://127.0.0.1:8000", "token")
    client._request = AsyncMock(side_effect=JoiApiError("backend unavailable"))

    with pytest.raises(JoiApiError, match="backend unavailable"):
        asyncio.run(client.recent_messages("telegram:111"))

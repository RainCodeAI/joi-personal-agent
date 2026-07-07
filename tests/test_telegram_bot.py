"""Tests for the Telegram bridge — authorization, routing, and approval safety.

No real bot token or network is used; the Joi client and Telegram Update objects
are faked. Handlers are async, run via asyncio.run to avoid a plugin dependency.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.integrations import telegram_bot as tb
from app.integrations.joi_client import JoiApiError


class FakeMessage:
    def __init__(self, text=""):
        self.text = text
        self.reply_text = AsyncMock()


class FakeUser:
    def __init__(self, user_id):
        self.id = user_id


class FakeUpdate:
    def __init__(self, user_id, text=""):
        self.effective_user = FakeUser(user_id)
        self.effective_message = FakeMessage(text)


def _fake_client(**overrides):
    client = AsyncMock()
    client.health = AsyncMock(return_value=overrides.get("health", True))
    client.ensure_session = AsyncMock()
    client.chat = AsyncMock(return_value=overrides.get("chat", {
        "assistant_message": {"content": "Hey, I hear you."},
        "pending_approvals": [],
    }))
    client.recent_messages = AsyncMock(return_value=overrides.get("recent", []))
    return client


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    tb._active_session.clear()
    tb._ensured_sessions.clear()
    monkeypatch.setattr(settings, "telegram_allowed_user_ids", "111")
    yield


# ── pure helpers ────────────────────────────────────────────────────────────

def test_summarize_approvals_empty():
    assert tb.summarize_approvals([]) == ""


def test_summarize_approvals_dedups_and_counts():
    out = tb.summarize_approvals([
        {"tool_name": "send_email"}, {"tool_name": "send_email"}, {"tool_name": "create_event"},
    ])
    assert "3 action(s)" in out
    assert "send_email" in out and "create_event" in out
    assert out.count("send_email") == 1  # deduped


def test_redact_sensitive_args():
    red = tb._redact_args({"to": "a@b.com", "subject": "hi", "body": "secret text"})
    assert red["to"] == "[redacted]"
    assert red["body"] == "[redacted]"
    assert red["subject"] == "hi"


def test_session_mapping_is_deterministic_per_user():
    assert tb._session_for(111) == "telegram:111"
    assert tb._session_for(111) == "telegram:111"  # stable


# ── authorization ───────────────────────────────────────────────────────────

def test_unauthorized_user_is_rejected_and_not_routed(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(tb, "_client", lambda: client)
    update = FakeUpdate(user_id=999, text="hello Joi")  # not in allowlist "111"

    asyncio.run(tb.on_text(update, None))

    client.chat.assert_not_called()
    update.effective_message.reply_text.assert_awaited_once()
    assert "private" in update.effective_message.reply_text.await_args.args[0].lower()


def test_allowed_user_message_routes_to_chat(monkeypatch):
    client = _fake_client()
    monkeypatch.setattr(tb, "_client", lambda: client)
    update = FakeUpdate(user_id=111, text="how are you?")

    asyncio.run(tb.on_text(update, None))

    client.ensure_session.assert_awaited_once_with("telegram:111")
    client.chat.assert_awaited_once_with("telegram:111", "how are you?")
    reply = update.effective_message.reply_text.await_args.args[0]
    assert "Hey, I hear you." in reply


# ── failure + approval safety ───────────────────────────────────────────────

def test_backend_unavailable_fails_cleanly(monkeypatch):
    client = _fake_client()
    client.chat = AsyncMock(side_effect=JoiApiError("down"))
    monkeypatch.setattr(tb, "_client", lambda: client)
    update = FakeUpdate(user_id=111, text="hi")

    asyncio.run(tb.on_text(update, None))

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "reach my backend" in reply.lower()


def test_pending_approval_is_reported_not_executed(monkeypatch):
    client = _fake_client(chat={
        "assistant_message": {"content": "I drafted that email."},
        "pending_approvals": [{"tool_name": "send_email", "args": {"to": "x@y.com", "body": "hi"}}],
    })
    monkeypatch.setattr(tb, "_client", lambda: client)
    update = FakeUpdate(user_id=111, text="email bob")

    asyncio.run(tb.on_text(update, None))

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "approval on the laptop" in reply
    # The bridge never approves/executes remotely — only chat + ensure_session run.
    assert not any(
        name in ("approve", "approve_action", "run_tool")
        for name in dir(client) if getattr(getattr(client, name, None), "await_count", 0)
    )


def test_status_reports_backend_health(monkeypatch):
    client = _fake_client(health=False)
    monkeypatch.setattr(tb, "_client", lambda: client)
    update = FakeUpdate(user_id=111, text="/status")

    asyncio.run(tb.cmd_status(update, None))

    reply = update.effective_message.reply_text.await_args.args[0]
    assert "offline" in reply.lower()


def test_new_rotates_session(monkeypatch):
    update = FakeUpdate(user_id=111, text="/new")
    asyncio.run(tb.cmd_new(update, None))
    assert tb._active_session[111] != "telegram:111"
    assert tb._active_session[111].startswith("telegram:111:")

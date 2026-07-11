"""Provider-level idempotency markers and read-back verification."""

import base64
from unittest.mock import MagicMock

from app.tools import calendar_gcal, email_gmail


def gmail_service():
    service = MagicMock()
    messages = service.users.return_value.messages.return_value
    return service, messages


def test_gmail_uses_stable_message_id_and_verifies_readback(monkeypatch):
    service, messages = gmail_service()
    messages.list.return_value.execute.return_value = {"messages": []}
    messages.send.return_value.execute.return_value = {"id": "gmail-1"}
    expected_header = email_gmail._idempotency_message_id("proposal-1")
    messages.get.return_value.execute.return_value = {
        "id": "gmail-1",
        "payload": {"headers": [{"name": "Message-ID", "value": expected_header}]},
    }
    monkeypatch.setattr(email_gmail, "get_credentials", lambda: object())
    monkeypatch.setattr(email_gmail, "build", lambda *args, **kwargs: service)

    sent = email_gmail.send_message(
        "rain@example.com",
        "Hello",
        "Body",
        idempotency_key="proposal-1",
    )
    raw = messages.send.call_args.kwargs["body"]["raw"]
    decoded = base64.urlsafe_b64decode(raw.encode()).decode()
    verified = email_gmail.verify_sent_message("gmail-1", "proposal-1")

    assert sent["id"] == "gmail-1"
    assert f"Message-ID: {expected_header}" in decoded
    assert verified["verified"] is True


def test_gmail_reuses_existing_message_before_send(monkeypatch):
    service, messages = gmail_service()
    messages.list.return_value.execute.return_value = {"messages": [{"id": "existing"}]}
    monkeypatch.setattr(email_gmail, "get_credentials", lambda: object())
    monkeypatch.setattr(email_gmail, "build", lambda *args, **kwargs: service)

    result = email_gmail.send_message(
        "rain@example.com",
        "Hello",
        "Body",
        idempotency_key="proposal-1",
    )

    assert result == {"id": "existing", "idempotent_replay": True}
    messages.send.assert_not_called()


def calendar_service():
    service = MagicMock()
    events = service.events.return_value
    return service, events


def test_calendar_uses_private_key_and_verifies_readback(monkeypatch):
    service, events = calendar_service()
    events.list.return_value.execute.return_value = {"items": []}
    events.insert.return_value.execute.return_value = {
        "id": "event-1",
        "htmlLink": "https://calendar/event-1",
    }
    events.get.return_value.execute.return_value = {
        "id": "event-1",
        "extendedProperties": {
            "private": {"joi_idempotency_key": "proposal-1"}
        },
    }
    monkeypatch.setattr(calendar_gcal, "get_credentials", lambda: object())
    monkeypatch.setattr(calendar_gcal, "build", lambda *args, **kwargs: service)

    created = calendar_gcal.create_event(
        "Planning",
        "2026-07-11T10:00:00-04:00",
        idempotency_key="proposal-1",
    )
    inserted = events.insert.call_args.kwargs["body"]
    verified = calendar_gcal.verify_created_event("event-1", "proposal-1")

    assert created["id"] == "event-1"
    assert inserted["extendedProperties"]["private"]["joi_idempotency_key"] == "proposal-1"
    assert verified["verified"] is True


def test_calendar_reuses_existing_event_before_insert(monkeypatch):
    service, events = calendar_service()
    events.list.return_value.execute.return_value = {"items": [{"id": "existing"}]}
    monkeypatch.setattr(calendar_gcal, "get_credentials", lambda: object())
    monkeypatch.setattr(calendar_gcal, "build", lambda *args, **kwargs: service)

    result = calendar_gcal.create_event(
        "Planning",
        "2026-07-11T10:00:00-04:00",
        idempotency_key="proposal-1",
    )

    assert result == {"id": "existing", "idempotent_replay": True}
    events.insert.assert_not_called()

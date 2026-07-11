"""Tests for proactive Telegram delivery: outbox store, policy, and bridge core."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.initiative.policy import InitiativeCandidate
from app.integrations import telegram_bot as tb
from app.integrations.joi_client import JoiApiError
from app.integrations.outbox import TelegramOutbox, initiative_is_deliverable


def _candidate(initiative_type="daily_greeting", message="Morning."):
    return InitiativeCandidate(
        type=initiative_type,
        priority="low",
        reason="test",
        session_id="default",
        message=message,
    )


# ── store ────────────────────────────────────────────────────────────────────


def test_enqueue_then_claim_then_ack(tmp_path):
    outbox = TelegramOutbox(tmp_path / "outbox.json")
    record = outbox.enqueue(text="Hey there.", kind="initiative:daily_greeting")
    assert record is not None

    claimed = outbox.claim()
    assert [m["text"] for m in claimed] == ["Hey there."]
    assert outbox.pending_count() == 1  # still pending until acked

    acked = outbox.ack([claimed[0]["id"]])
    assert acked == 1
    assert outbox.pending_count() == 0
    assert outbox.claim() == []


def test_enqueue_dedups_pending_by_key(tmp_path):
    outbox = TelegramOutbox(tmp_path / "outbox.json")
    first = outbox.enqueue(text="a", kind="k", dedup_key="daily:default:2026-07-11")
    dup = outbox.enqueue(text="b", kind="k", dedup_key="daily:default:2026-07-11")
    assert first is not None
    assert dup is None
    assert outbox.pending_count() == 1


def test_ack_frees_dedup_key(tmp_path):
    outbox = TelegramOutbox(tmp_path / "outbox.json")
    first = outbox.enqueue(text="a", kind="k", dedup_key="daily:default:2026-07-11")
    outbox.ack([first["id"]])
    # Once delivered, the same key may be queued again (a new day/emission).
    again = outbox.enqueue(text="c", kind="k", dedup_key="daily:default:2026-07-11")
    assert again is not None


def test_claim_skips_expired(tmp_path):
    outbox = TelegramOutbox(tmp_path / "outbox.json")
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    outbox.enqueue(text="stale", kind="k", expires_at=past)
    assert outbox.claim() == []
    assert outbox.pending_count() == 0


def test_blank_text_is_not_queued(tmp_path):
    outbox = TelegramOutbox(tmp_path / "outbox.json")
    assert outbox.enqueue(text="   ", kind="k") is None
    assert outbox.pending_count() == 0


def test_outbox_persists_across_instances(tmp_path):
    path = tmp_path / "outbox.json"
    TelegramOutbox(path).enqueue(text="remembered", kind="k")
    reopened = TelegramOutbox(path)
    assert reopened.pending_count() == 1


# ── delivery policy ──────────────────────────────────────────────────────────


def test_not_deliverable_when_proactive_disabled(monkeypatch):
    monkeypatch.setattr(settings, "telegram_proactive_enabled", False)
    assert initiative_is_deliverable(_candidate("daily_greeting")) is False


def test_deliverable_only_for_allowed_types(monkeypatch):
    monkeypatch.setattr(settings, "telegram_proactive_enabled", True)
    monkeypatch.setattr(settings, "telegram_proactive_types", "daily_greeting")
    assert initiative_is_deliverable(_candidate("daily_greeting")) is True
    assert initiative_is_deliverable(_candidate("memory_followup")) is False


# ── bridge delivery core ─────────────────────────────────────────────────────


def test_deliver_outbox_once_sends_and_acks():
    client = AsyncMock()
    client.claim_outbox = AsyncMock(return_value=[{"id": "m1", "text": "hi", "kind": "k"}])
    client.ack_outbox = AsyncMock(return_value=1)
    send = AsyncMock()

    delivered = asyncio.run(tb.deliver_outbox_once(client, send, [111]))

    assert delivered == 1
    send.assert_awaited_once_with(111, "hi")
    client.ack_outbox.assert_awaited_once_with(["m1"])


def test_deliver_outbox_once_does_not_ack_on_send_failure():
    client = AsyncMock()
    client.claim_outbox = AsyncMock(return_value=[{"id": "m1", "text": "hi", "kind": "k"}])
    client.ack_outbox = AsyncMock()
    send = AsyncMock(side_effect=RuntimeError("telegram down"))

    delivered = asyncio.run(tb.deliver_outbox_once(client, send, [111]))

    assert delivered == 0
    client.ack_outbox.assert_not_awaited()  # message stays queued for retry


def test_deliver_outbox_once_no_recipients_is_noop():
    client = AsyncMock()
    client.claim_outbox = AsyncMock()
    send = AsyncMock()

    delivered = asyncio.run(tb.deliver_outbox_once(client, send, []))

    assert delivered == 0
    client.claim_outbox.assert_not_awaited()


def test_deliver_outbox_once_survives_claim_failure():
    client = AsyncMock()
    client.claim_outbox = AsyncMock(side_effect=JoiApiError("backend down"))
    send = AsyncMock()

    delivered = asyncio.run(tb.deliver_outbox_once(client, send, [111]))

    assert delivered == 0
    send.assert_not_awaited()


# ── emit hook (InitiativeService._deliver_remote) ────────────────────────────


def _service_with_outbox(tmp_path):
    from unittest.mock import MagicMock

    from app.initiative.service import InitiativeService
    from app.initiative.store import InitiativeStore

    outbox = MagicMock()
    outbox.enqueue = MagicMock(return_value={"id": "x"})
    service = InitiativeService(store=InitiativeStore(tmp_path / "init.json"), outbox=outbox)
    return service, outbox


def test_emit_enqueues_eligible_initiative(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "telegram_proactive_enabled", True)
    monkeypatch.setattr(settings, "telegram_proactive_types", "daily_greeting")
    service, outbox = _service_with_outbox(tmp_path)

    service._deliver_remote(_candidate("daily_greeting", "Morning."), datetime.now(timezone.utc))

    outbox.enqueue.assert_called_once()
    kwargs = outbox.enqueue.call_args.kwargs
    assert kwargs["text"] == "Morning."
    assert kwargs["kind"] == "initiative:daily_greeting"


def test_emit_skips_ineligible_type(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "telegram_proactive_enabled", True)
    monkeypatch.setattr(settings, "telegram_proactive_types", "daily_greeting")
    service, outbox = _service_with_outbox(tmp_path)

    service._deliver_remote(_candidate("memory_followup", "Earlier..."), datetime.now(timezone.utc))

    outbox.enqueue.assert_not_called()


def test_deliver_remote_without_outbox_is_noop(tmp_path):
    from app.initiative.service import InitiativeService
    from app.initiative.store import InitiativeStore

    service = InitiativeService(store=InitiativeStore(tmp_path / "init.json"))
    # Must not raise when no outbox is configured.
    service._deliver_remote(_candidate(), datetime.now(timezone.utc))


# ── HTTP endpoints ───────────────────────────────────────────────────────────


def test_outbox_claim_and_ack_endpoints(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api import v2 as api_v2
    from app.api.main import app

    outbox = TelegramOutbox(tmp_path / "endpoint_outbox.json")
    record = outbox.enqueue(text="proactive line", kind="initiative:daily_greeting")
    monkeypatch.setattr(api_v2, "telegram_outbox", outbox)

    client = TestClient(app)

    claimed = client.post("/api/v2/telegram/outbox/claim", json={"limit": 5})
    assert claimed.status_code == 200
    messages = claimed.json()["messages"]
    assert [m["text"] for m in messages] == ["proactive line"]

    acked = client.post("/api/v2/telegram/outbox/ack", json={"ids": [record["id"]]})
    assert acked.status_code == 200
    assert acked.json()["acknowledged"] == 1

    # Nothing left to claim after ack.
    again = client.post("/api/v2/telegram/outbox/claim", json={"limit": 5})
    assert again.json()["messages"] == []

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.main import app
from app.api.models import ChatResponse
from app.api.realtime import RealtimeEventBus, format_sse_event
from app.api import v2 as api_v2
from app.orchestrator.security.approval import ApprovalStatus, PendingApproval


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_v2_create_session(monkeypatch):
    fake_session = SimpleNamespace(
        id="session-123",
        user_id="default",
        title="New chat",
        created_at=datetime(2026, 1, 1, 10, 0, 0),
        updated_at=datetime(2026, 1, 1, 10, 0, 0),
    )
    monkeypatch.setattr(api_v2.memory_store, "create_session", lambda *args, **kwargs: fake_session)

    response = client.post("/api/v2/sessions", json={"session_id": "session-123", "title": "New chat"})

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v2"
    assert body["session"]["id"] == "session-123"
    assert body["session"]["title"] == "New chat"


def test_v2_get_messages(monkeypatch):
    fake_session = SimpleNamespace(
        id="session-abc",
        user_id="default",
        title="Thread",
        created_at=datetime(2026, 1, 2, 8, 0, 0),
        updated_at=datetime(2026, 1, 2, 9, 0, 0),
    )
    fake_messages = [
        SimpleNamespace(id=1, session_id="session-abc", role="user", content="hi", timestamp=datetime(2026, 1, 2, 8, 0, 0)),
        SimpleNamespace(id=2, session_id="session-abc", role="assistant", content="hello", timestamp=datetime(2026, 1, 2, 8, 1, 0)),
    ]
    monkeypatch.setattr(api_v2.memory_store, "get_session", lambda session_id: fake_session)
    monkeypatch.setattr(api_v2.memory_store, "get_chat_history", lambda session_id: fake_messages)

    response = client.get("/api/v2/sessions/session-abc/messages")

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v2"
    assert len(body["messages"]) == 2
    assert body["messages"][1]["content"] == "hello"


def test_v2_chat_contract(monkeypatch):
    fake_session = SimpleNamespace(
        id="session-chat",
        user_id="default",
        title="Session chat",
        created_at=datetime(2026, 1, 3, 12, 0, 0),
        updated_at=datetime(2026, 1, 3, 12, 1, 0),
    )
    persisted_messages = [
        SimpleNamespace(id=10, session_id="session-chat", role="user", content="send email to bob", timestamp=datetime(2026, 1, 3, 12, 0, 0)),
        SimpleNamespace(id=11, session_id="session-chat", role="assistant", content="I can do that once you approve it.", timestamp=datetime(2026, 1, 3, 12, 0, 1)),
    ]

    def fake_history(session_id):
        return persisted_messages if fake_history.calls else []

    fake_history.calls = 0

    def history_wrapper(session_id):
        result = fake_history(session_id)
        fake_history.calls += 1
        return result

    monkeypatch.setattr(api_v2.memory_store, "get_chat_history", history_wrapper)
    monkeypatch.setattr(api_v2.memory_store, "get_session", lambda session_id: fake_session)
    monkeypatch.setattr(
        api_v2.agent,
        "reply",
        lambda history, text, session_id: ChatResponse(
            text="I can do that once you approve it.",
            session_id=session_id,
            tool_calls=[
                {
                    "tool_name": "send_email",
                    "args": {"to": "bob@example.com"},
                    "result": {"msg": "Approval required before sending."},
                    "status": "pending",
                }
            ],
            craving_score=72.0,
            is_dramatic_return=True,
            provider="ollama",
            route=["gguf", "ollama"],
            errors=[{"provider": "gguf", "error": "not configured"}],
            user_message_id=10,
            assistant_message_id=11,
            assistant_timestamp="2026-01-03T12:00:01",
        ),
    )

    pending = PendingApproval(
        id="approval-1",
        session_id="session-chat",
        tool_name="send_email",
        args={"to": "bob@example.com"},
        status=ApprovalStatus.PENDING,
        created_at="2026-01-03T12:00:01",
    )
    monkeypatch.setattr(api_v2.approval_manager, "request_approval", lambda *args, **kwargs: "approval-1")
    monkeypatch.setattr(api_v2.approval_manager, "get", lambda approval_id: pending)
    published_events = []

    async def fake_publish(event, payload, session_id=None, source="system"):
        envelope = {
            "api_version": "v2",
            "event_id": f"evt-{len(published_events)+1}",
            "event": event,
            "source": source,
            "session_id": session_id,
            "timestamp": "2026-01-03T12:00:01",
            "payload": payload,
        }
        published_events.append(envelope)
        return envelope

    monkeypatch.setattr(api_v2.event_bus, "publish", fake_publish)

    class FakeCravingEngine:
        def __init__(self, store):
            self.store = store

        def get_craving_expression(self, session_id):
            return "clingy"

    monkeypatch.setattr(api_v2, "CravingEngine", FakeCravingEngine)

    response = client.post("/api/v2/chat", json={"session_id": "session-chat", "text": "send email to bob"})

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v2"
    assert body["session"]["id"] == "session-chat"
    assert body["assistant_message"]["id"] == 11
    assert body["provider"]["selected"] == "ollama"
    assert body["avatar"]["expression"] == "clingy"
    assert body["avatar"]["voice_hint"] == "whisper"
    assert body["pending_approvals"][0]["tool_name"] == "send_email"
    assert [event["event"] for event in published_events] == [
        "message.received",
        "response.started",
        "approval.requested",
        "message.created",
        "message.completed",
        "avatar.state",
    ]


def test_v2_approve_action(monkeypatch):
    approved = PendingApproval(
        id="approval-2",
        session_id="session-chat",
        tool_name="send_email",
        args={"to": "bob@example.com"},
        status=ApprovalStatus.APPROVED,
        created_at="2026-01-03T12:00:01",
        resolved_at="2026-01-03T12:00:05",
    )
    monkeypatch.setattr(api_v2.approval_manager, "approve", lambda approval_id: approved)
    monkeypatch.setattr(
        api_v2.agent,
        "run_tool",
        lambda tool_name, args: {
            "tool_name": tool_name,
            "args": args,
            "result": {"status": "Email sent"},
            "status": "success",
        },
    )

    response = client.post("/api/v2/approvals/approval-2/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["approval"]["status"] == "approved"
    assert body["tool_result"]["result"]["status"] == "Email sent"


def test_v2_settings_patch(monkeypatch):
    class FakeRuntimeSettings:
        def __init__(self):
            self.values = {
                "airgap": False,
                "autonomy_level": "medium",
                "enable_proactive_messaging": True,
                "model_chat": "gpt-4o-mini",
                "model_embed": "nomic-embed-text",
                "router_timeout": 30,
                "gguf_n_ctx": 2048,
                "gguf_n_gpu_layers": 0,
            }

        def get(self):
            return dict(self.values)

        def update(self, patch):
            self.values.update(patch)
            return dict(self.values)

    fake_runtime = FakeRuntimeSettings()
    monkeypatch.setattr(api_v2, "runtime_settings", fake_runtime)

    response = client.patch("/api/v2/settings", json={"autonomy_level": "high", "router_timeout": 45})

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v2"
    assert body["settings"]["autonomy_level"] == "high"
    assert body["settings"]["router_timeout"] == 45


def test_v2_recent_events(monkeypatch):
    async def fake_recent(*, session_id=None, limit=20):
        return [
            {
                "api_version": "v2",
                "event_id": "evt-1",
                "event": "message.completed",
                "source": "chat",
                "session_id": session_id,
                "timestamp": "2026-01-03T12:00:01",
                "payload": {"text": "hello"},
            }
        ]

    monkeypatch.setattr(api_v2.event_bus, "get_recent", fake_recent)

    response = client.get("/api/v2/events", params={"session_id": "session-chat", "limit": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v2"
    assert body["events"][0]["event"] == "message.completed"
    assert body["events"][0]["payload"]["text"] == "hello"


def test_realtime_event_bus_and_sse_format():
    async def scenario():
        bus = RealtimeEventBus()
        subscriber_id, queue = await bus.subscribe(session_id="stream-session")
        try:
            envelope = await bus.publish(
                "message.completed",
                {"marker": "stream-test"},
                session_id="stream-session",
                source="chat",
            )
            received = await asyncio.wait_for(queue.get(), timeout=1.0)
            return envelope, received
        finally:
            await bus.unsubscribe(subscriber_id)

    envelope, received = asyncio.run(scenario())
    assert received["event"] == "message.completed"
    assert received["payload"]["marker"] == "stream-test"

    formatted = format_sse_event(envelope)
    assert "event: message.completed" in formatted
    payload_line = next(line for line in formatted.splitlines() if line.startswith("data: "))
    payload = json.loads(payload_line.split("data: ", 1)[1])
    assert payload["payload"]["marker"] == "stream-test"

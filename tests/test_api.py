import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import main as api_main
from app.api.main import app
from app.api.models import ChatResponse
from app.api.realtime import RealtimeEventBus, format_sse_event
from app.api import v2 as api_v2
from app.api.v2_models import ChatAttachmentResource
from app.api import diagnostics as diagnostics_api
from app.hardware.bridge import HardwareBridgeStore
from app.hardware import mqtt_bridge as mqtt_bridge_module
from app.orchestrator.security.approval import ApprovalStatus, PendingApproval


client = TestClient(app)


def test_health(monkeypatch):
    monkeypatch.setattr(api_main, "db_engine", object())
    monkeypatch.setattr(
        api_main.diagnostics_api,
        "build_runtime_diagnostics",
        lambda: {
            "status": "ok",
            "providers": {
                "ollama": {"available": True},
                "openai": {"available": False},
            },
            "storage": {
                "available": True,
                "database_mode": "sqlite",
                "vector_mode": "sql_only",
            },
            "media": {
                "tts": {"openai": True, "local_engine": False, "elevenlabs_sdk": False},
                "stt": {"google_local_stack": True, "whisper_local": False},
            },
            "realtime": {
                "available": True,
                "transport": "sse",
                "subscriber_count": 2,
            },
            "hardware_bridge": {
                "enabled": False,
                "available": False,
                "note": "disabled until ambient hardware Phase 8 begins",
            },
            "readiness": {
                "providers": {"state": "ready", "summary": "provider route available"},
                "storage": {"state": "ready", "summary": "sqlite / sql_only"},
                "media": {"state": "ready", "summary": "tts and stt ready"},
                "realtime": {"state": "ready", "summary": "sse transport"},
                "hardware_bridge": {
                    "state": "disabled",
                    "summary": "disabled until ambient hardware Phase 8 begins",
                },
            },
        },
    )

    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"]["available"] is True
    assert body["storage"]["database_mode"] == "sqlite"
    assert body["media"]["tts_available"] is True
    assert body["media"]["stt_available"] is True
    assert body["realtime"]["transport"] == "sse"
    assert body["hardware_bridge"]["enabled"] is False
    assert body["readiness"]["hardware_bridge"]["state"] == "disabled"


def test_runtime_diagnostics(monkeypatch):
    monkeypatch.setattr(
        diagnostics_api,
        "_provider_diagnostics",
        lambda: {
            "ollama": {"configured": True, "available": True, "host": "http://127.0.0.1:11434"},
            "openai": {"configured": False, "available": False, "sdk_available": True},
        },
    )
    monkeypatch.setattr(
        diagnostics_api,
        "_storage_diagnostics",
        lambda: {
            "airgap": False,
            "available": True,
            "database_mode": "sqlite",
            "database_target": "./data/joi_v1.db",
            "vector_mode": "sql_only",
            "session_store": "sqlalchemy",
        },
    )
    monkeypatch.setattr(
        diagnostics_api,
        "_media_diagnostics",
        lambda: {
            "tts": {"openai": True, "elevenlabs_sdk": False, "elevenlabs_configured": False, "local_engine": True},
            "stt": {"google_local_stack": True, "whisper_local": True, "microphone_stack": True},
            "vision": {"captioning_stack": True, "torch": True},
        },
    )
    monkeypatch.setattr(
        diagnostics_api,
        "_realtime_diagnostics",
        lambda: {
            "available": True,
            "transport": "sse",
            "bus": "in_process",
            "subscriber_count": 1,
            "recent_event_buffer": 20,
            "tracked_media_sessions": 0,
        },
    )
    monkeypatch.setattr(
        diagnostics_api,
        "_hardware_bridge_diagnostics",
        lambda: {
            "enabled": False,
            "available": False,
            "transport": "mqtt",
            "feature_flag": "off",
            "note": "disabled until ambient hardware Phase 8 begins",
        },
    )

    response = client.get("/diagnostics/runtime")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["readiness"]["media"]["state"] == "ready"
    assert body["providers"]["ollama"]["available"] is True
    assert body["storage"]["vector_mode"] == "sql_only"
    assert body["media"]["tts"]["openai"] is True
    assert body["realtime"]["transport"] == "sse"
    assert body["hardware_bridge"]["enabled"] is False


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
        lambda history, text, session_id, on_token=None, attachment_contexts=None: ChatResponse(
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
        "joi.state.changed",
        "approval.requested",
        "message.created",
        "message.completed",
        "joi.state.changed",
        "avatar.state",
    ]


def test_v2_chat_with_attachments_and_deltas(monkeypatch):
    fake_session = SimpleNamespace(
        id="session-chat",
        user_id="default",
        title="Session chat",
        created_at=datetime(2026, 1, 3, 12, 0, 0),
        updated_at=datetime(2026, 1, 3, 12, 1, 0),
    )
    persisted_messages = [
        SimpleNamespace(
            id=20,
            session_id="session-chat",
            role="user",
            content="[Attachments]\n- Image attachment 'scene.png' described as: a city skyline",
            timestamp=datetime(2026, 1, 3, 12, 0, 0),
        ),
        SimpleNamespace(
            id=21,
            session_id="session-chat",
            role="assistant",
            content="I see the skyline. It feels cinematic.",
            timestamp=datetime(2026, 1, 3, 12, 0, 1),
        ),
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
    streamed_chunks = []
    captured = {}

    def fake_reply(history, text, session_id, on_token=None, attachment_contexts=None):
        captured["text"] = text
        captured["attachment_contexts"] = attachment_contexts
        if on_token is not None:
            on_token("I see the ")
            streamed_chunks.append("I see the ")
            on_token("skyline.")
            streamed_chunks.append("skyline.")
        return ChatResponse(
            text="I see the skyline. It feels cinematic.",
            session_id=session_id,
            tool_calls=[],
            craving_score=40.0,
            is_dramatic_return=False,
            provider="ollama",
            route=["ollama"],
            errors=[],
            user_message_id=20,
            assistant_message_id=21,
            assistant_timestamp="2026-01-03T12:00:01",
        )

    monkeypatch.setattr(
        api_v2.agent,
        "reply",
        fake_reply,
    )

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
    monkeypatch.setattr(
        api_v2,
        "_attachment_context",
        lambda attachment: (
            ChatAttachmentResource(
                id="att-1",
                kind="image",
                name=attachment.name,
                media_type=attachment.media_type,
                size_bytes=128,
                preview_text="a city skyline",
            ),
            "Image attachment 'scene.png' described as: a city skyline",
        ),
    )

    class FakeCravingEngine:
        def __init__(self, store):
            self.store = store

        def get_craving_expression(self, session_id):
            return "neutral"

    monkeypatch.setattr(api_v2, "CravingEngine", FakeCravingEngine)

    response = client.post(
        "/api/v2/chat",
        json={
            "session_id": "session-chat",
            "text": "",
            "attachments": [
                {
                    "id": "draft-1",
                    "kind": "image",
                    "name": "scene.png",
                    "media_type": "image/png",
                    "data_url": "data:image/png;base64,ZmFrZQ==",
                    "size_bytes": 128,
                }
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["attachments"][0]["name"] == "scene.png"
    assert body["user_message"]["content"] == "Shared attachment: scene.png"
    assert captured["text"] == "Shared attachment: scene.png"
    assert captured["attachment_contexts"] == ["Image attachment 'scene.png' described as: a city skyline"]
    assert streamed_chunks == ["I see the ", "skyline."]
    assert [event["event"] for event in published_events] == [
        "message.received",
        "response.started",
        "joi.state.changed",
        "message.delta",
        "message.delta",
        "message.created",
        "message.completed",
        "joi.state.changed",
        "avatar.state",
    ]
    assert published_events[3]["payload"]["content"] == "I see the "
    assert published_events[4]["payload"]["content"] == "I see the skyline."
    assert published_events[0]["payload"]["attachments"][0]["name"] == "scene.png"


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


def test_v2_media_session_contract(monkeypatch):
    class FakeMediaSessions:
        def __init__(self):
            self.state = {
                "session_id": "session-chat",
                "mic_state": "idle",
                "speaking_state": "idle",
                "capture_source": "browser",
                "last_transcript": "",
                "recognition_latency_ms": None,
                "playback_latency_ms": None,
                "interruption_count": 0,
                "last_error": None,
                "updated_at": "2026-01-03T12:00:01",
            }

        def get(self, session_id):
            return dict(self.state, session_id=session_id)

        def update(self, session_id, **patch):
            self.state.update({"session_id": session_id, **patch, "updated_at": "2026-01-03T12:00:02"})
            return dict(self.state)

    published_events = []

    async def fake_publish(event, payload, session_id=None, source="system"):
        published_events.append((event, payload, session_id, source))
        return {
            "api_version": "v2",
            "event_id": "evt-media-1",
            "event": event,
            "source": source,
            "session_id": session_id,
            "timestamp": "2026-01-03T12:00:02",
            "payload": payload,
        }

    class FakeHardwareBridge:
        def __init__(self):
            self.calls = []

        def sync_from_media_session(self, session_id, state):
            self.calls.append((session_id, dict(state)))
            return (
                {
                    "state": "listening",
                    "led_state": "attentive_pulse",
                    "session_id": session_id,
                },
                True,
            )

    monkeypatch.setattr(api_v2, "media_sessions", FakeMediaSessions())
    fake_bridge = FakeHardwareBridge()
    monkeypatch.setattr(api_v2, "hardware_bridge", fake_bridge)
    monkeypatch.setattr(api_v2.event_bus, "publish", fake_publish)

    response = client.patch(
        "/api/v2/media/session",
        json={
            "session_id": "session-chat",
            "mic_state": "recording",
            "speaking_state": "interrupted",
            "interrupted": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["media_session"]["mic_state"] == "recording"
    assert body["media_session"]["speaking_state"] == "interrupted"
    assert body["media_session"]["interruption_count"] == 1
    assert published_events[0][0] == "joi.state.changed"
    assert published_events[1][0] == "media.session.updated"
    assert fake_bridge.calls[0][0] == "session-chat"
    assert fake_bridge.calls[0][1]["mic_state"] == "recording"


def test_v2_media_transcribe_contract(monkeypatch):
    class FakeMediaSessions:
        def __init__(self):
            self.state = {
                "session_id": "session-chat",
                "mic_state": "idle",
                "speaking_state": "idle",
                "capture_source": "browser",
                "last_transcript": "",
                "recognition_latency_ms": None,
                "playback_latency_ms": None,
                "interruption_count": 0,
                "last_error": None,
                "updated_at": "2026-01-03T12:00:01",
            }

        def get(self, session_id):
            return dict(self.state, session_id=session_id)

        def update(self, session_id, **patch):
            self.state.update({"session_id": session_id, **patch, "updated_at": "2026-01-03T12:00:03"})
            return dict(self.state)

    published_events = []

    async def fake_publish(event, payload, session_id=None, source="system"):
        published_events.append(event)
        return {
            "api_version": "v2",
            "event_id": f"evt-{len(published_events)}",
            "event": event,
            "source": source,
            "session_id": session_id,
            "timestamp": "2026-01-03T12:00:03",
            "payload": payload,
        }

    monkeypatch.setattr(api_v2, "media_sessions", FakeMediaSessions())
    monkeypatch.setattr(api_v2, "_transcribe_browser_audio", lambda raw_bytes, media_type: "voice drafted reply")
    monkeypatch.setattr(api_v2.event_bus, "publish", fake_publish)

    response = client.post(
        "/api/v2/media/transcribe",
        json={
            "session_id": "session-chat",
            "media_type": "audio/wav",
            "data_url": "data:audio/wav;base64,ZmFrZQ==",
            "duration_ms": 840,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "voice drafted reply"
    assert body["media_session"]["mic_state"] == "idle"
    assert body["media_session"]["recognition_latency_ms"] is not None
    assert published_events == [
        "joi.state.changed",
        "media.session.updated",
        "joi.state.changed",
        "media.session.updated",
        "media.transcription.completed",
    ]


def test_v2_settings_patch(monkeypatch):
    class FakeRuntimeSettings:
        def __init__(self):
            self.values = {
                "airgap": False,
                "autonomy_level": "medium",
                "enable_proactive_messaging": True,
                "initiative_enabled": True,
                "initiative_daily_limit": 2,
                "initiative_timezone": "America/Toronto",
                "initiative_daily_greeting_start": "07:00",
                "initiative_daily_greeting_end": "11:00",
                "initiative_quiet_hours_start": "22:00",
                "initiative_quiet_hours_end": "08:00",
                "initiative_focus_mode": False,
                "initiative_do_not_disturb": False,
                "initiative_late_night_start": "22:00",
                "initiative_late_night_end": "01:00",
                "initiative_silence_threshold_minutes": 90,
                "initiative_allowed_types": "daily_greeting,return_after_absence,late_night_checkin",
                "enable_hardware_nodes": False,
                "mqtt_broker_host": "127.0.0.1",
                "mqtt_broker_port": 1883,
                "mqtt_client_id": "joi-pc-runtime",
                "mqtt_topic_prefix": "joi",
                "mqtt_node_id": "desk",
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
    apply_calls = []

    class FakeMqttBridge:
        async def apply_runtime_settings(self):
            apply_calls.append("applied")

    monkeypatch.setattr(api_v2, "mqtt_bridge", FakeMqttBridge())

    response = client.patch("/api/v2/settings", json={"autonomy_level": "high", "router_timeout": 45})

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v2"
    assert body["settings"]["autonomy_level"] == "high"
    assert body["settings"]["router_timeout"] == 45
    assert body["settings"]["initiative_daily_limit"] == 2
    assert body["settings"]["mqtt_node_id"] == "desk"
    assert apply_calls == []

    response = client.patch("/api/v2/settings", json={"enable_hardware_nodes": True, "mqtt_node_id": "bedside"})

    assert response.status_code == 200
    body = response.json()
    assert body["settings"]["enable_hardware_nodes"] is True
    assert body["settings"]["mqtt_node_id"] == "bedside"
    assert apply_calls == ["applied"]


def test_v2_return_after_absence_candidate(monkeypatch):
    published_events = []

    class FakeInitiativeService:
        def __init__(self):
            self.away_recorded = False

        def record_absence_started(self, session_id, source):
            self.away_recorded = True
            return {
                "session_id": session_id,
                "source": source,
                "observed_at": "2026-04-25T10:00:00",
            }

        def build_return_after_absence_candidate(self, session_id):
            if not self.away_recorded:
                return None
            return SimpleNamespace(
                type="return_after_absence",
                priority="low",
                reason="user returned after 50 minutes away",
                session_id=session_id,
                message="Welcome back. Want to pick up where we left off?",
                expires_at="2026-04-25T11:20:00",
                to_dict=lambda: {
                    "type": "return_after_absence",
                    "priority": "low",
                    "reason": "user returned after 50 minutes away",
                    "session_id": session_id,
                    "message": "Welcome back. Want to pick up where we left off?",
                    "expires_at": "2026-04-25T11:20:00",
                },
            )

        def can_emit(self, candidate, media_session=None):
            return SimpleNamespace(
                allowed=True,
                to_dict=lambda: {
                    "allowed": True,
                    "candidate": candidate.to_dict(),
                    "suppressed_reason": None,
                },
            )

    class FakeMediaSessions:
        def get(self, session_id):
            return {"mic_state": "idle", "speaking_state": "idle"}

    async def fake_publish(event, payload, session_id=None, source="system"):
        published_events.append((event, payload, session_id, source))

    fake_service = FakeInitiativeService()
    monkeypatch.setattr(api_v2, "initiative_service", fake_service)
    monkeypatch.setattr(api_v2, "media_sessions", FakeMediaSessions())
    monkeypatch.setattr(api_v2.event_bus, "publish", fake_publish)

    response = client.post("/api/v2/initiative/activity", params={"session_id": "default", "state": "away", "source": "test"})
    assert response.status_code == 200
    assert response.json()["state"] == "away"

    response = client.post("/api/v2/initiative/return-after-absence", params={"session_id": "default"})
    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["allowed"] is True
    assert body["decision"]["candidate"]["type"] == "return_after_absence"
    assert published_events[-1][0] == "initiative.candidate"


def test_v2_hardware_contract(monkeypatch):
    class FakeHardwareBridge:
        def get_contract(self):
            return {
                "api_version": "v2",
                "contract_version": "ambient-v1",
                "disabled_by_default": True,
                "state_topic_template": "joi/nodes/{node_id}/cmd/state",
                "config_topic_template": "joi/nodes/{node_id}/cmd/config",
                "telemetry_topics": [
                    "joi/nodes/{node_id}/telemetry/presence",
                    "joi/nodes/{node_id}/status/health",
                ],
                "diagnostics_fields": [
                    "enabled",
                    "available",
                    "connection_state",
                    "node_count",
                ],
                "states": [
                    {
                        "state": "idle",
                        "led_state": "calm_pulse",
                        "intensity": 0.35,
                        "transition_ms": 1200,
                        "note": "Default calm presence",
                    },
                    {
                        "state": "speaking",
                        "led_state": "speaking_pulse",
                        "intensity": 0.65,
                        "transition_ms": 180,
                        "note": "Speech active",
                    },
                ],
                "bridge": {
                    "enabled": False,
                    "available": False,
                    "transport": "mqtt",
                    "feature_flag": "off",
                    "broker_host": "127.0.0.1",
                    "broker_port": 1883,
                    "client_id": "joi-pc-runtime",
                    "topic_prefix": "joi",
                    "connection_state": "disabled",
                    "node_count": 0,
                    "last_heartbeat_at": None,
                    "last_publish_at": None,
                    "last_bridge_error": None,
                    "contract_version": "ambient-v1",
                    "current_command": {
                        "contract_version": "ambient-v1",
                        "state": "idle",
                        "led_state": "calm_pulse",
                        "intensity": 0.35,
                        "transition_ms": 1200,
                        "mood": "neutral",
                        "source_event": "system.boot",
                        "session_id": None,
                        "reason": "ambient bridge initialized in disabled mode",
                        "updated_at": "2026-01-03T12:00:01Z",
                    },
                },
            }

    monkeypatch.setattr(api_v2, "hardware_bridge", FakeHardwareBridge())

    response = client.get("/api/v2/hardware/contract")

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v2"
    assert body["contract_version"] == "ambient-v1"
    assert body["bridge"]["enabled"] is False
    assert body["bridge"]["connection_state"] == "disabled"
    assert body["states"][0]["state"] == "idle"
    assert body["states"][1]["led_state"] == "speaking_pulse"


def test_mqtt_bridge_replays_current_command_on_connect(monkeypatch):
    class FakeStore:
        def __init__(self):
            self.connection_states = []
            self.publish_count = 0

        def set_connection_state(self, state, error=None):
            self.connection_states.append((state, error))

        def get_current_command(self):
            return {
                "contract_version": "ambient-v1",
                "state": "thinking",
                "led_state": "thinking_glow",
                "intensity": 0.45,
                "transition_ms": 700,
                "mood": "neutral",
                "source_event": "response.started",
                "session_id": "session-chat",
                "reason": "assistant response in progress",
                "updated_at": "2026-01-03T12:00:01Z",
            }

        def record_publish(self):
            self.publish_count += 1

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs
            self.publishes = []
            self.subscriptions = []
            self.messages = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def publish(self, topic, payload, retain=False):
            self.publishes.append((topic, json.loads(payload), retain))

        async def subscribe(self, topic):
            self.subscriptions.append(topic)

        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    class FakeAiomqtt:
        last_client = None

        class Will:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        @staticmethod
        def Client(*args, **kwargs):
            client = FakeClient(*args, **kwargs)
            FakeAiomqtt.last_client = client
            return client

    class FakeEventBus:
        async def subscribe(self, session_id=None):
            return "sub-1", asyncio.Queue()

        async def unsubscribe(self, subscriber_id):
            return None

    monkeypatch.setattr(mqtt_bridge_module, "_AIOMQTT_AVAILABLE", True)
    monkeypatch.setattr(mqtt_bridge_module, "aiomqtt", FakeAiomqtt, raising=False)
    monkeypatch.setattr(mqtt_bridge_module.settings, "enable_hardware_nodes", True)
    monkeypatch.setattr(mqtt_bridge_module.settings, "mqtt_broker_host", "127.0.0.1")
    monkeypatch.setattr(mqtt_bridge_module.settings, "mqtt_broker_port", 1883)
    monkeypatch.setattr(mqtt_bridge_module.settings, "mqtt_client_id", "joi-test")
    monkeypatch.setattr(mqtt_bridge_module.settings, "mqtt_topic_prefix", "joi")
    monkeypatch.setattr(mqtt_bridge_module.settings, "mqtt_node_id", "desk")

    bridge = mqtt_bridge_module.MqttBridge(FakeStore(), FakeEventBus())

    async def fake_publish_loop(client, queue, state_topic):
        return None

    bridge._publish_loop = fake_publish_loop  # type: ignore[method-assign]

    asyncio.run(bridge._connect_and_serve())

    published = FakeAiomqtt.last_client.publishes
    assert published[0][0] == "joi/bridge/status"
    assert published[0][1]["status"] == "online"
    assert published[0][2] is True
    assert published[1][0] == "joi/nodes/desk/cmd/state"
    assert published[1][1]["state"] == "thinking"
    assert published[1][2] is True


def test_hardware_contract_includes_node_payload_shapes(monkeypatch):
    monkeypatch.setattr(mqtt_bridge_module.settings, "mqtt_topic_prefix", "joi")
    monkeypatch.setattr(mqtt_bridge_module.settings, "mqtt_node_id", "desk")

    contract = HardwareBridgeStore().get_contract()
    payloads = {payload["payload_type"]: payload for payload in contract["node_payloads"]}

    assert "joi/nodes/{node_id}/telemetry/heartbeat" in contract["telemetry_topics"]
    assert payloads["telemetry.heartbeat"]["topic_template"] == "joi/nodes/{node_id}/telemetry/heartbeat"
    assert payloads["telemetry.heartbeat"]["required_fields"] == [
        "contract_version",
        "node_id",
        "status",
        "uptime_ms",
        "sequence",
        "published_at",
    ]
    assert payloads["status.health"]["topic_template"] == "joi/nodes/{node_id}/status/health"
    assert payloads["status.health"]["example"]["status"] == "ok"
    assert payloads["telemetry.presence"]["topic_template"] == "joi/nodes/{node_id}/telemetry/presence"
    assert payloads["telemetry.presence"]["example"]["event"] == "user_returned"


def test_mqtt_bridge_apply_runtime_settings_starts_when_enabled(monkeypatch):
    class FakeStore:
        def __init__(self):
            self.connection_states = []

        def set_connection_state(self, state, error=None):
            self.connection_states.append((state, error))

    class FakeEventBus:
        pass

    bridge = mqtt_bridge_module.MqttBridge(FakeStore(), FakeEventBus())
    calls = []

    async def fake_start():
        calls.append("start")

    monkeypatch.setattr(mqtt_bridge_module, "_AIOMQTT_AVAILABLE", True)
    monkeypatch.setattr(mqtt_bridge_module.settings, "enable_hardware_nodes", True)
    monkeypatch.setattr(bridge, "start", fake_start)

    asyncio.run(bridge.apply_runtime_settings())

    assert calls == ["start"]


def test_mqtt_bridge_apply_runtime_settings_restarts_when_node_id_changes(monkeypatch):
    class FakeStore:
        def set_connection_state(self, state, error=None):
            return None

    class FakeEventBus:
        pass

    class RunningTask:
        def done(self):
            return False

    bridge = mqtt_bridge_module.MqttBridge(FakeStore(), FakeEventBus())
    bridge._task = RunningTask()  # type: ignore[assignment]

    monkeypatch.setattr(mqtt_bridge_module, "_AIOMQTT_AVAILABLE", True)
    monkeypatch.setattr(mqtt_bridge_module.settings, "enable_hardware_nodes", True)
    monkeypatch.setattr(mqtt_bridge_module.settings, "mqtt_broker_host", "127.0.0.1")
    monkeypatch.setattr(mqtt_bridge_module.settings, "mqtt_broker_port", 1883)
    monkeypatch.setattr(mqtt_bridge_module.settings, "mqtt_client_id", "joi-test")
    monkeypatch.setattr(mqtt_bridge_module.settings, "mqtt_topic_prefix", "joi")
    bridge._config_signature = (
        True,
        "127.0.0.1",
        1883,
        "joi-test",
        "joi",
        "desk",
    )
    monkeypatch.setattr(mqtt_bridge_module.settings, "mqtt_node_id", "bedside")

    calls = []

    async def fake_stop(*, disabled=False):
        calls.append(("stop", disabled))
        bridge._task = None

    async def fake_start():
        calls.append(("start", None))

    monkeypatch.setattr(bridge, "stop", fake_stop)
    monkeypatch.setattr(bridge, "start", fake_start)

    asyncio.run(bridge.apply_runtime_settings())

    assert calls == [("stop", False), ("start", None)]


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


def test_v2_memory_search(monkeypatch):
    monkeypatch.setattr(
        api_v2.memory_store,
        "graph_rag_search",
        lambda query, k=5: [
            {
                "text": "Met Bob at the cafe",
                "metadata": {"type": "user_input"},
                "distance": 0.12,
                "source": "graph",
                "matched_entity": "Bob",
            }
        ],
    )

    response = client.get("/api/v2/memory/search", params={"query": "bob", "mode": "graph"})

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v2"
    assert body["query"] == "bob"
    assert body["items"][0]["matched_entity"] == "Bob"
    assert body["items"][0]["source"] == "graph"


def test_v2_profile_contract(monkeypatch):
    monkeypatch.setattr(
        api_v2.memory_store,
        "get_user_profile",
        lambda user_id: SimpleNamespace(
            user_id=user_id,
            name="Rain",
            email="rain@example.com",
            birthday="1990-01-01",
            hobbies="coding, music",
            relationships="close friends",
            notes="night owl",
            therapeutic_mode=True,
            personality="Curious",
            humor_level=8,
        ),
    )
    monkeypatch.setattr(
        api_v2.memory_store,
        "get_recent_moods",
        lambda user_id, limit=14: [
            SimpleNamespace(id=1, user_id=user_id, date=datetime(2026, 1, 4, 10, 0, 0), mood=7)
        ],
    )
    monkeypatch.setattr(
        api_v2.memory_store,
        "get_habits",
        lambda user_id: [SimpleNamespace(id=2, user_id=user_id, name="Workout", streak=4, last_done=datetime(2026, 1, 3, 8, 0, 0))],
    )
    monkeypatch.setattr(
        api_v2.memory_store,
        "get_personal_goals",
        lambda user_id: [SimpleNamespace(id=3, user_id=user_id, name="Ship v2", description="Launch the rewrite", linked_habit_id=None, linked_decision_id=None, status="active")],
    )
    monkeypatch.setattr(
        api_v2.memory_store,
        "get_decisions",
        lambda user_id: [SimpleNamespace(id=4, user_id=user_id, question="Rewrite UI?", pros="Better UX", cons="More work", outcome="Yes")],
    )
    monkeypatch.setattr(
        api_v2.memory_store,
        "get_cbt_exercises",
        lambda user_id: [SimpleNamespace(id=5, user_id=user_id, name="Gratitude", description="List wins", completed_count=2)],
    )
    monkeypatch.setattr(
        api_v2.memory_store,
        "get_recent_activities",
        lambda user_id, limit=10: [SimpleNamespace(id=6, user_id=user_id, app="VS Code", duration=3600, timestamp=datetime(2026, 1, 4, 11, 0, 0))],
    )
    monkeypatch.setattr(
        api_v2.memory_store,
        "get_recent_sleeps",
        lambda user_id, limit=10: [SimpleNamespace(id=7, user_id=user_id, date=datetime(2026, 1, 4).date(), hours_slept=7.5, quality=8)],
    )
    monkeypatch.setattr(
        api_v2.memory_store,
        "get_recent_transactions",
        lambda user_id, limit=10: [SimpleNamespace(id=8, user_id=user_id, date=datetime(2026, 1, 4).date(), amount=-12.5, category="food")],
    )
    monkeypatch.setattr(
        api_v2.memory_store,
        "get_contacts",
        lambda user_id, limit=50: [SimpleNamespace(id=9, user_id=user_id, name="Bob", last_contact=datetime(2026, 1, 2).date(), strength=7, entity_id=None)],
    )

    response = client.get("/api/v2/profile", params={"user_id": "default"})

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v2"
    assert body["profile"]["name"] == "Rain"
    assert body["moods"][0]["mood"] == 7
    assert body["habits"][0]["name"] == "Workout"
    assert body["goals"][0]["name"] == "Ship v2"
    assert body["contacts"][0]["name"] == "Bob"


def test_v2_user_model_contract_only_projection(monkeypatch):
    monkeypatch.setattr(
        api_v2.memory_store,
        "get_user_profile",
        lambda user_id: SimpleNamespace(
            user_id=user_id,
            name="Rain",
            email="rain@example.com",
            birthday=None,
            hobbies="coding",
            relationships=None,
            notes="night owl",
            therapeutic_mode=False,
            personality="Curious",
            humor_level=8,
        ),
    )
    monkeypatch.setattr(
        api_v2.memory_store,
        "get_personal_goals",
        lambda user_id: [
            SimpleNamespace(
                id=3,
                user_id=user_id,
                name="Ship Joi v2",
                description="Make Joi feel present",
                linked_habit_id=None,
                linked_decision_id=None,
                status="active",
            )
        ],
    )
    monkeypatch.setattr(
        api_v2.memory_store,
        "get_contacts",
        lambda user_id, limit=50: [
            SimpleNamespace(
                id=9,
                user_id=user_id,
                name="Bob",
                last_contact=datetime(2026, 1, 2).date(),
                strength=7,
                entity_id=None,
            )
        ],
    )
    monkeypatch.setattr(
        api_v2.memory_store,
        "get_recent_moods",
        lambda user_id, limit=14: [
            SimpleNamespace(id=1, user_id=user_id, date=datetime(2026, 1, 4, 10, 0, 0), mood=7),
            SimpleNamespace(id=2, user_id=user_id, date=datetime(2026, 1, 3, 10, 0, 0), mood=6),
            SimpleNamespace(id=3, user_id=user_id, date=datetime(2026, 1, 2, 10, 0, 0), mood=5),
        ],
    )

    response = client.get("/api/v2/user-model", params={"user_id": "default"})

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v2"
    assert body["status"] == "contract_only"
    assert body["policy"]["inference_enabled"] is False
    assert body["policy"]["correction_supported"] is False
    sections = {section["key"]: section for section in body["sections"]}
    assert set(sections) >= {
        "active_projects",
        "stated_goals",
        "important_people",
        "mood_trend",
        "communication_preferences",
        "character_notes",
    }
    assert sections["stated_goals"]["items"][0]["label"] == "Ship Joi v2"
    assert sections["stated_goals"]["items"][0]["user_confirmed"] is True
    assert sections["stated_goals"]["items"][0]["evidence"][0]["source_type"] == "goal"
    assert sections["important_people"]["items"][0]["label"] == "Bob"
    assert sections["mood_trend"]["items"][0]["category"] == "explicit_mood_log"


def test_v2_user_model_correction_contract_not_persisted():
    response = client.post(
        "/api/v2/user-model/correct",
        params={"user_id": "default"},
        json={
            "section_key": "communication_preferences",
            "action": "confirm",
            "item_id": "communication_preferences:default:humor",
        },
    )

    assert response.status_code == 501
    assert "not implemented" in response.json()["detail"]


def test_v2_profile_patch(monkeypatch):
    state = {
        "profile": SimpleNamespace(
            user_id="default",
            name="Rain",
            email="rain@example.com",
            birthday=None,
            hobbies=None,
            relationships=None,
            notes=None,
            therapeutic_mode=False,
            personality="Curious",
            humor_level=5,
        )
    }

    def fake_get_user_profile(user_id):
        return state["profile"]

    def fake_save_user_profile(profile):
        state["profile"] = profile
        return profile

    monkeypatch.setattr(api_v2.memory_store, "get_user_profile", fake_get_user_profile)
    monkeypatch.setattr(api_v2.memory_store, "save_user_profile", fake_save_user_profile)
    monkeypatch.setattr(api_v2.memory_store, "get_recent_moods", lambda user_id, limit=14: [])
    monkeypatch.setattr(api_v2.memory_store, "get_habits", lambda user_id: [])
    monkeypatch.setattr(api_v2.memory_store, "get_personal_goals", lambda user_id: [])
    monkeypatch.setattr(api_v2.memory_store, "get_decisions", lambda user_id: [])
    monkeypatch.setattr(api_v2.memory_store, "get_cbt_exercises", lambda user_id: [])
    monkeypatch.setattr(api_v2.memory_store, "get_recent_activities", lambda user_id, limit=10: [])
    monkeypatch.setattr(api_v2.memory_store, "get_recent_sleeps", lambda user_id, limit=10: [])
    monkeypatch.setattr(api_v2.memory_store, "get_recent_transactions", lambda user_id, limit=10: [])
    monkeypatch.setattr(api_v2.memory_store, "get_contacts", lambda user_id, limit=50: [])

    response = client.patch("/api/v2/profile", params={"user_id": "default"}, json={"name": "Rain C", "humor_level": 9})

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["name"] == "Rain C"
    assert body["profile"]["humor_level"] == 9


def test_v2_create_contact(monkeypatch):
    monkeypatch.setattr(
        api_v2.memory_store,
        "add_contact",
        lambda name, last_contact=None, strength=5, entity_id=None, user_id="default": SimpleNamespace(
            id=11,
            user_id=user_id,
            name=name,
            last_contact=last_contact or datetime(2026, 1, 4).date(),
            strength=strength,
            entity_id=entity_id,
        ),
    )

    response = client.post(
        "/api/v2/profile/contacts",
        json={"user_id": "default", "name": "Alice", "last_contact": "2026-01-04", "strength": 8},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v2"
    assert body["contact"]["name"] == "Alice"
    assert body["contact"]["strength"] == 8


def test_v2_planner_generate(monkeypatch):
    monkeypatch.setattr(
        api_v2,
        "generate_day_plan",
        lambda memory_store, user_id, key_tasks, focus_areas, energy_level: {
            "provider": "ollama",
            "model": "gpt-4o-mini",
            "blocks": [
                {"time": "8:00-9:00", "activity": "Morning reset"},
                {"time": "9:00-11:00", "activity": "Build Next.js shell"},
            ],
            "snapshot": {
                "user_id": user_id,
                "latest_mood": 6,
                "mood_trend": {"direction": "up"},
                "health_correlation": {"sleep_delta": -0.5},
                "overdue_contacts": [{"name": "Bob", "days_overdue": 14, "strength": 7}],
                "goals": [SimpleNamespace(name="Ship v2", status="active")],
                "habits": [SimpleNamespace(name="Workout")],
            },
        },
    )

    response = client.post(
        "/api/v2/planner/generate",
        json={
            "user_id": "default",
            "key_tasks": ["Build Next.js shell"],
            "focus_areas": ["Work"],
            "energy_level": 7,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["api_version"] == "v2"
    assert body["provider"] == "ollama"
    assert body["blocks"][0]["time"] == "8:00-9:00"
    assert body["snapshot"]["active_goals"] == ["Ship v2"]
    assert body["snapshot"]["habits"] == ["Workout"]


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

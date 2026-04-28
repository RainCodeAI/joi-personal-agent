"""Tests for explicit sharing detection and chat integration."""
from app.user_model.explicit_share import (
    ShareDetection,
    acknowledgement_hint,
    detect_explicit_share,
)


# ---------------------------------------------------------------------------
# Detection — trigger phrases
# ---------------------------------------------------------------------------

def test_joi_remember_that():
    d = detect_explicit_share("Joi, remember that I'm going through a job search right now.")
    assert d is not None
    assert d.trigger == "joi_remember"
    assert "job search" in d.value


def test_i_want_you_to_know():
    d = detect_explicit_share("I want you to know that my father passed away last month.")
    assert d is not None
    assert "father" in d.value.lower()


def test_keep_in_mind():
    d = detect_explicit_share("Keep in mind that I prefer short replies — I get overwhelmed easily.")
    assert d is not None
    assert d.section_key == "communication_preferences"


def test_note_that():
    d = detect_explicit_share("Note that I'm working on a Python backend project for the next few weeks.")
    assert d is not None
    assert d.section_key == "active_projects"


def test_you_should_know():
    d = detect_explicit_share("You should know that my goal is to get promoted this year.")
    assert d is not None
    assert d.section_key == "stated_goals"


def test_dont_forget():
    d = detect_explicit_share("Don't forget that I have an important meeting tomorrow.")
    assert d is not None


def test_just_so_you_know():
    d = detect_explicit_share("Just so you know, I'm really stressed about the deadline.")
    assert d is not None
    assert d.section_key == "recurring_worries"


def test_for_context():
    d = detect_explicit_share("For context, I finished building the MQTT bridge yesterday.")
    assert d is not None
    assert d.section_key == "recent_wins"


def test_remember_that_start():
    d = detect_explicit_share("Remember that my colleague Sarah is handling the frontend.")
    assert d is not None
    assert d.section_key == "important_people"


# ---------------------------------------------------------------------------
# No match — ordinary messages
# ---------------------------------------------------------------------------

def test_no_match_ordinary():
    assert detect_explicit_share("What time is it?") is None


def test_no_match_general_remember():
    # "remember" used non-personally should not trigger
    assert detect_explicit_share("Do you remember what we talked about?") is None


def test_no_match_short_excerpt():
    # Trigger present but extracted content is too short
    assert detect_explicit_share("Joi, remember that") is None


def test_no_match_empty():
    assert detect_explicit_share("") is None


# ---------------------------------------------------------------------------
# Section routing
# ---------------------------------------------------------------------------

def test_routes_goal():
    d = detect_explicit_share("I want you to know my goal is to run a marathon.")
    assert d is not None
    assert d.section_key == "stated_goals"


def test_routes_project():
    d = detect_explicit_share("Note that I'm building a 3D avatar renderer for Joi.")
    assert d is not None
    assert d.section_key == "active_projects"


def test_routes_worry():
    d = detect_explicit_share("Keep in mind that I'm really anxious about the presentation.")
    assert d is not None
    assert d.section_key == "recurring_worries"


def test_routes_person():
    d = detect_explicit_share("Remember that my partner is really supportive of this project.")
    assert d is not None
    assert d.section_key == "important_people"


def test_routes_default_to_character_notes():
    d = detect_explicit_share("Joi, remember that I tend to work best late at night.")
    assert d is not None
    assert d.section_key == "character_notes"


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

def test_confidence_is_high():
    d = detect_explicit_share("I want you to know I'm going through a difficult time.")
    assert d is not None
    assert d.confidence >= 0.90


def test_label_is_shorter_than_value():
    d = detect_explicit_share("Joi, remember that I'm working on building a FastAPI backend for my personal agent project.")
    assert d is not None
    assert len(d.label) <= len(d.value)
    assert len(d.label) <= 60


def test_acknowledgement_hint_contains_excerpt():
    d = detect_explicit_share("I want you to know that my cat died last week.")
    assert d is not None
    hint = acknowledgement_hint(d)
    assert "cat" in hint.lower() or "died" in hint.lower()
    assert "briefly" in hint.lower()


# ---------------------------------------------------------------------------
# Chat API integration — share is persisted and hint is passed
# ---------------------------------------------------------------------------

def test_chat_persists_share_on_explicit_message(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from app.api.main import app
    from app.api import v2 as api_v2
    from app.user_model.store import UserModelCorrectionStore

    store_path = tmp_path / "corrections.json"
    correction_store = UserModelCorrectionStore(path=store_path)
    monkeypatch.setattr(api_v2, "user_model_corrections", correction_store)

    captured_extra = {}

    original_reply = api_v2.agent.reply

    def mock_reply(history, text, session_id, *, on_token=None, attachment_contexts=None, extra_context=None):
        captured_extra["extra_context"] = extra_context
        return SimpleNamespace(
            user_message_id=1,
            assistant_message_id=2,
            tool_calls=[],
            craving_score=0,
            is_dramatic_return=False,
            provider="mock",
            route=["mock"],
            errors=[],
        )

    monkeypatch.setattr(api_v2.agent, "reply", mock_reply)
    monkeypatch.setattr(
        api_v2.memory_store, "get_chat_history", lambda sid: []
    )
    monkeypatch.setattr(
        api_v2.memory_store, "get_session",
        lambda sid: SimpleNamespace(id=sid, user_id="default", title=None, created_at="2026-01-01", updated_at="2026-01-01"),
    )
    monkeypatch.setattr(
        api_v2.memory_store, "get_chat_history",
        lambda sid: [
            SimpleNamespace(id=1, session_id=sid, role="user", content="test", timestamp="2026-01-01"),
            SimpleNamespace(id=2, session_id=sid, role="assistant", content="ok", timestamp="2026-01-01"),
        ],
    )

    client = TestClient(app)
    resp = client.post(
        "/api/v2/chat",
        json={"session_id": "s1", "text": "Joi, remember that I'm working on a FastAPI project."},
    )

    # Correction was persisted
    corrections = correction_store.list_for_user("default")
    assert any(c["action"] == "add" for c in corrections)
    assert any("FastAPI" in (c.get("value") or "") or "FastAPI" in (c.get("label") or "") for c in corrections)

    # Acknowledgement hint was passed to agent.reply
    assert captured_extra.get("extra_context") is not None
    assert "FastAPI" in captured_extra["extra_context"] or "deliberately shared" in captured_extra["extra_context"]


def test_chat_no_share_passes_no_extra_context(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from fastapi.testclient import TestClient
    from app.api.main import app
    from app.api import v2 as api_v2
    from app.user_model.store import UserModelCorrectionStore

    store_path = tmp_path / "corrections.json"
    correction_store = UserModelCorrectionStore(path=store_path)
    monkeypatch.setattr(api_v2, "user_model_corrections", correction_store)

    captured_extra = {}

    def mock_reply(history, text, session_id, *, on_token=None, attachment_contexts=None, extra_context=None):
        captured_extra["extra_context"] = extra_context
        return SimpleNamespace(
            user_message_id=1, assistant_message_id=2, tool_calls=[],
            craving_score=0, is_dramatic_return=False, provider="mock", route=["mock"], errors=[],
        )

    monkeypatch.setattr(api_v2.agent, "reply", mock_reply)
    monkeypatch.setattr(api_v2.memory_store, "get_session",
        lambda sid: SimpleNamespace(id=sid, user_id="default", title=None, created_at="2026-01-01", updated_at="2026-01-01"),
    )
    monkeypatch.setattr(api_v2.memory_store, "get_chat_history",
        lambda sid: [
            SimpleNamespace(id=1, session_id=sid, role="user", content="hi", timestamp="2026-01-01"),
            SimpleNamespace(id=2, session_id=sid, role="assistant", content="hello", timestamp="2026-01-01"),
        ],
    )

    client = TestClient(app)
    client.post("/api/v2/chat", json={"session_id": "s1", "text": "What's the weather like?"})

    assert captured_extra.get("extra_context") is None
    assert correction_store.list_for_user("default") == []

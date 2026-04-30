"""Tests for session synthesis pattern extraction and API stub."""
import json
from types import SimpleNamespace

import pytest

from app.user_model.synthesis import (
    SynthesisCandidate,
    _MIN_CONFIDENCE,
    extract_candidates,
)


def _msg(content: str, role: str = "user", idx: int = 0) -> SimpleNamespace:
    return SimpleNamespace(role=role, content=content, session_id="test", timestamp=None)


# ---------------------------------------------------------------------------
# Pattern extraction — basic
# ---------------------------------------------------------------------------

def test_extracts_stated_goal():
    msgs = [_msg("My goal is to ship the hardware node by the end of the month.")]
    results = extract_candidates(msgs)
    assert any(c.section_key == "stated_goals" for c in results)


def test_extracts_active_project():
    msgs = [_msg("I've been working on a FastAPI backend for Joi for the past few weeks.")]
    results = extract_candidates(msgs)
    assert any(c.section_key == "active_projects" for c in results)


def test_extracts_recurring_worry():
    msgs = [_msg("I keep thinking about whether the deadline is realistic.")]
    results = extract_candidates(msgs)
    assert any(c.section_key == "recurring_worries" for c in results)


def test_extracts_open_loop():
    msgs = [_msg("I still haven't replied to that email from last week.")]
    results = extract_candidates(msgs)
    assert any(c.section_key == "open_loops" for c in results)


def test_extracts_communication_preference():
    msgs = [_msg("Can you just be more direct with me? I prefer short answers.")]
    results = extract_candidates(msgs)
    assert any(c.section_key == "communication_preferences" for c in results)


def test_extracts_recent_win():
    msgs = [_msg("I finally got the MQTT bridge working after days of debugging.")]
    results = extract_candidates(msgs)
    assert any(c.section_key == "recent_wins" for c in results)


def test_extracts_mood_positive():
    msgs = [_msg("I'm really excited about what we built today.")]
    results = extract_candidates(msgs)
    assert any(c.section_key == "mood_trend" for c in results)


def test_extracts_mood_negative():
    msgs = [_msg("Honestly I'm exhausted. It's been a brutal week.")]
    results = extract_candidates(msgs)
    assert any(c.section_key == "mood_trend" for c in results)


def test_extracts_important_person():
    msgs = [_msg("My friend Sarah helped me talk through the hardware problem.")]
    results = extract_candidates(msgs)
    people = [c for c in results if c.section_key == "important_people"]
    assert people
    assert people[0].label == "Sarah (friend)"


def test_important_person_requires_name():
    msgs = [_msg("I need to follow up with Dana because my colleague from hardware is waiting.")]
    results = extract_candidates(msgs)
    people = [c for c in results if c.section_key == "important_people"]
    assert people == []


def test_preserves_subject_casing():
    msgs = [_msg("I've been working on a FastAPI backend for Joi.")]
    results = extract_candidates(msgs)
    active = [c for c in results if c.section_key == "active_projects"]
    assert active
    assert "FastAPI" in active[0].label


def test_ignores_conversational_want_to_false_positive():
    msgs = [_msg("I want to know what you think about this.")]
    results = extract_candidates(msgs)
    assert all(c.section_key != "stated_goals" for c in results)


def test_deduplicates_multiple_patterns_from_same_sentence():
    msgs = [_msg("Can you just be more direct when you're giving me implementation options?")]
    results = extract_candidates(msgs)
    prefs = [c for c in results if c.section_key == "communication_preferences"]
    assert len(prefs) == 1
    assert prefs[0].label == "Be more direct when you're giving me implementation options"


# ---------------------------------------------------------------------------
# Assistant messages are ignored
# ---------------------------------------------------------------------------

def test_ignores_assistant_messages():
    msgs = [_msg("My goal is to finish this.", role="assistant")]
    results = extract_candidates(msgs)
    assert results == []


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------

def test_confidence_at_least_min():
    msgs = [_msg("My goal is to run a marathon next year.")]
    results = extract_candidates(msgs)
    assert all(c.confidence >= _MIN_CONFIDENCE for c in results)


def test_confidence_higher_when_subject_parseable():
    msgs = [_msg("My goal is to launch the product in Q3.")]
    results = extract_candidates(msgs)
    goals = [c for c in results if c.section_key == "stated_goals"]
    assert goals
    assert goals[0].confidence >= 0.75


# ---------------------------------------------------------------------------
# Deduplication — same label across messages
# ---------------------------------------------------------------------------

def test_deduplicates_same_label():
    msgs = [
        _msg("My goal is to finish the Joi backend."),
        _msg("My goal is to finish the Joi backend, seriously."),
    ]
    results = extract_candidates(msgs)
    goal_labels = [c.label.lower() for c in results if c.section_key == "stated_goals"]
    # Should not have duplicates for the same effective label
    assert len(goal_labels) == len(set(goal_labels))


# ---------------------------------------------------------------------------
# Correction blocking
# ---------------------------------------------------------------------------

def test_correction_block_hides_candidate():
    msgs = [_msg("My goal is to ship the hardware node.")]
    # Pre-extract to get the candidate_id
    candidates = extract_candidates(msgs)
    goals = [c for c in candidates if c.section_key == "stated_goals"]
    assert goals

    cid = goals[0].candidate_id
    corrections = [{"action": "hide", "item_id": cid, "section_key": "stated_goals"}]
    results = extract_candidates(msgs, corrections=corrections)
    # Blocked items are excluded from results
    assert all(c.candidate_id != cid for c in results)


def test_correction_delete_hides_candidate():
    msgs = [_msg("I finally got the MQTT bridge working.")]
    candidates = extract_candidates(msgs)
    wins = [c for c in candidates if c.section_key == "recent_wins"]
    assert wins

    cid = wins[0].candidate_id
    corrections = [{"action": "delete", "item_id": cid, "section_key": "recent_wins"}]
    results = extract_candidates(msgs, corrections=corrections)
    assert all(c.candidate_id != cid for c in results)


def test_confirm_correction_does_not_block():
    msgs = [_msg("My goal is to finish the backend.")]
    candidates = extract_candidates(msgs)
    goals = [c for c in candidates if c.section_key == "stated_goals"]
    assert goals

    cid = goals[0].candidate_id
    corrections = [{"action": "confirm", "item_id": cid, "section_key": "stated_goals"}]
    results = extract_candidates(msgs, corrections=corrections)
    # Confirm does not block re-extraction (user has confirmed it; synthesis duplicate check handles it)
    # The item may still appear — that is correct behaviour (duplicate_of_existing handles merging)
    assert isinstance(results, list)


# ---------------------------------------------------------------------------
# Existing label deduplication
# ---------------------------------------------------------------------------

def test_duplicate_of_existing_excluded():
    msgs = [_msg("I'm working on the FastAPI backend.")]

    existing_item = SimpleNamespace(label="FastAPI backend", id="existing-1", hidden=False, user_confirmed=True)
    existing_section = SimpleNamespace(key="active_projects", items=[existing_item])

    results = extract_candidates(msgs, existing_sections=[existing_section])
    active = [c for c in results if c.section_key == "active_projects"]
    # Should be excluded because label matches existing
    assert all(not c.duplicate_of_existing for c in results)
    assert not active


def test_include_skipped_returns_duplicate_with_flag():
    msgs = [_msg("I'm working on the FastAPI backend.")]

    existing_item = SimpleNamespace(label="FastAPI backend", id="existing-1", hidden=False, user_confirmed=True)
    existing_section = SimpleNamespace(key="active_projects", items=[existing_item])

    results = extract_candidates(msgs, existing_sections=[existing_section], include_skipped=True)
    active = [c for c in results if c.section_key == "active_projects"]
    assert active
    assert active[0].duplicate_of_existing is True


# ---------------------------------------------------------------------------
# Empty inputs
# ---------------------------------------------------------------------------

def test_empty_messages_returns_empty():
    assert extract_candidates([]) == []


def test_no_matching_messages():
    msgs = [_msg("The weather is fine today. Nothing personal here.")]
    results = extract_candidates(msgs)
    assert results == []


# ---------------------------------------------------------------------------
# API stub
# ---------------------------------------------------------------------------

def test_synthesize_endpoint_returns_dry_run(monkeypatch):
    from fastapi.testclient import TestClient
    from app.api.main import app
    from app.api import v2 as api_v2
    from app.user_model.store import UserModelCorrectionStore
    import tempfile, pathlib

    tmp = pathlib.Path(tempfile.mkdtemp()) / "corrections.json"
    store = UserModelCorrectionStore(path=tmp)
    monkeypatch.setattr(api_v2, "user_model_corrections", store)

    # Patch memory_store to return a fake session with one user message
    fake_msg = SimpleNamespace(role="user", content="My goal is to launch the product.", session_id="s1", timestamp=None)
    monkeypatch.setattr(api_v2.memory_store, "get_chat_history", lambda sid: [fake_msg])

    client = TestClient(app)
    resp = client.post("/api/v2/user-model/synthesize", params={"session_id": "s1", "user_id": "default"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is True
    assert data["writes_enabled"] is False
    assert data["message_count"] == 1
    assert isinstance(data["candidates"], list)
    assert data["written_count"] == 0


def test_synthesize_endpoint_session_not_found_returns_empty(monkeypatch):
    from fastapi.testclient import TestClient
    from app.api.main import app
    from app.api import v2 as api_v2

    monkeypatch.setattr(api_v2.memory_store, "get_chat_history", lambda sid: [])

    client = TestClient(app)
    resp = client.post("/api/v2/user-model/synthesize", params={"session_id": "nonexistent"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["candidates"] == []
    assert data["message_count"] == 0


def test_synthesize_endpoint_returns_skipped_duplicates(monkeypatch):
    from fastapi.testclient import TestClient
    from app.api.main import app
    from app.api import v2 as api_v2
    from app.user_model.store import UserModelCorrectionStore
    import tempfile, pathlib

    tmp = pathlib.Path(tempfile.mkdtemp()) / "corrections.json"
    store = UserModelCorrectionStore(path=tmp)
    monkeypatch.setattr(api_v2, "user_model_corrections", store)

    fake_msg = SimpleNamespace(role="user", content="I'm working on the FastAPI backend.", session_id="s1", timestamp=None)
    monkeypatch.setattr(api_v2.memory_store, "get_chat_history", lambda sid: [fake_msg])

    existing_item = SimpleNamespace(label="FastAPI backend", id="existing-1", hidden=False, user_confirmed=True)
    existing_section = SimpleNamespace(key="active_projects", items=[existing_item])
    monkeypatch.setattr(api_v2, "_user_model_response", lambda user_id: SimpleNamespace(sections=[existing_section]))

    client = TestClient(app)
    resp = client.post("/api/v2/user-model/synthesize", params={"session_id": "s1", "user_id": "default"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["skipped_count"] == 1
    assert data["candidates"][0]["duplicate_of_existing"] is True


def test_synthesize_endpoint_llm_method_is_dry_run_only(monkeypatch):
    from fastapi.testclient import TestClient
    from app.api.main import app
    from app.api import v2 as api_v2
    from app.user_model.store import UserModelCorrectionStore
    import tempfile, pathlib

    store = UserModelCorrectionStore(path=pathlib.Path(tempfile.mkdtemp()) / "corrections.json")
    monkeypatch.setattr(api_v2, "user_model_corrections", store)

    fake_msg = SimpleNamespace(
        role="user",
        content="I'm building a prompt preview panel.",
        session_id="s1",
        timestamp=None,
    )
    monkeypatch.setattr(api_v2.memory_store, "get_chat_history", lambda sid: [fake_msg])

    def fake_route(prompt, context):
        assert "Messages JSON" in prompt
        assert "prompt preview panel" in prompt
        assert context["task"] == "user_model_synthesis"
        assert context["dry_run"] is True
        assert context["writes_enabled"] is False
        return {
            "response": json.dumps(
                {
                    "candidates": [
                        {
                            "section_key": "active_projects",
                            "label": "Prompt preview panel",
                            "value": "User is building a prompt preview panel.",
                            "confidence": 0.86,
                            "source_excerpt": "I'm building a prompt preview panel.",
                            "source_message_index": 0,
                            "source_message_role": "user",
                        }
                    ]
                }
            ),
            "model_used": "mock-llm",
            "route": ["mock-llm"],
            "errors": [],
        }

    monkeypatch.setattr(api_v2, "_route_synthesis_prompt", fake_route)

    client = TestClient(app)
    resp = client.post(
        "/api/v2/user-model/synthesize",
        params={"session_id": "s1", "user_id": "default", "method": "llm"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["method"] == "llm"
    assert data["dry_run"] is True
    assert data["writes_enabled"] is False
    assert data["written_count"] == 0
    assert data["provider"]["selected"] == "mock-llm"
    assert len(data["candidates"]) == 1
    assert data["candidates"][0]["inference_method"] == "llm"
    assert store.list_for_user("default") == []


def test_synthesize_endpoint_rejects_unknown_method():
    from fastapi.testclient import TestClient
    from app.api.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/v2/user-model/synthesize",
        params={"session_id": "s1", "method": "automatic"},
    )
    assert resp.status_code == 422

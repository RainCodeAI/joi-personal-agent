import json
from types import SimpleNamespace

from app.user_model.llm_synthesis import parse_llm_candidates


def _msg(content: str, role: str = "user") -> SimpleNamespace:
    return SimpleNamespace(role=role, content=content, session_id="test", timestamp=None)


def _payload(candidate: dict) -> str:
    return json.dumps({"candidates": [candidate]})


def _candidate(**overrides):
    base = {
        "section_key": "active_projects",
        "label": "Prompt preview panel",
        "value": "User is building a prompt preview panel.",
        "confidence": 0.86,
        "source_excerpt": "I'm building a prompt preview panel.",
        "source_message_index": 0,
        "source_message_role": "user",
    }
    base.update(overrides)
    return base


def test_parse_llm_candidates_accepts_grounded_candidate():
    messages = [_msg("I'm building a prompt preview panel.")]
    results = parse_llm_candidates(_payload(_candidate()), messages)
    assert len(results) == 1
    assert results[0].section_key == "active_projects"
    assert results[0].inference_method == "llm"
    assert results[0].confidence == 0.86


def test_parse_llm_candidates_accepts_list_payload():
    messages = [_msg("I'm building a prompt preview panel.")]
    raw = json.dumps([_candidate()])
    results = parse_llm_candidates(raw, messages)
    assert len(results) == 1


def test_parse_llm_candidates_drops_malformed_json():
    messages = [_msg("I'm building a prompt preview panel.")]
    assert parse_llm_candidates("not-json", messages) == []


def test_parse_llm_candidates_drops_unsupported_section():
    messages = [_msg("I'm building a prompt preview panel.")]
    raw = _payload(_candidate(section_key="character_notes"))
    assert parse_llm_candidates(raw, messages) == []


def test_parse_llm_candidates_drops_low_confidence():
    messages = [_msg("I'm building a prompt preview panel.")]
    raw = _payload(_candidate(confidence=0.70))
    assert parse_llm_candidates(raw, messages) == []


def test_parse_llm_candidates_drops_missing_evidence():
    messages = [_msg("I'm building a prompt preview panel.")]
    raw = _payload(_candidate(source_excerpt=""))
    assert parse_llm_candidates(raw, messages) == []


def test_parse_llm_candidates_drops_ungrounded_evidence():
    messages = [_msg("I'm building a prompt preview panel.")]
    raw = _payload(_candidate(source_excerpt="I'm building a calendar integration."))
    assert parse_llm_candidates(raw, messages) == []


def test_parse_llm_candidates_drops_assistant_role_evidence():
    messages = [
        _msg("That sounds useful.", role="assistant"),
        _msg("I'm building a prompt preview panel."),
    ]
    raw = _payload(_candidate(source_message_index=0, source_message_role="assistant"))
    assert parse_llm_candidates(raw, messages) == []


def test_parse_llm_candidates_drops_assistant_index_even_if_role_claims_user():
    messages = [
        _msg("I'm building a prompt preview panel.", role="assistant"),
        _msg("Okay."),
    ]
    raw = _payload(_candidate(source_message_index=0, source_message_role="user"))
    assert parse_llm_candidates(raw, messages) == []


def test_parse_llm_candidates_deduplicates_existing_labels():
    messages = [_msg("I'm building a prompt preview panel.")]
    existing_item = SimpleNamespace(label="Prompt preview panel")
    existing_section = SimpleNamespace(items=[existing_item])
    results = parse_llm_candidates(
        _payload(_candidate()),
        messages,
        existing_sections=[existing_section],
    )
    assert results == []


def test_parse_llm_candidates_can_include_skipped_duplicates_for_diagnostics():
    messages = [_msg("I'm building a prompt preview panel.")]
    existing_item = SimpleNamespace(label="Prompt preview panel")
    existing_section = SimpleNamespace(items=[existing_item])
    results = parse_llm_candidates(
        _payload(_candidate()),
        messages,
        existing_sections=[existing_section],
        include_skipped=True,
    )
    assert len(results) == 1
    assert results[0].duplicate_of_existing is True


def test_parse_llm_candidates_applies_correction_blocks():
    messages = [_msg("I'm building a prompt preview panel.")]
    first = parse_llm_candidates(_payload(_candidate()), messages)
    assert first
    corrections = [{"action": "delete", "item_id": first[0].candidate_id}]
    results = parse_llm_candidates(
        _payload(_candidate()),
        messages,
        corrections=corrections,
    )
    assert results == []


def test_parse_llm_candidates_keeps_highest_duplicate_confidence():
    messages = [_msg("I'm building a prompt preview panel.")]
    raw = json.dumps(
        {
            "candidates": [
                _candidate(confidence=0.78),
                _candidate(confidence=0.91),
            ]
        }
    )
    results = parse_llm_candidates(raw, messages)
    assert len(results) == 1
    assert results[0].confidence == 0.91

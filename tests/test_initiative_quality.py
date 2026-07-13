"""Tests for the Phase 10 initiative quality gate and emission memory."""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.config import settings
from app.initiative.emission_memory import InitiativeEmissionMemory
from app.initiative.policy import CandidateEvidence, InitiativeCandidate, InitiativePolicy
from app.initiative.quality import (
    DEFAULT_THRESHOLD,
    IGNORED_DAMPEN_FACTOR,
    InitiativeQualityGate,
    SAFETY_FLOOR,
)
from app.initiative.service import InitiativeService
from app.initiative.store import InitiativeStore


def _now():
    return datetime(2026, 7, 11, 15, 0, tzinfo=timezone.utc)


def _evidence_candidate(
    *,
    excerpt="I still need to follow up with Dana about the review checklist.",
    source_id="mem-1",
    observed_hours_ago=14.0,
    message="Earlier you mentioned Dana - did that go anywhere?",
    topic_key=None,
):
    observed = (_now() - timedelta(hours=observed_hours_ago)).isoformat()
    if topic_key is None and source_id:
        topic_key = f"memory_followup:{source_id}"
    return InitiativeCandidate(
        type="memory_followup",
        priority="low",
        reason="test",
        session_id="s",
        message=message,
        expires_at=(_now() + timedelta(hours=2)).isoformat(),
        evidence=CandidateEvidence(
            source_type="memory",
            excerpt=excerpt,
            source_id=source_id,
            observed_at=observed,
            topic_key=topic_key,
        ),
    )


# ── emission memory ──────────────────────────────────────────────────────────


def test_emission_memory_records_and_detects_repeat(tmp_path):
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    memory.record(
        initiative_type="memory_followup",
        topic_key="memory_followup:mem-1",
        message="Earlier...",
        quality_score=0.9,
        emitted_at=_now(),
    )
    assert memory.seen_topic_within("memory_followup:mem-1", now=_now()) is True
    # Outside the 7-day window it should no longer count.
    later = _now() + timedelta(days=8)
    assert memory.seen_topic_within("memory_followup:mem-1", now=later) is False
    assert memory.seen_topic_within("memory_followup:other", now=_now()) is False


def test_register_user_reply_marks_recent_engaged(tmp_path):
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    memory.record(
        initiative_type="memory_followup",
        topic_key="k1",
        message="Earlier...",
        quality_score=0.9,
        session_id="s",
        emitted_at=_now() - timedelta(minutes=5),
    )
    changed = memory.register_user_reply("s", now=_now())
    assert len(changed) == 1
    assert changed[0]["user_response"] == "engaged"


def test_register_user_reply_ages_out_stale_to_ignored(tmp_path):
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    memory.record(
        initiative_type="memory_followup",
        topic_key="k1",
        message="Old one",
        quality_score=0.9,
        session_id="s",
        emitted_at=_now() - timedelta(hours=2),  # well outside the 30-min window
    )
    changed = memory.register_user_reply("s", now=_now())
    assert len(changed) == 1
    assert changed[0]["user_response"] == "ignored"


def test_register_user_reply_is_session_scoped(tmp_path):
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    memory.record(
        initiative_type="memory_followup",
        topic_key="k1",
        message="theirs",
        quality_score=0.9,
        session_id="other",
        emitted_at=_now() - timedelta(minutes=5),
    )
    changed = memory.register_user_reply("s", now=_now())
    assert changed == []
    assert memory.recent()[0]["user_response"] == "unknown"


def test_register_user_reply_engages_only_newest_within_window(tmp_path):
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    for minutes in (20, 3):  # older-but-in-window, then newest
        memory.record(
            initiative_type="memory_followup",
            topic_key=f"k{minutes}",
            message="m",
            quality_score=0.9,
            session_id="s",
            emitted_at=_now() - timedelta(minutes=minutes),
        )
    memory.register_user_reply("s", now=_now())
    by_topic = {r["topic_key"]: r["user_response"] for r in memory.recent()}
    assert by_topic["k3"] == "engaged"      # newest in-window → the reply target
    assert by_topic["k20"] == "unknown"     # second in-window stays unresolved


def test_emission_memory_get_by_id(tmp_path):
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    record = memory.record(
        initiative_type="memory_followup",
        topic_key="k",
        message="m",
        quality_score=0.8,
        session_id="default",
    )
    assert memory.get(record["id"])["session_id"] == "default"
    assert memory.get("nope") is None


def test_emission_memory_set_response_and_persist(tmp_path):
    path = tmp_path / "emissions.json"
    record = InitiativeEmissionMemory(path).record(
        initiative_type="memory_followup",
        topic_key="k",
        message="m",
        quality_score=0.8,
    )
    memory = InitiativeEmissionMemory(path)  # reload from disk
    assert memory.set_response(record["id"], "engaged") is True
    assert memory.recent()[0]["user_response"] == "engaged"
    with pytest.raises(ValueError):
        memory.set_response(record["id"], "not-a-response")


# ── quality gate scoring ─────────────────────────────────────────────────────


def test_gate_passes_grounded_recent_evidence():
    gate = InitiativeQualityGate()
    score = gate.evaluate(_evidence_candidate(), now=_now())
    assert score.passed is True
    assert score.total >= DEFAULT_THRESHOLD
    assert score.relevance == 1.0
    assert score.recency == 1.0


def test_gate_suppresses_missing_evidence():
    gate = InitiativeQualityGate()
    bare = InitiativeCandidate(
        type="memory_followup", priority="low", reason="r", session_id="s", message="hi"
    )
    score = gate.evaluate(bare, now=_now())
    assert score.passed is False
    assert score.hard_reason == "no evidence"


def test_gate_suppresses_generic_excerpt():
    gate = InitiativeQualityGate()
    score = gate.evaluate(_evidence_candidate(excerpt="ok"), now=_now())
    assert score.passed is False
    assert score.hard_reason == "evidence too generic"


def test_gate_suppresses_unsafe_language_via_safety_floor():
    gate = InitiativeQualityGate()
    score = gate.evaluate(
        _evidence_candidate(message="You clearly have depression and you always avoid it."),
        now=_now(),
    )
    assert score.safety < SAFETY_FLOOR
    assert score.passed is False


def test_gate_suppresses_repeat_topic_within_window(tmp_path):
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    memory.record(
        initiative_type="memory_followup",
        topic_key="memory_followup:mem-1",
        message="Earlier...",
        quality_score=0.9,
        emitted_at=_now() - timedelta(days=1),
    )
    gate = InitiativeQualityGate(memory)
    score = gate.evaluate(_evidence_candidate(), now=_now())
    assert score.novelty == 0.0
    assert score.passed is False
    assert "similar initiative" in (score.hard_reason or "")


def test_gate_recency_decays_for_stale_evidence():
    gate = InitiativeQualityGate()
    fresh = gate.evaluate(_evidence_candidate(observed_hours_ago=14), now=_now())
    stale = gate.evaluate(_evidence_candidate(observed_hours_ago=200), now=_now())
    assert stale.recency < fresh.recency


def test_record_emission_persists_topic(tmp_path):
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    gate = InitiativeQualityGate(memory)
    candidate = _evidence_candidate()
    score = gate.evaluate(candidate, now=_now())
    gate.record_emission(candidate, score)
    assert memory.seen_topic_within("memory_followup:mem-1", now=_now()) is True


def test_record_emission_persists_dimension_breakdown(tmp_path):
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    gate = InitiativeQualityGate(memory)
    candidate = _evidence_candidate()
    score = gate.evaluate(candidate, now=_now())
    gate.record_emission(candidate, score)

    dims = memory.recent()[0]["dimensions"]
    assert dims["relevance"] == score.relevance
    assert dims["timing"] == score.timing
    assert dims["recency"] == score.recency
    assert dims["novelty"] == score.novelty
    assert dims["safety"] == score.safety
    assert dims["feedback_factor"] == score.feedback_factor


# ── feedback consumption (learning loop) ─────────────────────────────────────


def _seed_feedback(memory, responses, *, initiative_type="memory_followup"):
    for index, response in enumerate(responses):
        record = memory.record(
            initiative_type=initiative_type,
            topic_key=f"{initiative_type}:seed{index}",
            message="m",
            quality_score=0.9,
            session_id="s",
            emitted_at=_now() - timedelta(days=1),
        )
        memory.set_response(record["id"], response)


def test_feedback_counts_windowed(tmp_path):
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    _seed_feedback(memory, ["ignored", "ignored", "engaged"])
    counts = memory.feedback_counts(initiative_type="memory_followup", now=_now())
    assert counts == {"engaged": 1, "ignored": 2, "negative": 0}


def test_ignored_streak_dampens_and_suppresses(tmp_path):
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    _seed_feedback(memory, ["ignored", "ignored"])
    gate = InitiativeQualityGate(memory)

    score = gate.evaluate(_evidence_candidate(source_id="fresh"), now=_now())
    assert score.feedback_factor == IGNORED_DAMPEN_FACTOR
    assert score.passed is False  # a would-be-passing candidate drops under threshold


def test_engagement_clears_dampening(tmp_path):
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    _seed_feedback(memory, ["ignored", "ignored", "engaged"])
    gate = InitiativeQualityGate(memory)

    score = gate.evaluate(_evidence_candidate(source_id="fresh"), now=_now())
    assert score.feedback_factor == 1.0
    assert score.passed is True


def test_negative_feedback_hard_suppresses(tmp_path):
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    _seed_feedback(memory, ["negative"])
    gate = InitiativeQualityGate(memory)

    score = gate.evaluate(_evidence_candidate(source_id="fresh"), now=_now())
    assert score.passed is False
    assert score.hard_reason == "negative feedback on this initiative type"


def test_single_ignore_does_not_dampen(tmp_path):
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    _seed_feedback(memory, ["ignored"])  # below the streak threshold
    gate = InitiativeQualityGate(memory)

    score = gate.evaluate(_evidence_candidate(source_id="fresh"), now=_now())
    assert score.feedback_factor == 1.0
    assert score.passed is True


# ── service integration ──────────────────────────────────────────────────────


def _policy(**overrides):
    values = {
        "enabled": True,
        "daily_limit": 2,
        "timezone": "UTC",
        "daily_greeting_start": "07:00",
        "daily_greeting_end": "11:00",
        "quiet_hours_start": "22:00",
        "quiet_hours_end": "08:00",
        "focus_mode": False,
        "do_not_disturb": False,
        "min_spacing_minutes": 240,
    }
    values.update(overrides)
    return InitiativePolicy(**values)


def _gated_service(tmp_path):
    store = InitiativeStore(tmp_path / "init.json")
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    gate = InitiativeQualityGate(memory)
    return InitiativeService(store=store, quality_gate=gate), memory


def test_service_emits_evidence_candidate_and_records_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "initiative_quality_gate_enabled", True)
    service, memory = _gated_service(tmp_path)
    bus = AsyncMock()

    decision = asyncio.run(
        service.emit(
            _evidence_candidate(),
            event_bus=bus,
            policy=_policy(),
            media_session={"mic_state": "idle", "speaking_state": "idle"},
            now=_now(),
        )
    )
    assert decision.allowed is True
    assert memory.seen_topic_within("memory_followup:mem-1", now=_now()) is True


def test_service_second_emit_suppressed_by_novelty(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "initiative_quality_gate_enabled", True)
    service, _ = _gated_service(tmp_path)
    bus = AsyncMock()

    asyncio.run(
        service.emit(
            _evidence_candidate(),
            event_bus=bus,
            policy=_policy(),
            media_session={"mic_state": "idle", "speaking_state": "idle"},
            now=_now(),
        )
    )
    second = asyncio.run(
        service.emit(
            _evidence_candidate(message="Different phrasing, same source."),
            event_bus=bus,
            policy=_policy(),
            media_session={"mic_state": "idle", "speaking_state": "idle"},
            now=_now() + timedelta(minutes=1),
        )
    )
    assert second.allowed is False
    assert "quality gate" in (second.suppressed_reason or "")


def test_service_reply_marks_emitted_initiative_engaged(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "initiative_quality_gate_enabled", True)
    service, memory = _gated_service(tmp_path)
    bus = AsyncMock()

    asyncio.run(
        service.emit(
            _evidence_candidate(),
            event_bus=bus,
            policy=_policy(),
            media_session={"mic_state": "idle", "speaking_state": "idle"},
            now=_now(),
        )
    )
    assert memory.recent()[0]["user_response"] == "unknown"

    changed = service.register_user_reply("s", now=_now() + timedelta(minutes=2))
    assert len(changed) == 1
    assert memory.recent()[0]["user_response"] == "engaged"


def test_service_register_user_reply_without_gate_is_noop(tmp_path):
    from app.initiative.service import InitiativeService
    from app.initiative.store import InitiativeStore

    service = InitiativeService(store=InitiativeStore(tmp_path / "init.json"))
    assert service.register_user_reply("s") == []


def test_service_timer_candidate_bypasses_gate(tmp_path, monkeypatch):
    """A candidate without evidence must not be touched by the quality gate."""
    monkeypatch.setattr(settings, "initiative_quality_gate_enabled", True)
    service, _ = _gated_service(tmp_path)

    candidate = service.build_daily_greeting_candidate(
        session_id="default", now=datetime(2026, 7, 11, 9, 0)
    )
    assert candidate is not None and candidate.evidence is None

    decision = service.can_emit(
        candidate,
        policy=_policy(),
        media_session={"mic_state": "idle", "speaking_state": "idle"},
        now=datetime(2026, 7, 11, 9, 0),
    )
    assert decision.allowed is True


def test_service_gate_disabled_skips_scoring(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "initiative_quality_gate_enabled", False)
    service, memory = _gated_service(tmp_path)

    # Even a generic excerpt (which the gate would reject) passes when disabled.
    decision = service.can_emit(
        _evidence_candidate(excerpt="no"),
        policy=_policy(),
        media_session={"mic_state": "idle", "speaking_state": "idle"},
        now=_now(),
    )
    assert decision.allowed is True


# ── negative-feedback producer (endpoints) ───────────────────────────────────


def _seed_emission(memory):
    return memory.record(
        initiative_type="memory_followup",
        topic_key="memory_followup:mem-1",
        message="Earlier you mentioned Dana...",
        quality_score=0.9,
        session_id="s",
        emitted_at=_now(),
    )


def test_feedback_endpoint_marks_negative(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api import v2 as api_v2
    from app.api.main import app

    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    record = _seed_emission(memory)
    monkeypatch.setattr(api_v2, "initiative_emission_memory", memory)

    client = TestClient(app)
    resp = client.post(f"/api/v2/initiative/emissions/{record['id']}/feedback?response=negative")
    assert resp.status_code == 200
    assert resp.json()["response"] == "negative"
    assert memory.recent()[0]["user_response"] == "negative"


def test_feedback_endpoint_unknown_id_is_404(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api import v2 as api_v2
    from app.api.main import app

    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    monkeypatch.setattr(api_v2, "initiative_emission_memory", memory)

    client = TestClient(app)
    resp = client.post("/api/v2/initiative/emissions/does-not-exist/feedback?response=negative")
    assert resp.status_code == 404


def test_feedback_endpoint_rejects_invalid_response(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api import v2 as api_v2
    from app.api.main import app

    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    record = _seed_emission(memory)
    monkeypatch.setattr(api_v2, "initiative_emission_memory", memory)

    client = TestClient(app)
    resp = client.post(f"/api/v2/initiative/emissions/{record['id']}/feedback?response=unknown")
    assert resp.status_code == 422  # not an allowed response value


def test_list_emissions_endpoint(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.api import v2 as api_v2
    from app.api.main import app

    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    _seed_emission(memory)
    monkeypatch.setattr(api_v2, "initiative_emission_memory", memory)

    client = TestClient(app)
    resp = client.get("/api/v2/initiative/emissions?limit=5")
    assert resp.status_code == 200
    emissions = resp.json()["emissions"]
    assert len(emissions) == 1
    assert emissions[0]["type"] == "memory_followup"


def test_negative_from_endpoint_suppresses_type_end_to_end(tmp_path, monkeypatch):
    """Producer -> consumer: marking an emission negative quiets its type."""
    monkeypatch.setattr(settings, "initiative_quality_gate_enabled", True)
    memory = InitiativeEmissionMemory(tmp_path / "emissions.json")
    record = _seed_emission(memory)
    gate = InitiativeQualityGate(memory)

    # Before feedback, a fresh candidate of this type would pass.
    assert gate.evaluate(_evidence_candidate(source_id="other"), now=_now()).passed is True

    memory.set_response(record["id"], "negative")

    after = gate.evaluate(_evidence_candidate(source_id="other"), now=_now())
    assert after.passed is False
    assert after.hard_reason == "negative feedback on this initiative type"

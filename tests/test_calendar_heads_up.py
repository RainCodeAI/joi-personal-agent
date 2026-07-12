"""Tests for the calendar_heads_up initiative type and its scheduler tick."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.initiative.emission_memory import InitiativeEmissionMemory
from app.initiative.policy import ALLOWED_INITIATIVE_TYPES, InitiativePolicy
from app.initiative.quality import InitiativeQualityGate
from app.initiative.scheduler import InitiativeScheduler
from app.initiative.service import InitiativeService
from app.initiative.store import InitiativeStore


def _now():
    return datetime(2026, 7, 11, 15, 0, tzinfo=timezone.utc)


def _event(event_id, summary, minutes_from_now, *, all_day=False):
    start = _now() + timedelta(minutes=minutes_from_now)
    start_block = {"date": start.date().isoformat()} if all_day else {"dateTime": start.isoformat()}
    return {"id": event_id, "summary": summary, "start": start_block}


def _service(tmp_path, *, gate=True):
    store = InitiativeStore(tmp_path / "init.json")
    quality_gate = None
    if gate:
        quality_gate = InitiativeQualityGate(InitiativeEmissionMemory(tmp_path / "emissions.json"))
    return InitiativeService(store=store, quality_gate=quality_gate)


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


# ── builder ──────────────────────────────────────────────────────────────────


def test_builder_picks_soonest_event_in_window(tmp_path):
    service = _service(tmp_path)
    candidate = service.build_calendar_heads_up_candidate(
        events=[_event("e1", "Later thing", 60), _event("e2", "Sync with Dana", 30)],
        now=_now(),
    )
    assert candidate is not None
    assert candidate.type == "calendar_heads_up"
    assert "Sync with Dana" in candidate.message
    assert candidate.evidence.source_type == "calendar"
    assert candidate.evidence.source_id == "e2"
    assert candidate.evidence.topic_key == "calendar_heads_up:e2"


def test_builder_skips_events_outside_window(tmp_path):
    service = _service(tmp_path)
    candidate = service.build_calendar_heads_up_candidate(
        events=[_event("e1", "Too soon", 5), _event("e2", "Too far", 200)],
        now=_now(),
    )
    assert candidate is None


def test_builder_skips_all_day_events(tmp_path):
    service = _service(tmp_path)
    candidate = service.build_calendar_heads_up_candidate(
        events=[_event("e1", "All-day offsite", 30, all_day=True)],
        now=_now(),
    )
    assert candidate is None


def test_builder_returns_none_without_events(tmp_path):
    service = _service(tmp_path)
    assert service.build_calendar_heads_up_candidate(events=[], now=_now()) is None


# ── quality gate ─────────────────────────────────────────────────────────────


def test_gate_passes_grounded_calendar_candidate(tmp_path):
    service = _service(tmp_path)
    candidate = service.build_calendar_heads_up_candidate(
        events=[_event("e2", "Sync with Dana", 30)], now=_now()
    )
    score = InitiativeQualityGate().evaluate(candidate, now=_now())
    assert score.passed is True
    assert score.relevance == 1.0


# ── service integration (diagnostics-only posture) ───────────────────────────


def test_diagnostics_only_suppressed_when_type_not_allowed(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "initiative_quality_gate_enabled", True)
    service = _service(tmp_path)
    candidate = service.build_calendar_heads_up_candidate(
        events=[_event("e2", "Sync with Dana", 30)], now=_now()
    )
    allowed = tuple(t for t in ALLOWED_INITIATIVE_TYPES if t != "calendar_heads_up")

    decision = service.can_emit(
        candidate,
        policy=_policy(allowed_types=allowed),
        media_session={"mic_state": "idle", "speaking_state": "idle"},
        now=_now(),
    )
    assert decision.allowed is False
    assert decision.suppressed_reason == "initiative type disabled: calendar_heads_up"


def test_passes_gate_and_policy_when_type_enabled(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "initiative_quality_gate_enabled", True)
    service = _service(tmp_path)
    candidate = service.build_calendar_heads_up_candidate(
        events=[_event("e2", "Sync with Dana", 30)], now=_now()
    )

    decision = service.can_emit(
        candidate,
        policy=_policy(allowed_types=ALLOWED_INITIATIVE_TYPES),
        media_session={"mic_state": "idle", "speaking_state": "idle"},
        now=_now(),
    )
    assert decision.allowed is True


# ── endpoint ─────────────────────────────────────────────────────────────────


def test_endpoint_reports_no_event_when_calendar_unavailable(tmp_path):
    from fastapi.testclient import TestClient

    from app.api.main import app

    client = TestClient(app)
    # No calendar auth in the test env → builder finds no events.
    response = client.post("/api/v2/initiative/calendar-heads-up")
    assert response.status_code == 200
    body = response.json()
    assert body["decision"]["candidate"] is None
    assert body["quality"] is None


# ── scheduler tick ───────────────────────────────────────────────────────────


def _scheduler_with_service(service):
    return InitiativeScheduler(
        service,
        event_bus=MagicMock(),
        memory_store=MagicMock(),
        media_sessions=MagicMock(),
    )


def test_calendar_tick_emits_when_candidate_built(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "enable_proactive_messaging", True)
    monkeypatch.setattr(settings, "initiative_enabled", True)

    candidate = _service(tmp_path).build_calendar_heads_up_candidate(
        events=[_event("e2", "Sync with Dana", 30)], now=_now()
    )
    service = MagicMock()
    service.build_calendar_heads_up_candidate = MagicMock(return_value=candidate)
    service.emit = AsyncMock(return_value=SimpleNamespace(allowed=True, suppressed_reason=None))

    asyncio.run(_scheduler_with_service(service)._calendar_tick())

    service.build_calendar_heads_up_candidate.assert_called_once()
    service.emit.assert_awaited_once()


def test_calendar_tick_noops_without_candidate(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "enable_proactive_messaging", True)
    monkeypatch.setattr(settings, "initiative_enabled", True)

    service = MagicMock()
    service.build_calendar_heads_up_candidate = MagicMock(return_value=None)
    service.emit = AsyncMock()

    asyncio.run(_scheduler_with_service(service)._calendar_tick())

    service.emit.assert_not_awaited()


def test_calendar_tick_skipped_when_initiatives_disabled(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "initiative_enabled", False)

    service = MagicMock()
    service.build_calendar_heads_up_candidate = MagicMock(return_value=None)

    asyncio.run(_scheduler_with_service(service)._calendar_tick())

    service.build_calendar_heads_up_candidate.assert_not_called()


def test_calendar_heads_up_in_default_allowed_types():
    """Taken live: the default policy now permits calendar_heads_up."""
    policy = InitiativePolicy.from_settings()
    assert "calendar_heads_up" in policy.allowed_types


# ── throttle exemptions ──────────────────────────────────────────────────────


def _cal_candidate(service, event_id="e2", minutes=30):
    return service.build_calendar_heads_up_candidate(
        events=[_event(event_id, "Sync with Dana", minutes)], now=_now()
    )


def _idle():
    return {"mic_state": "idle", "speaking_state": "idle"}


def test_heads_up_bypasses_min_spacing(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "initiative_quality_gate_enabled", True)
    service = _service(tmp_path)
    # A greeting fired one minute ago would normally trip the 4-hour spacing rule.
    service.store.record_emitted(
        initiative_type="daily_greeting",
        session_id="default",
        message="Morning.",
        reason="test",
        emitted_at=_now() - timedelta(minutes=1),
    )
    decision = service.can_emit(
        _cal_candidate(service), policy=_policy(), media_session=_idle(), now=_now()
    )
    assert decision.allowed is True


def test_second_event_same_day_allowed_with_gate(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "initiative_quality_gate_enabled", True)
    service = _service(tmp_path)
    # A heads-up for a different event already fired today.
    service.store.record_emitted(
        initiative_type="calendar_heads_up",
        session_id="default",
        message="Earlier event.",
        reason="test",
        emitted_at=_now() - timedelta(hours=1),
    )
    decision = service.can_emit(
        _cal_candidate(service, event_id="later"),
        policy=_policy(),
        media_session=_idle(),
        now=_now(),
    )
    assert decision.allowed is True  # per-event dedup, not per-day


def test_second_event_blocked_without_gate(tmp_path):
    service = _service(tmp_path, gate=False)  # no per-event dedup available
    service.store.record_emitted(
        initiative_type="calendar_heads_up",
        session_id="default",
        message="Earlier event.",
        reason="test",
        emitted_at=_now() - timedelta(hours=1),
    )
    decision = service.can_emit(
        _cal_candidate(service, event_id="later"),
        policy=_policy(),
        media_session=_idle(),
        now=_now(),
    )
    assert decision.allowed is False
    assert "already emitted today" in (decision.suppressed_reason or "")


def test_heads_up_still_bounded_by_daily_limit(tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "initiative_quality_gate_enabled", True)
    service = _service(tmp_path)
    for i in range(2):
        service.store.record_emitted(
            initiative_type="daily_greeting",
            session_id="default",
            message="m",
            reason="test",
            emitted_at=_now() - timedelta(minutes=10 * (i + 1)),
        )
    decision = service.can_emit(
        _cal_candidate(service), policy=_policy(daily_limit=2), media_session=_idle(), now=_now()
    )
    assert decision.allowed is False
    assert decision.suppressed_reason == "daily limit reached"

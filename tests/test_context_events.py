from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import settings
from app.context_events.service import ContextEventService
from app.context_events.store import ContextEventStore
from app.context_events.feedback import ContextFeedbackStore
from app.initiative.scheduler import InitiativeScheduler
from app.initiative.policy import InitiativePolicy


def _service(tmp_path) -> ContextEventService:
    return ContextEventService(
        ContextEventStore(tmp_path / "context_events.json"),
        ContextFeedbackStore(tmp_path / "context_feedback.json"),
    )


def test_context_event_buffer_defaults_to_commentary_off(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "context_commentary_enabled", False)
    service = _service(tmp_path)

    decision = service.observe(
        source="screen",
        kind="manual_screen_capture",
        category="work_activity",
        confidence=0.95,
        sensitivity="private",
        payload={"application": "Visual Studio Code", "data_url": "must-not-store"},
    )

    assert decision.accepted is True
    assert decision.commentary_eligible is False
    assert decision.queued is False
    assert decision.event.payload == {"application": "Visual Studio Code"}
    assert service.store.recent()[0]["kind"] == "manual_screen_capture"


def test_active_flow_observations_do_not_queue_duplicate_commentary(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "context_commentary_enabled", True)
    service = _service(tmp_path)

    decision = service.observe(
        source="screen",
        kind="manual_screen_capture",
        category="work_activity",
        confidence=0.95,
        sensitivity="private",
        payload={"description": "a code editor", "user_initiated": True},
    )

    assert decision.accepted is True
    assert decision.queued is False
    assert "handled by active flow" in decision.reason


def test_context_event_deduplicates_within_policy_window(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "context_dedup_minutes", 10)
    service = _service(tmp_path)
    now = datetime(2026, 6, 20, 20, 0, tzinfo=timezone.utc)
    kwargs = {
        "source": "presence",
        "kind": "user_returned",
        "category": "wellbeing",
        "confidence": 0.9,
        "sensitivity": "private",
        "payload": {"state": "returned"},
    }

    first = service.observe(**kwargs, now=now)
    duplicate = service.observe(**kwargs, now=now + timedelta(minutes=2))

    assert first.accepted is True
    assert duplicate.accepted is False
    assert duplicate.reason == "duplicate context event"
    assert len(service.store.recent(now=now + timedelta(minutes=2))) == 1


def test_context_event_rejects_low_confidence(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "context_min_confidence", 0.8)
    service = _service(tmp_path)

    decision = service.observe(
        source="camera",
        kind="possible_tension",
        category="wellbeing",
        confidence=0.55,
        sensitivity="sensitive",
    )

    assert decision.accepted is False
    assert decision.reason == "confidence below threshold"
    assert service.store.recent() == []


def test_context_event_expiry_prunes_persisted_buffer(tmp_path) -> None:
    service = _service(tmp_path)
    now = datetime(2026, 6, 20, 20, 0, tzinfo=timezone.utc)
    service.observe(
        source="screen",
        kind="manual_screen_capture",
        category="work_activity",
        confidence=0.95,
        sensitivity="private",
        ttl_seconds=30,
        now=now,
    )

    assert service.store.recent(now=now + timedelta(seconds=31)) == []
    restored = ContextEventStore(tmp_path / "context_events.json")
    assert restored.recent(now=now + timedelta(seconds=31)) == []


def test_appearance_and_social_categories_default_off(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "context_commentary_enabled", True)
    monkeypatch.setattr(
        settings,
        "context_allowed_categories",
        "work_activity,wellbeing,entertainment,reminders",
    )
    service = _service(tmp_path)

    appearance = service.observe(
        source="camera",
        kind="appearance_change",
        category="appearance",
        confidence=0.99,
        sensitivity="private",
    )

    assert appearance.accepted is True
    assert appearance.commentary_eligible is False
    assert "category disabled" in appearance.reason


def test_eligible_context_event_queues_restrained_candidate(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "context_commentary_enabled", True)
    service = _service(tmp_path)

    decision = service.observe(
        source="screen",
        kind="manual_screen_capture",
        category="work_activity",
        confidence=0.98,
        sensitivity="private",
        payload={"description": "a code editor showing a traceback"},
    )
    candidate = service.build_commentary_candidate(decision.event.event_id)

    assert decision.queued is True
    assert candidate is not None
    assert candidate.type == "context_commentary"
    assert candidate.context_event_id == decision.event.event_id
    assert "traceback" in candidate.message
    assert service.store.get(decision.event.event_id)["commentary_status"] == "queued"


def test_context_feedback_blocks_kind_and_applies_category_cooldown(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "context_commentary_enabled", True)
    service = _service(tmp_path)
    first = service.observe(
        source="presence",
        kind="user_returned",
        category="wellbeing",
        confidence=0.95,
        sensitivity="private",
        payload={"state": "returned"},
    )
    service.record_feedback(first.event.event_id, "never_comment")

    blocked = service.observe(
        source="presence",
        kind="user_returned",
        category="wellbeing",
        confidence=0.95,
        sensitivity="private",
        payload={"state": "returned", "sequence": 2},
    )

    assert blocked.accepted is True
    assert blocked.commentary_eligible is False
    assert "blocked by feedback" in blocked.reason

    screen = service.observe(
        source="screen",
        kind="manual_screen_capture",
        category="work_activity",
        confidence=0.95,
        sensitivity="private",
        payload={"description": "a spreadsheet"},
    )
    service.record_feedback(screen.event.event_id, "too_much")
    cooled = service.observe(
        source="screen",
        kind="active_application_changed",
        category="work_activity",
        confidence=0.95,
        sensitivity="private",
        payload={"application": "Excel"},
    )

    assert cooled.commentary_eligible is False
    assert "cooldown active" in cooled.reason


def test_context_delivery_status_tracks_retry_and_emission(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "context_commentary_enabled", True)
    service = _service(tmp_path)
    decision = service.observe(
        source="presence",
        kind="user_returned",
        category="wellbeing",
        confidence=0.95,
        sensitivity="private",
    )

    service.mark_delivery(
        decision.event.event_id,
        emitted=False,
        reason="mic state is recording",
        retryable=True,
    )
    assert service.store.get(decision.event.event_id)["commentary_status"] == "queued"

    service.mark_delivery(decision.event.event_id, emitted=True)
    emitted = service.store.get(decision.event.event_id)
    assert emitted["commentary_status"] == "emitted"
    assert datetime.fromisoformat(emitted["expires_at"]) > (
        datetime.now(timezone.utc) + timedelta(days=6)
    )


def test_commentary_claim_is_atomic_and_stale_claims_recover(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "context_commentary_enabled", True)
    service = _service(tmp_path)
    observed = service.observe(
        source="presence",
        kind="user_returned",
        category="wellbeing",
        confidence=0.95,
        sensitivity="private",
    )
    event_id = observed.event.event_id

    assert service.build_commentary_candidate(event_id, claim=True) is not None
    assert service.build_commentary_candidate(event_id, claim=True) is None

    stale_at = datetime.now(timezone.utc) - timedelta(minutes=11)
    service.store.update(
        event_id,
        {
            "commentary_status": "delivering",
            "commentary_updated_at": stale_at.isoformat(),
        },
    )

    assert service.store.pending(limit=1)[0]["event_id"] == event_id
    assert service.store.get(event_id)["commentary_status"] == "queued"


def test_context_feedback_is_idempotent_per_event(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "context_commentary_enabled", True)
    service = _service(tmp_path)
    observed = service.observe(
        source="presence",
        kind="user_returned",
        category="wellbeing",
        confidence=0.95,
        sensitivity="private",
    )

    first = service.record_feedback(observed.event.event_id, "useful")
    duplicate = service.record_feedback(observed.event.event_id, "useful")

    assert first["action"] == "useful"
    assert duplicate["duplicate"] is True
    assert service.feedback_store.diagnostics()["feedback_records"] == 1


def test_context_scheduler_retries_busy_turn_then_marks_emitted(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "context_commentary_enabled", True)
    context_service = _service(tmp_path)
    observed = context_service.observe(
        source="presence",
        kind="user_returned",
        category="wellbeing",
        confidence=0.95,
        sensitivity="private",
    )
    decisions = [
        type("Decision", (), {"allowed": False, "suppressed_reason": "mic state is recording"})(),
        type("Decision", (), {"allowed": True, "suppressed_reason": None})(),
    ]

    class FakeInitiativeService:
        async def emit(self, candidate, **kwargs):
            return decisions.pop(0)

    class FakeMediaSessions:
        def get(self, session_id):
            return {"mic_state": "idle", "speaking_state": "idle"}

    scheduler = InitiativeScheduler(
        FakeInitiativeService(),
        object(),
        object(),
        FakeMediaSessions(),
        context_events=context_service,
    )
    monkeypatch.setattr(scheduler, "_is_ready", lambda: True)

    import asyncio

    asyncio.run(scheduler._context_tick())
    assert (
        context_service.store.get(observed.event.event_id)["commentary_status"]
        == "queued"
    )

    asyncio.run(scheduler._context_tick())
    assert (
        context_service.store.get(observed.event.event_id)["commentary_status"]
        == "emitted"
    )


def test_commentary_toggle_authorizes_initiative_type_for_legacy_settings(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "context_commentary_enabled", True)
    monkeypatch.setattr(
        settings,
        "initiative_allowed_types",
        "daily_greeting,return_after_absence",
    )

    policy = InitiativePolicy.from_settings()

    assert "context_commentary" in policy.allowed_types

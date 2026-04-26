import asyncio
from datetime import datetime

from app.initiative.policy import ALLOWED_INITIATIVE_TYPES, InitiativePolicy, is_quiet_time
from app.initiative.service import InitiativeService
from app.initiative.store import InitiativeStore


def _service(tmp_path):
    return InitiativeService(InitiativeStore(tmp_path / "initiative_state.json"))


def _policy(**overrides):
    values = {
        "enabled": True,
        "daily_limit": 2,
        "timezone": "America/Toronto",
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


def test_quiet_hours_cross_midnight():
    assert is_quiet_time(datetime(2026, 4, 25, 23, 0), "22:00", "08:00") is True
    assert is_quiet_time(datetime(2026, 4, 25, 7, 30), "22:00", "08:00") is True
    assert is_quiet_time(datetime(2026, 4, 25, 12, 0), "22:00", "08:00") is False


def test_daily_greeting_suppressed_by_dnd(tmp_path):
    service = _service(tmp_path)
    candidate = service.build_daily_greeting_candidate(
        session_id="default",
        now=datetime(2026, 4, 25, 10, 0),
    )
    assert candidate is not None

    decision = service.can_emit(
        candidate,
        policy=_policy(do_not_disturb=True),
        media_session={"mic_state": "idle", "speaking_state": "idle"},
        now=datetime(2026, 4, 25, 10, 0),
    )

    assert decision.allowed is False
    assert decision.suppressed_reason == "do not disturb enabled"


def test_daily_greeting_emits_once_per_day(tmp_path):
    service = _service(tmp_path)
    candidate = service.build_daily_greeting_candidate(
        session_id="default",
        now=datetime(2026, 4, 25, 10, 0),
    )
    assert candidate is not None

    first = service.can_emit(
        candidate,
        policy=_policy(),
        media_session={"mic_state": "idle", "speaking_state": "idle"},
        now=datetime(2026, 4, 25, 10, 0),
    )
    assert first.allowed is True
    service.store.record_emitted(
        initiative_type=candidate.type,
        session_id=candidate.session_id,
        message=candidate.message,
        reason=candidate.reason,
        emitted_at=datetime(2026, 4, 25, 10, 0),
    )

    second = service.can_emit(
        candidate,
        policy=_policy(),
        media_session={"mic_state": "idle", "speaking_state": "idle"},
        now=datetime(2026, 4, 25, 14, 30),
    )

    assert second.allowed is False
    assert second.suppressed_reason == "daily_greeting already emitted today"


def test_daily_greeting_only_inside_window(tmp_path):
    service = _service(tmp_path)

    assert service.build_daily_greeting_candidate(
        session_id="default",
        now=datetime(2026, 4, 25, 6, 59),
    ) is None
    assert service.build_daily_greeting_candidate(
        session_id="default",
        now=datetime(2026, 4, 25, 11, 0),
    ) is None
    assert service.build_daily_greeting_candidate(
        session_id="default",
        now=datetime(2026, 4, 25, 8, 0),
    ) is not None


def test_emit_records_and_publishes(tmp_path):
    service = _service(tmp_path)
    candidate = service.build_daily_greeting_candidate(
        session_id="session-chat",
        now=datetime(2026, 4, 25, 10, 0),
    )
    assert candidate is not None
    published = []
    messages = []

    class FakeBus:
        async def publish(self, event, payload, session_id=None, source="system"):
            published.append((event, payload, session_id, source))

    class FakeMemory:
        def add_chat_message(self, session_id, role, content):
            messages.append((session_id, role, content))

    decision = asyncio.run(
        service.emit(
            candidate,
            event_bus=FakeBus(),
            memory_store=FakeMemory(),
            policy=_policy(),
            media_session={"mic_state": "idle", "speaking_state": "idle"},
            now=datetime(2026, 4, 25, 10, 0),
        )
    )

    assert decision.allowed is True
    assert service.store.daily_count("2026-04-25") == 1
    assert messages == [("session-chat", "assistant", candidate.message)]
    assert published[0][0] == "initiative.emitted"


def test_return_after_absence_requires_threshold(tmp_path):
    service = _service(tmp_path)
    service.record_absence_started(
        session_id="default",
        source="test",
        now=datetime(2026, 4, 25, 10, 0),
    )

    early = service.build_return_after_absence_candidate(
        session_id="default",
        now=datetime(2026, 4, 25, 10, 30),
    )
    eligible = service.build_return_after_absence_candidate(
        session_id="default",
        now=datetime(2026, 4, 25, 10, 46),
    )

    assert early is None
    assert eligible is not None
    assert eligible.type == "return_after_absence"
    assert "46 minutes away" in eligible.reason


def test_user_activity_clears_absence(tmp_path):
    service = _service(tmp_path)
    service.record_absence_started(
        session_id="default",
        source="test",
        now=datetime(2026, 4, 25, 10, 0),
    )
    service.record_user_activity(
        session_id="default",
        source="chat",
        clear_absence=True,
        now=datetime(2026, 4, 25, 10, 20),
    )

    candidate = service.build_return_after_absence_candidate(
        session_id="default",
        now=datetime(2026, 4, 25, 11, 20),
    )

    assert candidate is None


# ---------------------------------------------------------------------------
# Daily limit across multiple trigger types
# ---------------------------------------------------------------------------

def test_daily_limit_across_trigger_types(tmp_path):
    """Emitting two distinct types exhausts the daily budget; a third is blocked."""
    service = _service(tmp_path)
    now = datetime(2026, 4, 25, 10, 0)
    day = "2026-04-25"

    # Record two emissions of different types directly (bypass spacing gate).
    service.store.record_emitted(
        initiative_type="daily_greeting",
        session_id="s",
        message="Morning.",
        reason="test",
        emitted_at=datetime(2026, 4, 25, 10, 0),
    )
    service.store.record_emitted(
        initiative_type="return_after_absence",
        session_id="s",
        message="Welcome back.",
        reason="test",
        emitted_at=datetime(2026, 4, 25, 14, 30),
    )

    assert service.store.daily_count(day) == 2

    # A third candidate of any type should be blocked by "daily limit reached".
    service.store.record_user_activity(
        session_id="s", source="chat",
        observed_at=datetime(2026, 4, 25, 8, 0),
    )
    # Build prolonged_silence candidate (silent since 08:00, now 18:00 -> 600 min)
    candidate = service.build_prolonged_silence_candidate(
        session_id="s",
        policy=_policy(daily_limit=2, silence_threshold_minutes=90,
                       allowed_types=ALLOWED_INITIATIVE_TYPES),
        now=datetime(2026, 4, 25, 18, 0),
    )
    assert candidate is not None

    decision = service.can_emit(
        candidate,
        policy=_policy(daily_limit=2, allowed_types=ALLOWED_INITIATIVE_TYPES),
        media_session={"mic_state": "idle", "speaking_state": "idle"},
        now=datetime(2026, 4, 25, 18, 0),
    )

    assert decision.allowed is False
    assert decision.suppressed_reason == "daily limit reached"


def test_daily_limit_resets_next_day(tmp_path):
    """Emissions recorded on day N do not count toward day N+1's limit."""
    service = _service(tmp_path)
    for hour in range(2):
        service.store.record_emitted(
            initiative_type="daily_greeting" if hour == 0 else "return_after_absence",
            session_id="s",
            message="msg",
            reason="test",
            emitted_at=datetime(2026, 4, 25, 10 + hour, 0),
        )

    assert service.store.daily_count("2026-04-25") == 2
    assert service.store.daily_count("2026-04-26") == 0

    candidate = service.build_daily_greeting_candidate(
        session_id="s", now=datetime(2026, 4, 26, 9, 0)
    )
    assert candidate is not None
    decision = service.can_emit(
        candidate,
        policy=_policy(daily_limit=2),
        media_session={"mic_state": "idle", "speaking_state": "idle"},
        now=datetime(2026, 4, 26, 9, 0),
    )
    assert decision.allowed is True


# ---------------------------------------------------------------------------
# Quiet hours - exact boundary minutes
# ---------------------------------------------------------------------------

def test_quiet_hours_exact_boundary():
    """Start time is inclusive; end time is exclusive."""
    # Cross-midnight window: 22:00-08:00
    assert is_quiet_time(datetime(2026, 4, 25, 22, 0), "22:00", "08:00") is True   # start - in
    assert is_quiet_time(datetime(2026, 4, 25, 21, 59), "22:00", "08:00") is False  # one min before start - out
    assert is_quiet_time(datetime(2026, 4, 25, 7, 59), "22:00", "08:00") is True   # one min before end - in
    assert is_quiet_time(datetime(2026, 4, 25, 8, 0), "22:00", "08:00") is False   # end - out (exclusive)
    assert is_quiet_time(datetime(2026, 4, 25, 12, 0), "22:00", "08:00") is False  # midday - out


def test_quiet_hours_same_side_window():
    """Same-day window (start < end) has its own boundary semantics."""
    # 08:00-18:00
    assert is_quiet_time(datetime(2026, 4, 25, 8, 0), "08:00", "18:00") is True    # start - in
    assert is_quiet_time(datetime(2026, 4, 25, 7, 59), "08:00", "18:00") is False  # just before start - out
    assert is_quiet_time(datetime(2026, 4, 25, 17, 59), "08:00", "18:00") is True  # one min before end - in
    assert is_quiet_time(datetime(2026, 4, 25, 18, 0), "08:00", "18:00") is False  # end - out (exclusive)


def test_quiet_hours_equal_start_end():
    """start == end means never quiet (degenerate config)."""
    assert is_quiet_time(datetime(2026, 4, 25, 12, 0), "08:00", "08:00") is False


def test_quiet_hours_suppresses_candidate(tmp_path):
    """A non-late-night candidate built during quiet hours is suppressed."""
    service = _service(tmp_path)
    candidate = service.build_daily_greeting_candidate(
        session_id="s", now=datetime(2026, 4, 25, 10, 0)
    )
    assert candidate is not None
    assert candidate is not None
    decision = service.can_emit(
        candidate,
        policy=_policy(quiet_hours_start="22:00", quiet_hours_end="08:00"),
        media_session={"mic_state": "idle", "speaking_state": "idle"},
        now=datetime(2026, 4, 25, 23, 30),
    )
    assert decision.allowed is False
    assert decision.suppressed_reason == "quiet hours active"


# ---------------------------------------------------------------------------
# Absence threshold - exact boundary
# ---------------------------------------------------------------------------

def test_absence_threshold_exact_boundary(tmp_path):
    """Candidate appears at exactly 45 min; one minute short returns None."""
    service = _service(tmp_path)
    absence_time = datetime(2026, 4, 25, 10, 0)
    service.record_absence_started(session_id="s", source="test", now=absence_time)

    # 44 minutes away - too short
    too_short = service.build_return_after_absence_candidate(
        session_id="s", now=datetime(2026, 4, 25, 10, 44)
    )
    assert too_short is None

    # Exactly 45 minutes away - at threshold
    at_threshold = service.build_return_after_absence_candidate(
        session_id="s", now=datetime(2026, 4, 25, 10, 45)
    )
    assert at_threshold is not None
    assert at_threshold.type == "return_after_absence"
    assert "45 minutes away" in at_threshold.reason


def test_prolonged_silence_threshold_boundary(tmp_path):
    """Candidate appears at exactly the silence threshold; one minute short returns None."""
    service = _service(tmp_path)
    now = datetime(2026, 4, 25, 14, 0)
    policy = _policy(silence_threshold_minutes=90, allowed_types=ALLOWED_INITIATIVE_TYPES)

    # 89 minutes of silence - too short
    service.store.record_user_activity(
        session_id="s", source="chat",
        observed_at=datetime(2026, 4, 25, 12, 31),
    )
    assert service.build_prolonged_silence_candidate(
        session_id="s", policy=policy, now=now
    ) is None

    # Exactly 90 minutes of silence - at threshold
    service.store.record_user_activity(
        session_id="s", source="chat",
        observed_at=datetime(2026, 4, 25, 12, 30),
    )
    candidate = service.build_prolonged_silence_candidate(
        session_id="s", policy=policy, now=now
    )
    assert candidate is not None
    assert candidate.type == "prolonged_silence"
    assert "90 minutes" in candidate.reason


def test_prolonged_silence_no_activity_returns_none(tmp_path):
    """No recorded activity -> no candidate (never interrupted the user cold)."""
    service = _service(tmp_path)
    candidate = service.build_prolonged_silence_candidate(
        session_id="s",
        policy=_policy(silence_threshold_minutes=90, allowed_types=ALLOWED_INITIATIVE_TYPES),
        now=datetime(2026, 4, 25, 14, 0),
    )
    assert candidate is None


# ---------------------------------------------------------------------------
# Late-night window - active / inactive + quiet-hours bypass
# ---------------------------------------------------------------------------

def test_late_night_checkin_inside_window(tmp_path):
    """Candidate is produced only while inside the late-night window."""
    service = _service(tmp_path)
    policy = _policy(
        late_night_start="22:00",
        late_night_end="01:00",
        allowed_types=ALLOWED_INITIATIVE_TYPES,
    )
    service.record_user_activity(
        session_id="s",
        source="test",
        now=datetime(2026, 4, 25, 22, 45),
    )

    inside = service.build_late_night_checkin_candidate(
        session_id="s", policy=policy, now=datetime(2026, 4, 25, 23, 0)
    )
    assert inside is not None
    assert inside.type == "late_night_checkin"

    outside = service.build_late_night_checkin_candidate(
        session_id="s", policy=policy, now=datetime(2026, 4, 25, 14, 0)
    )
    assert outside is None


def test_late_night_checkin_requires_recent_activity(tmp_path):
    service = _service(tmp_path)
    policy = _policy(
        late_night_start="22:00",
        late_night_end="01:00",
        allowed_types=ALLOWED_INITIATIVE_TYPES,
    )

    no_activity = service.build_late_night_checkin_candidate(
        session_id="s", policy=policy, now=datetime(2026, 4, 25, 23, 0)
    )
    assert no_activity is None

    service.record_user_activity(
        session_id="s",
        source="test",
        now=datetime(2026, 4, 25, 20, 30),
    )
    stale_activity = service.build_late_night_checkin_candidate(
        session_id="s", policy=policy, now=datetime(2026, 4, 25, 23, 0)
    )
    assert stale_activity is None


def test_late_night_checkin_suppressed_while_away(tmp_path):
    service = _service(tmp_path)
    policy = _policy(
        late_night_start="22:00",
        late_night_end="01:00",
        allowed_types=ALLOWED_INITIATIVE_TYPES,
    )
    service.record_user_activity(
        session_id="s",
        source="test",
        now=datetime(2026, 4, 25, 22, 45),
    )
    service.record_absence_started(
        session_id="s",
        source="test",
        now=datetime(2026, 4, 25, 22, 50),
    )

    candidate = service.build_late_night_checkin_candidate(
        session_id="s", policy=policy, now=datetime(2026, 4, 25, 23, 0)
    )
    assert candidate is None


def test_late_night_checkin_boundary(tmp_path):
    """Boundary: exactly at start (in) and exactly at end (out)."""
    service = _service(tmp_path)
    policy = _policy(
        late_night_start="22:00",
        late_night_end="01:00",
        allowed_types=ALLOWED_INITIATIVE_TYPES,
    )
    service.record_user_activity(
        session_id="s",
        source="test",
        now=datetime(2026, 4, 25, 21, 50),
    )

    at_start = service.build_late_night_checkin_candidate(
        session_id="s", policy=policy, now=datetime(2026, 4, 25, 22, 0)
    )
    assert at_start is not None

    at_end = service.build_late_night_checkin_candidate(
        session_id="s", policy=policy, now=datetime(2026, 4, 26, 1, 0)
    )
    assert at_end is None


def test_late_night_checkin_bypasses_quiet_hours(tmp_path):
    """late_night_checkin is allowed while quiet hours are active - its window IS the point."""
    service = _service(tmp_path)
    now = datetime(2026, 4, 25, 23, 30)
    policy = _policy(
        quiet_hours_start="22:00",
        quiet_hours_end="08:00",
        late_night_start="22:00",
        late_night_end="01:00",
        allowed_types=ALLOWED_INITIATIVE_TYPES,
    )

    # Verify quiet hours are actually active at this time
    assert is_quiet_time(now, "22:00", "08:00") is True
    service.record_user_activity(
        session_id="s",
        source="test",
        now=datetime(2026, 4, 25, 23, 15),
    )

    candidate = service.build_late_night_checkin_candidate(
        session_id="s", policy=policy, now=now
    )
    assert candidate is not None

    decision = service.can_emit(
        candidate,
        policy=policy,
        media_session={"mic_state": "idle", "speaking_state": "idle"},
        now=now,
    )
    assert decision.allowed is True
    assert decision.suppressed_reason is None


def test_non_late_night_type_suppressed_by_quiet_hours(tmp_path):
    """Confirm the bypass is specific to LATE_NIGHT_TYPES - other types still blocked."""
    service = _service(tmp_path)
    now = datetime(2026, 4, 25, 23, 30)
    policy = _policy(quiet_hours_start="22:00", quiet_hours_end="08:00")

    candidate = service.build_daily_greeting_candidate(session_id="s", now=datetime(2026, 4, 25, 10, 0))
    assert candidate is not None
    decision = service.can_emit(
        candidate,
        policy=policy,
        media_session={"mic_state": "idle", "speaking_state": "idle"},
        now=now,
    )
    assert decision.allowed is False
    assert decision.suppressed_reason == "quiet hours active"


# ---------------------------------------------------------------------------
# Active mic / speaking state suppression
# ---------------------------------------------------------------------------

def test_suppressed_while_mic_active(tmp_path):
    """Any non-idle mic state blocks emission."""
    service = _service(tmp_path)
    candidate = service.build_daily_greeting_candidate(
        session_id="s", now=datetime(2026, 4, 25, 10, 0)
    )
    assert candidate is not None
    for mic_state in ("recording", "processing", "requesting"):
        decision = service.can_emit(
            candidate,
            policy=_policy(),
            media_session={"mic_state": mic_state, "speaking_state": "idle"},
            now=datetime(2026, 4, 25, 10, 0),
        )
        assert decision.allowed is False, f"expected suppression for mic_state={mic_state}"
        assert mic_state in (decision.suppressed_reason or ""), (
            f"reason should mention mic state, got: {decision.suppressed_reason}"
        )


def test_suppressed_while_speaking(tmp_path):
    """Queued or playing TTS blocks emission."""
    service = _service(tmp_path)
    candidate = service.build_daily_greeting_candidate(
        session_id="s", now=datetime(2026, 4, 25, 10, 0)
    )
    assert candidate is not None
    for speaking_state in ("queued", "playing"):
        decision = service.can_emit(
            candidate,
            policy=_policy(),
            media_session={"mic_state": "idle", "speaking_state": speaking_state},
            now=datetime(2026, 4, 25, 10, 0),
        )
        assert decision.allowed is False, f"expected suppression for speaking_state={speaking_state}"
        assert speaking_state in (decision.suppressed_reason or ""), (
            f"reason should mention speaking state, got: {decision.suppressed_reason}"
        )


def test_allowed_when_both_idle(tmp_path):
    """mic=idle and speaking=idle does not suppress on media grounds."""
    service = _service(tmp_path)
    candidate = service.build_daily_greeting_candidate(
        session_id="s", now=datetime(2026, 4, 25, 10, 0)
    )
    assert candidate is not None
    decision = service.can_emit(
        candidate,
        policy=_policy(),
        media_session={"mic_state": "idle", "speaking_state": "idle"},
        now=datetime(2026, 4, 25, 10, 0),
    )
    assert decision.allowed is True


# ---------------------------------------------------------------------------
# Memory follow-up - graceful fallbacks
# ---------------------------------------------------------------------------

class _FakeMemory:
    def __init__(self, created_at: str, text: str) -> None:
        self.created_at = created_at
        self.text = text


class _FakeScopedMemoryStore:
    def __init__(self, memories=None, error: Exception | None = None) -> None:
        self.memories = memories or []
        self.error = error
        self.recent_calls: list[tuple[str, int]] = []

    def recent(self, context_id, limit=15):
        self.recent_calls.append((context_id, limit))
        if self.error is not None:
            raise self.error
        return self.memories[:limit]

    def get_recent_memories(self, limit=15):
        raise AssertionError("memory follow-up must use scoped recent memories")


def test_memory_followup_no_store(tmp_path):
    """Passing memory_store=None returns None without raising."""
    service = _service(tmp_path)
    candidate = service.build_memory_followup_candidate(
        session_id="s",
        memory_store=None,
        now=datetime(2026, 4, 25, 10, 0),
    )
    assert candidate is None


def test_memory_followup_empty_store(tmp_path):
    """Empty memory list -> no candidate."""
    service = _service(tmp_path)

    assert service.build_memory_followup_candidate(
        session_id="s",
        memory_store=_FakeScopedMemoryStore(),
        now=datetime(2026, 4, 25, 10, 0),
    ) is None


def test_memory_followup_default_session_does_not_search_global_memories(tmp_path):
    service = _service(tmp_path)

    assert service.build_memory_followup_candidate(
        session_id="default",
        memory_store=_FakeScopedMemoryStore([
            _FakeMemory(
                created_at=datetime(2026, 4, 24, 20, 0).isoformat(),
                text="I need to follow up with Sarah about the contract renewal before Friday.",
            )
        ]),
        now=datetime(2026, 4, 25, 10, 0),
    ) is None


def test_memory_followup_store_raises(tmp_path):
    """Store that raises does not propagate - returns None gracefully."""
    service = _service(tmp_path)

    assert service.build_memory_followup_candidate(
        session_id="s",
        memory_store=_FakeScopedMemoryStore(error=RuntimeError("db unreachable")),
        now=datetime(2026, 4, 25, 10, 0),
    ) is None


def test_memory_followup_too_recent(tmp_path):
    """Memory created < 2 hours ago is skipped (user still remembers it)."""
    service = _service(tmp_path)
    now = datetime(2026, 4, 25, 10, 0)

    memory_store = _FakeScopedMemoryStore([
        _FakeMemory(
            created_at=datetime(2026, 4, 25, 9, 30).isoformat(),  # 30 min ago
            text="I need to finish the quarterly report for the finance team before Friday.",
        )
    ])

    assert service.build_memory_followup_candidate(
        session_id="s", memory_store=memory_store, now=now
    ) is None


def test_memory_followup_too_old(tmp_path):
    """Memory older than 72 hours is skipped (too stale to follow up on)."""
    service = _service(tmp_path)
    now = datetime(2026, 4, 25, 10, 0)

    memory_store = _FakeScopedMemoryStore([
        _FakeMemory(
            created_at=datetime(2026, 4, 21, 9, 0).isoformat(),  # ~97 hours ago
            text="I need to follow up with the landlord about the lease renewal paperwork.",
        )
    ])

    assert service.build_memory_followup_candidate(
        session_id="s", memory_store=memory_store, now=now
    ) is None


def test_memory_followup_eligible(tmp_path):
    """Memory in the 2-72h window produces a candidate referencing the text."""
    service = _service(tmp_path)
    now = datetime(2026, 4, 25, 10, 0)

    memory_store = _FakeScopedMemoryStore([
        _FakeMemory(
            created_at=datetime(2026, 4, 24, 20, 0).isoformat(),  # 14 hours ago
            text="I need to follow up with Sarah about the contract renewal before Friday.",
        )
    ])

    candidate = service.build_memory_followup_candidate(
        session_id="s", memory_store=memory_store, now=now
    )
    assert candidate is not None
    assert candidate.type == "memory_followup"
    assert "Sarah" in candidate.message
    assert "Earlier you mentioned" in candidate.message


def test_memory_followup_skips_short_text(tmp_path):
    """Memory text under 20 characters is skipped (not meaningful enough)."""
    service = _service(tmp_path)
    now = datetime(2026, 4, 25, 10, 0)

    memory_store = _FakeScopedMemoryStore([
        _FakeMemory(
            created_at=datetime(2026, 4, 24, 22, 0).isoformat(),  # 12 hours ago
            text="Buy milk",  # 8 chars - too short
        )
    ])

    assert service.build_memory_followup_candidate(
        session_id="s", memory_store=memory_store, now=now
    ) is None

def test_memory_followup_not_double_emitted_today(tmp_path):
    """If memory_followup was already emitted today, build returns None immediately."""
    service = _service(tmp_path)
    now = datetime(2026, 4, 25, 10, 0)

    service.store.record_emitted(
        initiative_type="memory_followup",
        session_id="s",
        message="Earlier you mentioned...",
        reason="test",
        emitted_at=now,
    )

    class GoodStore:
        def get_recent_memories(self, limit=15):
            return [_FakeMemory(
                created_at=datetime(2026, 4, 24, 20, 0).isoformat(),
                text="I need to follow up with Sarah about the contract renewal before Friday.",
            )]

    candidate = service.build_memory_followup_candidate(
        session_id="s",
        memory_store=GoodStore(),
        now=datetime(2026, 4, 25, 14, 0),
    )
    assert candidate is None


# ---------------------------------------------------------------------------
# Scheduler - no double-emit
# ---------------------------------------------------------------------------

def test_scheduler_no_double_emit(tmp_path):
    """
    Two consecutive emit calls for the same type on the same day:
    only the first is allowed; the second is suppressed before any spacing check.
    """
    service = _service(tmp_path)
    now = datetime(2026, 4, 25, 10, 0)
    events_published: list[str] = []

    class FakeBus:
        async def publish(self, event, payload, session_id=None, source="system"):
            events_published.append(event)

    candidate = service.build_daily_greeting_candidate(session_id="s", now=now)
    assert candidate is not None

    first = asyncio.run(
        service.emit(
            candidate,
            event_bus=FakeBus(),
            policy=_policy(),
            media_session={"mic_state": "idle", "speaking_state": "idle"},
            now=now,
        )
    )
    assert first.allowed is True

    # Simulate the scheduler running again 15 minutes later (same day, same type).
    second = asyncio.run(
        service.emit(
            candidate,
            event_bus=FakeBus(),
            policy=_policy(),
            media_session={"mic_state": "idle", "speaking_state": "idle"},
            now=datetime(2026, 4, 25, 10, 15),
        )
    )
    assert second.allowed is False
    assert "already emitted today" in (second.suppressed_reason or "")

    # First call fired emitted, second fired suppressed.
    assert events_published == ["initiative.emitted", "initiative.suppressed"]


def test_scheduler_no_double_emit_across_types_at_limit(tmp_path):
    """
    Scheduler processes multiple candidates per tick; once the daily limit is
    hit mid-tick, later candidates in the same tick are suppressed.
    """
    service = _service(tmp_path)
    published: list[str] = []

    class FakeBus:
        async def publish(self, event, payload, session_id=None, source="system"):
            published.append(event)

    policy = _policy(daily_limit=1)
    t0 = datetime(2026, 4, 25, 10, 0)

    greeting = service.build_daily_greeting_candidate(session_id="s", now=t0)
    assert greeting is not None
    service.record_absence_started(
        session_id="s", source="test", now=datetime(2026, 4, 25, 8, 0)
    )
    absence = service.build_return_after_absence_candidate(session_id="s", now=t0)
    assert absence is not None

    # Emit greeting - consumes the single allowed slot.
    r1 = asyncio.run(
        service.emit(
            greeting,
            event_bus=FakeBus(),
            policy=policy,
            media_session={"mic_state": "idle", "speaking_state": "idle"},
            now=t0,
        )
    )
    assert r1.allowed is True

    # Absence candidate evaluated in the same tick - hits the limit.
    r2 = asyncio.run(
        service.emit(
            absence,
            event_bus=FakeBus(),
            policy=policy,
            media_session={"mic_state": "idle", "speaking_state": "idle"},
            now=t0,
        )
    )
    assert r2.allowed is False
    assert r2.suppressed_reason == "daily limit reached"

    assert published.count("initiative.emitted") == 1
    assert published.count("initiative.suppressed") == 1


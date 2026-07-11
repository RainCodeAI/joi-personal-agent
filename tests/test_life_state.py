"""Deterministic Phase-5 avatar life-state behavior and scheduling."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.avatar.life_state import LifeStateEngine, evaluate_life_state
from app.initiative.scheduler import InitiativeScheduler


DAYTIME = datetime(2026, 7, 10, 14, 0, tzinfo=timezone(timedelta(hours=-4)))
LATE_NIGHT = DAYTIME.replace(hour=23)


def test_runtime_states_override_ambient_behavior():
    assert evaluate_life_state(joi_state="speaking", now=DAYTIME) == "engaged"
    assert evaluate_life_state(joi_state="listening", now=DAYTIME) == "observant"
    assert evaluate_life_state(joi_state="thinking", now=DAYTIME) == "observant"
    assert evaluate_life_state(joi_state="user_away", now=DAYTIME) == "resting"


def test_daytime_quiet_has_a_bounded_curious_window():
    assert evaluate_life_state(
        last_activity_at=DAYTIME - timedelta(minutes=2), now=DAYTIME
    ) == "calm"
    assert evaluate_life_state(
        last_activity_at=DAYTIME - timedelta(minutes=10), now=DAYTIME
    ) == "curious"
    assert evaluate_life_state(
        last_activity_at=DAYTIME - timedelta(minutes=40), now=DAYTIME
    ) == "calm"
    assert evaluate_life_state(
        last_activity_at=DAYTIME - timedelta(minutes=60), now=DAYTIME
    ) == "resting"


def test_late_night_quiet_settles_instead_of_becoming_curious():
    assert evaluate_life_state(
        last_activity_at=LATE_NIGHT - timedelta(minutes=2), now=LATE_NIGHT
    ) == "calm"
    assert evaluate_life_state(
        last_activity_at=LATE_NIGHT - timedelta(minutes=10), now=LATE_NIGHT
    ) == "resting"


def test_absence_is_always_resting():
    assert evaluate_life_state(
        last_activity_at=DAYTIME,
        absence_started_at=DAYTIME - timedelta(seconds=1),
        now=DAYTIME,
    ) == "resting"


def test_ambient_transition_requires_stable_candidate():
    engine = LifeStateEngine(ambient_settle_seconds=60)
    last_activity = DAYTIME - timedelta(minutes=10)

    assert engine.evaluate(last_activity_at=last_activity, now=DAYTIME) is None
    assert engine.snapshot()["pending_life_state"] == "curious"
    assert engine.evaluate(last_activity_at=last_activity, now=DAYTIME + timedelta(seconds=59)) is None
    assert engine.evaluate(last_activity_at=last_activity, now=DAYTIME + timedelta(seconds=60)) == "curious"
    assert engine.current == "curious"
    assert engine.snapshot()["pending_life_state"] is None


def test_presence_and_runtime_transitions_bypass_or_clear_hysteresis():
    engine = LifeStateEngine(ambient_settle_seconds=60)
    engine.evaluate(last_activity_at=DAYTIME - timedelta(minutes=10), now=DAYTIME)

    assert engine.on_joi_state_changed("thinking", now=DAYTIME) == "observant"
    assert engine.snapshot()["pending_life_state"] is None
    assert engine.on_joi_state_changed("idle", now=DAYTIME + timedelta(seconds=1)) == "calm"
    assert engine.evaluate(
        absence_started_at=DAYTIME,
        now=DAYTIME + timedelta(seconds=2),
        immediate=True,
    ) == "resting"


def test_life_state_tick_publishes_only_real_transition():
    store = SimpleNamespace(
        last_user_activity_at=MagicMock(return_value=DAYTIME - timedelta(minutes=10)),
        absence_started_at=MagicMock(return_value=None),
    )
    service = SimpleNamespace(store=store)
    event_bus = SimpleNamespace(publish=AsyncMock())
    engine = MagicMock()
    engine.evaluate.return_value = "curious"
    scheduler = InitiativeScheduler(
        service,
        event_bus,
        memory_store=object(),
        media_sessions=object(),
        life_state_engine=engine,
    )

    asyncio.run(scheduler._life_state_tick())

    engine.evaluate.assert_called_once_with(
        last_activity_at=DAYTIME - timedelta(minutes=10),
        absence_started_at=None,
    )
    event_bus.publish.assert_awaited_once_with(
        "avatar.life_state_changed",
        {"life_state": "curious"},
        session_id="default",
        source="life_state",
    )


def test_life_state_tick_stays_quiet_without_transition():
    store = SimpleNamespace(
        last_user_activity_at=MagicMock(return_value=DAYTIME),
        absence_started_at=MagicMock(return_value=None),
    )
    event_bus = SimpleNamespace(publish=AsyncMock())
    engine = MagicMock()
    engine.evaluate.return_value = None
    scheduler = InitiativeScheduler(
        SimpleNamespace(store=store),
        event_bus,
        memory_store=object(),
        media_sessions=object(),
        life_state_engine=engine,
    )

    asyncio.run(scheduler._life_state_tick())

    event_bus.publish.assert_not_awaited()


def test_scheduler_registers_one_minute_life_state_tick(monkeypatch):
    class FakeScheduler:
        def __init__(self):
            self.jobs = []
            self.running = False

        def add_job(self, func, **kwargs):
            self.jobs.append((func, kwargs))

        def start(self):
            self.running = True

        def shutdown(self, wait=False):
            self.running = False

    fake_scheduler = FakeScheduler()
    monkeypatch.setattr(
        "apscheduler.schedulers.asyncio.AsyncIOScheduler",
        lambda: fake_scheduler,
    )
    scheduler = InitiativeScheduler(
        SimpleNamespace(store=SimpleNamespace()),
        SimpleNamespace(publish=AsyncMock()),
        memory_store=object(),
        media_sessions=object(),
        life_state_engine=LifeStateEngine(),
    )

    asyncio.run(scheduler.start())

    life_job = next(
        kwargs
        for _, kwargs in fake_scheduler.jobs
        if kwargs["id"] == "avatar_life_state_tick"
    )
    assert life_job["trigger"] == "interval"
    assert life_job["minutes"] == 1
    assert life_job["coalesce"] is True
    assert life_job["max_instances"] == 1
    asyncio.run(scheduler.stop())

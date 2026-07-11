from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal

LifeStateName = Literal["calm", "observant", "resting", "engaged", "curious"]

# Joi/hardware states that immediately override life state regardless of time/idle.
_JOI_STATE_OVERRIDES: dict[str, LifeStateName] = {
    "speaking": "engaged",
    "listening": "observant",
    "thinking": "observant",
    "user_returned": "observant",
    "sleeping": "resting",
    "user_away": "resting",
    "error": "resting",
}

_CURIOUS_AFTER_SECONDS = 5 * 60
_CURIOUS_UNTIL_SECONDS = 30 * 60
_IDLE_RESTING_SECONDS = 60 * 60
_DEFAULT_AMBIENT_SETTLE_SECONDS = 60


def _time_of_day_base(hour: int) -> LifeStateName:
    if hour >= 22 or hour < 6:
        return "resting"
    if 6 <= hour < 9:
        return "calm"
    return "calm"


def _normalise_time(value: datetime, current: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=current.tzinfo)
    return value.astimezone(current.tzinfo)


def evaluate_life_state(
    *,
    joi_state: str | None = None,
    last_activity_at: datetime | None = None,
    absence_started_at: datetime | None = None,
    now: datetime | None = None,
) -> LifeStateName:
    """Pure function — derive life state from available signals.

    Priority order:
      1. Joi state override (speaking/listening/thinking/away/sleeping)
      2. User absence
      3. Idle duration (brief quiet → curious, sustained idle → resting)
      4. Time of day
    """
    # Time-of-day behavior follows the room Joi is in, not UTC.
    current = now or datetime.now().astimezone()

    if joi_state in _JOI_STATE_OVERRIDES:
        return _JOI_STATE_OVERRIDES[joi_state]

    if absence_started_at is not None:
        return "resting"

    if last_activity_at is not None:
        laa = _normalise_time(last_activity_at, current)
        idle = (current - laa).total_seconds()
        if idle >= _IDLE_RESTING_SECONDS:
            return "resting"
        if current.hour >= 22 or current.hour < 6:
            return "calm" if idle < _CURIOUS_AFTER_SECONDS else "resting"
        if _CURIOUS_AFTER_SECONDS <= idle < _CURIOUS_UNTIL_SECONDS:
            return "curious"
        return "calm"

    return _time_of_day_base(current.hour)


class LifeStateEngine:
    """Stateful wrapper around evaluate_life_state.

    Tracks the last published state so callers can check whether anything
    changed before deciding to publish an event.
    """

    def __init__(
        self,
        *,
        ambient_settle_seconds: int = _DEFAULT_AMBIENT_SETTLE_SECONDS,
    ) -> None:
        self._state: LifeStateName = "calm"
        self._joi_state: str | None = None
        self._state_changed_at = datetime.now().astimezone()
        self._pending_state: LifeStateName | None = None
        self._pending_since: datetime | None = None
        self._ambient_settle = timedelta(seconds=max(0, ambient_settle_seconds))

    @property
    def current(self) -> LifeStateName:
        return self._state

    def _transition(
        self,
        new_state: LifeStateName,
        *,
        now: datetime,
    ) -> LifeStateName | None:
        self._pending_state = None
        self._pending_since = None
        if new_state == self._state:
            return None
        self._state = new_state
        self._state_changed_at = now
        return new_state

    def on_joi_state_changed(
        self,
        joi_state: str,
        *,
        now: datetime | None = None,
    ) -> LifeStateName | None:
        """Fast-path update when the Joi runtime state changes.

        Returns the new life state if it changed, else None.
        """
        current = now or datetime.now().astimezone()
        self._joi_state = joi_state
        # Active runtime states override immediately. Returning to idle settles
        # to calm first; the periodic ambient evaluator then decides whether
        # sustained quiet should become curious or resting.
        new_state = _JOI_STATE_OVERRIDES.get(joi_state, "calm")
        return self._transition(new_state, now=current)

    def evaluate(
        self,
        *,
        last_activity_at: datetime | None = None,
        absence_started_at: datetime | None = None,
        now: datetime | None = None,
        immediate: bool = False,
    ) -> LifeStateName | None:
        """Slow-path update with full context (presence, idle, time-of-day).

        Returns the new life state if it changed, else None.
        """
        current = now or datetime.now().astimezone()
        new_state = evaluate_life_state(
            joi_state=self._joi_state,
            last_activity_at=last_activity_at,
            absence_started_at=absence_started_at,
            now=current,
        )
        if immediate or new_state in {"engaged", "observant"}:
            return self._transition(new_state, now=current)
        if new_state == self._state:
            self._pending_state = None
            self._pending_since = None
            return None
        if self._ambient_settle.total_seconds() == 0:
            return self._transition(new_state, now=current)
        if self._pending_state != new_state:
            self._pending_state = new_state
            self._pending_since = current
            return None
        if (
            self._pending_since is not None
            and current - self._pending_since >= self._ambient_settle
        ):
            return self._transition(new_state, now=current)
        return None

    def snapshot(self) -> dict[str, Any]:
        return {
            "life_state": self._state,
            "joi_state": self._joi_state,
            "state_changed_at": self._state_changed_at.isoformat(),
            "pending_life_state": self._pending_state,
        }

from __future__ import annotations

from datetime import datetime, timezone
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

_IDLE_RESTING_SECONDS = 60 * 60  # 1 h idle → resting
_IDLE_CALM_SECONDS = 30 * 60     # 30 min idle → calm


def _time_of_day_base(hour: int) -> LifeStateName:
    if hour >= 22 or hour < 6:
        return "resting"
    if 6 <= hour < 9:
        return "calm"
    return "calm"


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
      3. Idle duration (long idle → resting, medium → calm)
      4. Time of day
    """
    current = now or datetime.now(timezone.utc)

    if joi_state in _JOI_STATE_OVERRIDES:
        return _JOI_STATE_OVERRIDES[joi_state]

    if absence_started_at is not None:
        return "resting"

    if last_activity_at is not None:
        # Normalise timezone so subtraction is safe
        laa = last_activity_at
        if laa.tzinfo is None:
            laa = laa.replace(tzinfo=current.tzinfo)
        else:
            laa = laa.astimezone(current.tzinfo)
        idle = (current - laa).total_seconds()
        if idle > _IDLE_RESTING_SECONDS:
            return "resting"
        if idle > _IDLE_CALM_SECONDS:
            return "calm"

    return _time_of_day_base(current.hour)


class LifeStateEngine:
    """Stateful wrapper around evaluate_life_state.

    Tracks the last published state so callers can check whether anything
    changed before deciding to publish an event.
    """

    def __init__(self) -> None:
        self._state: LifeStateName = "calm"
        self._joi_state: str | None = None

    @property
    def current(self) -> LifeStateName:
        return self._state

    def on_joi_state_changed(self, joi_state: str) -> LifeStateName | None:
        """Fast-path update when the Joi runtime state changes.

        Returns the new life state if it changed, else None.
        """
        self._joi_state = joi_state
        new_state = evaluate_life_state(joi_state=joi_state)
        if new_state != self._state:
            self._state = new_state
            return new_state
        return None

    def evaluate(
        self,
        *,
        last_activity_at: datetime | None = None,
        absence_started_at: datetime | None = None,
        now: datetime | None = None,
    ) -> LifeStateName | None:
        """Slow-path update with full context (presence, idle, time-of-day).

        Returns the new life state if it changed, else None.
        """
        new_state = evaluate_life_state(
            joi_state=self._joi_state,
            last_activity_at=last_activity_at,
            absence_started_at=absence_started_at,
            now=now,
        )
        if new_state != self._state:
            self._state = new_state
            return new_state
        return None

    def snapshot(self) -> dict[str, Any]:
        return {
            "life_state": self._state,
            "joi_state": self._joi_state,
        }

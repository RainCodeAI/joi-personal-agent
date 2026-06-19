from __future__ import annotations

import pytest

from app.tools import calendar_gcal


def test_create_event_rejects_unparseable_time_before_api_call(monkeypatch):
    monkeypatch.setattr(calendar_gcal, "get_credentials", lambda: object())

    with pytest.raises(ValueError, match="ISO-8601"):
        calendar_gcal.create_event("Meeting", "tomorrow 2pm")


def test_create_event_rejects_invalid_duration(monkeypatch):
    monkeypatch.setattr(calendar_gcal, "get_credentials", lambda: object())

    with pytest.raises(ValueError, match="duration_minutes"):
        calendar_gcal.create_event("Meeting", "2026-06-18T14:00:00-04:00", 0)

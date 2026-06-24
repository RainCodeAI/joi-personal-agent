from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from app.persistence import read_json, write_json_atomic


class ContextEventStore:
    """Persist a bounded, expiry-pruned context-event buffer."""

    _DELIVERY_CLAIM_TIMEOUT = timedelta(minutes=10)

    def __init__(self, path: Path, *, limit: int = 200) -> None:
        self.path = path
        self.limit = max(1, limit)
        self._lock = Lock()
        loaded = read_json(path, [])
        self._events: list[dict[str, Any]] = loaded if isinstance(loaded, list) else []
        self._prune_locked(datetime.now(timezone.utc))

    def add(self, event: dict[str, Any], *, now: datetime | None = None) -> None:
        current = now or datetime.now(timezone.utc)
        with self._lock:
            self._prune_locked(current)
            self._events.append(dict(event))
            self._events = self._events[-self.limit :]
            self._persist_locked()

    def get(self, event_id: str, *, now: datetime | None = None) -> dict[str, Any] | None:
        for event in self.recent(limit=self.limit, now=now):
            if event.get("event_id") == event_id:
                return event
        return None

    def update(self, event_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            for index, event in enumerate(self._events):
                if event.get("event_id") != event_id:
                    continue
                updated = {**event, **patch}
                self._events[index] = updated
                self._persist_locked()
                return dict(updated)
        return None

    def claim_commentary(
        self,
        event_id: str,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        current = now or datetime.now(timezone.utc)
        with self._lock:
            changed = self._prune_locked(current)
            for index, event in enumerate(self._events):
                if (
                    event.get("event_id") != event_id
                    or event.get("commentary_status") != "queued"
                ):
                    continue
                claimed = {
                    **event,
                    "commentary_status": "delivering",
                    "commentary_reason": "delivery claimed",
                    "commentary_updated_at": current.isoformat(),
                }
                self._events[index] = claimed
                self._persist_locked()
                return dict(claimed)
            if changed:
                self._persist_locked()
        return None

    def pending(self, *, limit: int = 10, now: datetime | None = None) -> list[dict[str, Any]]:
        current = now or datetime.now(timezone.utc)
        with self._lock:
            changed = self._prune_locked(current)
            for index, event in enumerate(self._events):
                if event.get("commentary_status") != "delivering":
                    continue
                updated_at = self._parse_datetime(event.get("commentary_updated_at"))
                if (
                    updated_at is not None
                    and current - updated_at < self._DELIVERY_CLAIM_TIMEOUT
                ):
                    continue
                self._events[index] = {
                    **event,
                    "commentary_status": "queued",
                    "commentary_reason": "stale delivery claim recovered",
                    "commentary_updated_at": current.isoformat(),
                }
                changed = True
            events = [
                dict(event)
                for event in self._events
                if event.get("commentary_status") == "queued"
            ][: max(0, limit)]
            if changed:
                self._persist_locked()
        return events

    def recent(
        self,
        *,
        session_id: str | None = None,
        limit: int = 20,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        current = now or datetime.now(timezone.utc)
        with self._lock:
            changed = self._prune_locked(current)
            events = list(self._events)
            if changed:
                self._persist_locked()
        if session_id is not None:
            events = [event for event in events if event.get("session_id") == session_id]
        return events[-max(0, limit) :] if limit > 0 else []

    def find_recent_dedup(
        self,
        dedup_key: str,
        *,
        since: datetime,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        for event in reversed(self.recent(limit=self.limit, now=now)):
            if event.get("dedup_key") != dedup_key:
                continue
            try:
                observed = datetime.fromisoformat(str(event.get("observed_at")))
                if observed.tzinfo is None:
                    observed = observed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if observed >= since:
                return event
        return None

    def diagnostics(self) -> dict[str, Any]:
        events = self.recent(limit=self.limit)
        return {
            "buffered_events": len(events),
            "buffer_limit": self.limit,
            "latest_event_at": events[-1].get("observed_at") if events else None,
            "queued_commentary": sum(
                event.get("commentary_status") == "queued" for event in events
            ),
            "delivering_commentary": sum(
                event.get("commentary_status") == "delivering" for event in events
            ),
        }

    def _prune_locked(self, now: datetime) -> bool:
        kept: list[dict[str, Any]] = []
        for event in self._events:
            expires = self._parse_datetime(event.get("expires_at"))
            if expires is None:
                continue
            if expires > now:
                kept.append(event)
        changed = len(kept) != len(self._events)
        self._events = kept[-self.limit :]
        return changed

    def _persist_locked(self) -> None:
        write_json_atomic(self.path, self._events)

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

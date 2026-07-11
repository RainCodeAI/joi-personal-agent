"""Durable outbound queue for proactive delivery to remote surfaces (Telegram).

The Joi backend never talks to Telegram directly — the bot token lives only in
the standalone bridge process. So when Joi wants to reach the user while they're
away (a gated initiative), the backend *enqueues* the line here and the bridge
claims and delivers it on its next poll, then acks. That keeps the bridge the
sole Telegram-touching component and the queue durable across restarts.

Delivery is at-least-once: an unacked message is handed out again on the next
claim. The emission gate upstream already prevents duplicate same-type messages,
and `dedup_key` guards against a message piling up while the bridge is offline.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Iterable

from app.config import settings
from app.initiative.policy import InitiativeCandidate
from app.persistence import read_json, write_json_atomic

logger = logging.getLogger("joi.outbox")

# Retention: acked or long-expired records are pruned once older than this, and
# the file is hard-capped so an offline bridge can't grow it without bound.
_RETENTION_HOURS = 24
_MAX_RECORDS = 200
_DEFAULT_TTL_MINUTES = 180


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def initiative_is_deliverable(candidate: InitiativeCandidate) -> bool:
    """Whether a gated initiative should also be pushed to the remote surface.

    Conservative by design: remote delivery is opt-in (``telegram_proactive_enabled``)
    and only the explicitly allowed initiative types leave the laptop, so
    memory- or context-derived lines that may quote sensitive content stay local
    unless the user widens ``telegram_proactive_types``.
    """
    if not getattr(settings, "telegram_proactive_enabled", False):
        return False
    return candidate.type in settings.telegram_proactive_type_set


class TelegramOutbox:
    """Small persisted queue of proactive messages awaiting remote delivery."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("data/telegram_outbox.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._records: list[dict[str, Any]] = self._load()

    # ── writes ────────────────────────────────────────────────────────────

    def enqueue(
        self,
        *,
        text: str,
        kind: str,
        dedup_key: str | None = None,
        expires_at: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        """Queue one message. Returns the record, or None if it was deduplicated.

        Dedup is against still-pending (unacked, unexpired) records only: the
        emission gate handles not re-sending the same idea, so here we only stop
        a message stacking up while the bridge is unreachable.
        """
        text = (text or "").strip()
        if not text:
            return None
        current = now or _utc_now()
        if expires_at is None:
            expires_at = (current + timedelta(minutes=_DEFAULT_TTL_MINUTES)).isoformat()

        with self._lock:
            self._prune(current)
            if dedup_key:
                for record in self._records:
                    if (
                        record.get("dedup_key") == dedup_key
                        and record.get("delivered_at") is None
                        and not self._is_expired(record, current)
                    ):
                        return None
            record = {
                "id": str(uuid.uuid4()),
                "kind": kind,
                "text": text,
                "dedup_key": dedup_key,
                "created_at": current.isoformat(),
                "expires_at": expires_at,
                "claimed_at": None,
                "delivered_at": None,
                "attempts": 0,
            }
            self._records.append(record)
            self._persist()
        return dict(record)

    def claim(self, *, limit: int = 10, now: datetime | None = None) -> list[dict[str, Any]]:
        """Hand out undelivered, unexpired messages (oldest first) for delivery."""
        current = now or _utc_now()
        claimed: list[dict[str, Any]] = []
        with self._lock:
            self._prune(current)
            for record in self._records:
                if record.get("delivered_at") is not None:
                    continue
                if self._is_expired(record, current):
                    continue
                record["claimed_at"] = current.isoformat()
                record["attempts"] = int(record.get("attempts", 0)) + 1
                claimed.append(
                    {
                        "id": record["id"],
                        "kind": record["kind"],
                        "text": record["text"],
                        "created_at": record["created_at"],
                    }
                )
                if len(claimed) >= max(1, limit):
                    break
            if claimed:
                self._persist()
        return claimed

    def ack(self, ids: Iterable[str], *, now: datetime | None = None) -> int:
        """Mark the given message ids delivered. Returns how many were updated."""
        wanted = {str(i) for i in ids}
        if not wanted:
            return 0
        current = now or _utc_now()
        updated = 0
        with self._lock:
            for record in self._records:
                if record["id"] in wanted and record.get("delivered_at") is None:
                    record["delivered_at"] = current.isoformat()
                    updated += 1
            self._prune(current)
            if updated:
                self._persist()
        return updated

    # ── reads / diagnostics ───────────────────────────────────────────────

    def pending_count(self, *, now: datetime | None = None) -> int:
        current = now or _utc_now()
        with self._lock:
            return sum(
                1
                for record in self._records
                if record.get("delivered_at") is None and not self._is_expired(record, current)
            )

    # ── internals ─────────────────────────────────────────────────────────

    @staticmethod
    def _is_expired(record: dict[str, Any], now: datetime) -> bool:
        expires = _parse_dt(record.get("expires_at"))
        return expires is not None and now > expires

    def _prune(self, now: datetime) -> None:
        """Drop delivered/expired records past retention; cap the total size."""
        cutoff = now - timedelta(hours=_RETENTION_HOURS)
        kept: list[dict[str, Any]] = []
        for record in self._records:
            delivered = _parse_dt(record.get("delivered_at"))
            if delivered is not None and delivered < cutoff:
                continue
            if delivered is None and self._is_expired(record, now):
                created = _parse_dt(record.get("created_at"))
                if created is not None and created < cutoff:
                    continue
            kept.append(record)
        if len(kept) > _MAX_RECORDS:
            # Oldest-first order is preserved, so trimming the front drops the
            # stalest records (delivered ones sort out via retention first).
            kept = kept[-_MAX_RECORDS:]
        self._records = kept

    def _load(self) -> list[dict[str, Any]]:
        data = read_json(self.path, [])
        if isinstance(data, list):
            return [record for record in data if isinstance(record, dict) and record.get("id")]
        return []

    def _persist(self) -> None:
        write_json_atomic(self.path, self._records)

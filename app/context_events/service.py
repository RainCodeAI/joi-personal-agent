from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import settings
from app.context_events.models import ContextCategory, ContextDecision, ContextEvent
from app.context_events.feedback import ContextFeedbackStore
from app.context_events.store import ContextEventStore
from app.initiative.policy import InitiativeCandidate


DEFAULT_ALLOWED_CATEGORIES = (
    "work_activity",
    "wellbeing",
    "entertainment",
    "reminders",
)
FEEDBACK_RETENTION_DAYS = 7
RETRYABLE_SUPPRESSION_REASONS = {
    "minimum initiative spacing active",
}


class ContextEventService:
    def __init__(
        self,
        store: ContextEventStore,
        feedback_store: ContextFeedbackStore | None = None,
    ) -> None:
        self.store = store
        self.feedback_store = feedback_store

    def observe(
        self,
        *,
        source: str,
        kind: str,
        category: ContextCategory,
        confidence: float,
        sensitivity: str,
        session_id: str = "default",
        payload: dict[str, Any] | None = None,
        ttl_seconds: int = 300,
        now: datetime | None = None,
    ) -> ContextDecision:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        safe_payload = self._sanitize_payload(payload or {})
        dedup_key = self._dedup_key(source, kind, category, safe_payload)
        event = ContextEvent(
            source=source,
            kind=kind,
            category=category,
            confidence=max(0.0, min(float(confidence), 1.0)),
            sensitivity=sensitivity if sensitivity in {"public", "private", "sensitive"} else "private",
            observed_at=current.isoformat(),
            expires_at=(current + timedelta(seconds=max(1, ttl_seconds))).isoformat(),
            session_id=session_id,
            payload=safe_payload,
            dedup_key=dedup_key,
        )

        minimum = float(getattr(settings, "context_min_confidence", 0.75))
        if event.confidence < minimum:
            return ContextDecision(False, event, "confidence below threshold")

        dedup_minutes = max(1, int(getattr(settings, "context_dedup_minutes", 10)))
        existing = self.store.find_recent_dedup(
            dedup_key,
            since=current - timedelta(minutes=dedup_minutes),
            now=current,
        )
        if existing is not None:
            return ContextDecision(False, event, "duplicate context event")

        allowed = self._allowed_categories()
        commentary_enabled = bool(getattr(settings, "context_commentary_enabled", False))
        category_enabled = category in allowed
        sensitivity_allowed = event.sensitivity != "sensitive"
        active_flow_handled = bool(
            event.payload.get("user_initiated")
            or event.payload.get("handled_by_existing_flow")
        )
        kind_allowed = not (
            self.feedback_store and self.feedback_store.kind_blocked(event.kind)
        )
        cooldown_clear = not (
            self.feedback_store
            and self.feedback_store.category_cooldown_active(event.category, now=current)
        )
        commentary_eligible = (
            commentary_enabled
            and category_enabled
            and sensitivity_allowed
            and kind_allowed
            and cooldown_clear
            and not active_flow_handled
        )
        if not commentary_enabled:
            reason = "buffered; commentary disabled"
        elif not category_enabled:
            reason = f"buffered; category disabled: {category}"
        elif not sensitivity_allowed:
            reason = "buffered; sensitive events cannot trigger commentary"
        elif not kind_allowed:
            reason = f"buffered; event kind blocked by feedback: {event.kind}"
        elif not cooldown_clear:
            reason = f"buffered; category feedback cooldown active: {category}"
        elif active_flow_handled:
            reason = "buffered; observation handled by active flow"
        else:
            reason = "buffered; eligible for restrained commentary"
        event_record = {
            **event.to_dict(),
            "commentary_status": "queued" if commentary_eligible else "not_eligible",
            "commentary_reason": reason,
        }
        self.store.add(event_record, now=current)
        return ContextDecision(
            True,
            event,
            reason,
            commentary_eligible=commentary_eligible,
            queued=commentary_eligible,
        )

    def diagnostics(self) -> dict[str, Any]:
        return {
            **self.store.diagnostics(),
            **(self.feedback_store.diagnostics() if self.feedback_store else {}),
            "commentary_enabled": bool(
                getattr(settings, "context_commentary_enabled", False)
            ),
            "min_confidence": float(getattr(settings, "context_min_confidence", 0.75)),
            "dedup_minutes": int(getattr(settings, "context_dedup_minutes", 10)),
            "allowed_categories": sorted(self._allowed_categories()),
            "appearance_default_off": "appearance" not in self._allowed_categories(),
            "social_app_activity_default_off": (
                "social_app_activity" not in self._allowed_categories()
            ),
        }

    def build_commentary_candidate(
        self,
        event_id: str,
        *,
        claim: bool = False,
    ) -> InitiativeCandidate | None:
        event = (
            self.store.claim_commentary(event_id)
            if claim
            else self.store.get(event_id)
        )
        expected_status = "delivering" if claim else "queued"
        if event is None or event.get("commentary_status") != expected_status:
            return None
        message = self._commentary_message(event)
        if not message:
            self.store.update(
                event_id,
                {
                    "commentary_status": "not_eligible",
                    "commentary_reason": "no restrained commentary template",
                },
            )
            return None
        return InitiativeCandidate(
            type="context_commentary",
            priority="low",
            reason=f"context event {event.get('kind')}: {event_id}",
            session_id=str(event.get("session_id") or "default"),
            message=message,
            expires_at=str(event.get("expires_at") or ""),
            context_event_id=event_id,
        )

    def mark_delivery(
        self,
        event_id: str,
        *,
        emitted: bool,
        reason: str | None = None,
        retryable: bool = False,
    ) -> dict[str, Any] | None:
        status = "emitted" if emitted else ("queued" if retryable else "suppressed")
        current = datetime.now(timezone.utc)
        patch: dict[str, Any] = {
            "commentary_status": status,
            "commentary_reason": reason or status,
            "commentary_updated_at": current.isoformat(),
        }
        if emitted:
            patch["expires_at"] = (
                current + timedelta(days=FEEDBACK_RETENTION_DAYS)
            ).isoformat()
        return self.store.update(
            event_id,
            patch,
        )

    def record_feedback(self, event_id: str, action: str) -> dict[str, Any]:
        if action not in {"useful", "wrong", "too_much", "never_comment"}:
            raise ValueError("Unsupported context feedback action")
        event = self.store.get(event_id)
        if event is None:
            raise KeyError(event_id)
        if self.feedback_store is None:
            raise RuntimeError("Context feedback storage is unavailable")
        existing = self.feedback_store.find_record(event_id)
        if existing is not None:
            if existing.get("action") == action:
                return {**existing, "duplicate": True}
            raise ValueError("Feedback has already been recorded for this context event")
        record = self.feedback_store.record(
            event_id=event_id,
            kind=str(event.get("kind") or "unknown"),
            category=str(event.get("category") or "work_activity"),
            action=action,
        )
        self.store.update(
            event_id,
            {
                "feedback": action,
                "feedback_at": record["created_at"],
            },
        )
        return record

    @staticmethod
    def is_retryable_suppression(reason: str | None) -> bool:
        if not reason:
            return False
        return (
            reason.startswith("mic state is ")
            or reason.startswith("speaking state is ")
            or reason in RETRYABLE_SUPPRESSION_REASONS
        )

    @staticmethod
    def _commentary_message(event: dict[str, Any]) -> str | None:
        kind = str(event.get("kind") or "")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if kind == "user_returned":
            return "Welcome back. Want to pick up where you left off?"
        if kind == "manual_screen_capture":
            description = str(payload.get("description") or "").strip()
            if description:
                return f"I noticed {description[:180]}. Want me to help with what's on screen?"
            return "I have the screen context you shared. Want me to help with it?"
        return None

    @staticmethod
    def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            if key in {"data_url", "raw_image", "image_bytes", "audio_bytes"}:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                sanitized[str(key)] = value
            elif isinstance(value, list):
                sanitized[str(key)] = value[:20]
            elif isinstance(value, dict):
                sanitized[str(key)] = {
                    str(inner_key): inner_value
                    for inner_key, inner_value in list(value.items())[:20]
                    if isinstance(inner_value, (str, int, float, bool)) or inner_value is None
                }
        return sanitized

    @staticmethod
    def _dedup_key(
        source: str,
        kind: str,
        category: str,
        payload: dict[str, Any],
    ) -> str:
        canonical = json.dumps(
            {"source": source, "kind": kind, "category": category, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _allowed_categories() -> set[str]:
        raw = str(
            getattr(
                settings,
                "context_allowed_categories",
                ",".join(DEFAULT_ALLOWED_CATEGORIES),
            )
        )
        return {piece.strip() for piece in raw.split(",") if piece.strip()}

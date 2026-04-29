from __future__ import annotations

import json
import uuid
from typing import Any

from app.user_model.synthesis import SynthesisCandidate


ALLOWED_LLM_SECTIONS = {
    "active_projects",
    "recurring_worries",
    "stated_goals",
    "important_people",
    "mood_trend",
    "communication_preferences",
    "recent_wins",
    "open_loops",
}

MIN_LLM_CONFIDENCE = 0.75


def parse_llm_candidates(
    raw_response: str,
    messages: list[Any],
    *,
    user_id: str = "default",
    corrections: list[dict] | None = None,
    existing_sections: list[Any] | None = None,
    min_confidence: float = MIN_LLM_CONFIDENCE,
) -> list[SynthesisCandidate]:
    """Validate LLM synthesis JSON into safe dry-run candidates.

    The parser is intentionally strict. It only accepts candidates grounded in a
    provided user-message excerpt, in allowed sections, with enough confidence.
    """
    payload = _load_payload(raw_response)
    if payload is None:
        return []

    raw_candidates = payload if isinstance(payload, list) else payload.get("candidates", [])
    if not isinstance(raw_candidates, list):
        return []

    blocked_ids = _blocked_ids(corrections or [])
    existing_labels = _existing_labels(existing_sections or [])
    accepted: dict[str, SynthesisCandidate] = {}
    for raw in raw_candidates:
        if not isinstance(raw, dict):
            continue

        section_key = str(raw.get("section_key") or "").strip()
        if section_key not in ALLOWED_LLM_SECTIONS:
            continue

        label = _clean_text(raw.get("label"), limit=80)
        value = _clean_text(raw.get("value"), limit=320)
        evidence = _clean_text(
            raw.get("source_excerpt") or raw.get("evidence_excerpt") or raw.get("evidence"),
            limit=500,
        )
        if not label or not value or not evidence:
            continue

        confidence = _as_confidence(raw.get("confidence"))
        if confidence is None or confidence < min_confidence:
            continue

        source_index = _as_index(raw.get("source_message_index"), len(messages))
        if source_index is None:
            continue

        source_role = str(raw.get("source_message_role") or "user").strip().lower()
        if source_role != "user":
            continue

        if not _excerpt_is_grounded(evidence, messages, source_index):
            continue

        candidate_id = f"{section_key}:llm:{uuid.uuid5(uuid.NAMESPACE_DNS, f'{user_id}:{section_key}:{label.lower()}')}"
        blocked = candidate_id in blocked_ids
        duplicate = _is_duplicate(label, existing_labels)

        candidate = SynthesisCandidate(
            candidate_id=candidate_id,
            section_key=section_key,
            label=label,
            value=value,
            confidence=confidence,
            inference_method="llm",
            trigger_phrase="llm_extraction",
            source_excerpt=evidence,
            source_message_role="user",
            source_message_index=source_index,
            blocked_by_correction=blocked,
            duplicate_of_existing=duplicate,
        )

        key = f"{section_key}:{label.lower()}"
        previous = accepted.get(key)
        if previous is None or candidate.confidence > previous.confidence:
            accepted[key] = candidate

    return [
        candidate
        for candidate in accepted.values()
        if not candidate.blocked_by_correction and not candidate.duplicate_of_existing
    ]


def _load_payload(raw_response: str) -> Any | None:
    try:
        payload = json.loads(raw_response)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, (dict, list)):
        return None
    return payload


def _clean_text(value: Any, *, limit: int) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:limit]


def _as_confidence(value: Any) -> float | None:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= confidence <= 1.0:
        return None
    return confidence


def _as_index(value: Any, message_count: int) -> int | None:
    try:
        index = int(value)
    except (TypeError, ValueError):
        return None
    if index < 0 or index >= message_count:
        return None
    return index


def _excerpt_is_grounded(excerpt: str, messages: list[Any], source_index: int) -> bool:
    normalized_excerpt = _normalize_for_match(excerpt)
    if not normalized_excerpt:
        return False

    if source_index < len(messages):
        source_message = messages[source_index]
        if getattr(source_message, "role", "") != "user":
            return False
        source_text = _normalize_for_match(getattr(source_message, "content", "") or "")
        if normalized_excerpt in source_text:
            return True

    return any(
        normalized_excerpt in _normalize_for_match(getattr(message, "content", "") or "")
        for message in messages
        if getattr(message, "role", "") == "user"
    )


def _normalize_for_match(text: str) -> str:
    return " ".join(str(text or "").lower().split())


def _blocked_ids(corrections: list[dict]) -> set[str]:
    return {
        str(correction["item_id"])
        for correction in corrections
        if correction.get("action") in {"hide", "delete"} and correction.get("item_id")
    }


def _existing_labels(sections: list[Any]) -> set[str]:
    labels: set[str] = set()
    for section in sections:
        for item in getattr(section, "items", []) or []:
            label = str(getattr(item, "label", "") or "").strip().lower()
            if label:
                labels.add(label)
    return labels


def _is_duplicate(candidate_label: str, existing_labels: set[str]) -> bool:
    label = candidate_label.lower()
    return any(label in existing or existing in label for existing in existing_labels)

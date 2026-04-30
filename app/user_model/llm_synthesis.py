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


LLM_SYNTHESIS_SYSTEM_PROMPT = """You extract cautious user-model candidates from a single chat session.

Return JSON only. Do not explain.

You may infer only facts directly supported by user messages in the provided session. Do not infer from assistant messages except to understand conversational context. Do not guess. Do not diagnose. Do not label the user's personality. Do not create a candidate when the evidence is weak, generic, playful, or only small talk.

Allowed section_key values:
- active_projects
- recurring_worries
- stated_goals
- important_people
- mood_trend
- communication_preferences
- recent_wins
- open_loops

Every candidate must include:
- section_key
- label
- value
- confidence, from 0.0 to 1.0
- source_excerpt, copied from a user message
- source_message_index, the zero-based index of that user message in the provided messages array
- source_message_role, always "user"

Confidence rules:
- 0.90-1.00: explicit user instruction or direct statement with durable meaning
- 0.80-0.89: clear direct evidence with a specific subject
- 0.75-0.79: likely durable context, but less explicit
- below 0.75: do not emit

Use the shortest label that preserves meaning. Values should be one plain sentence. Source excerpts must be exact substrings from user messages. If no durable candidates are present, return {"candidates":[]}."""


LLM_SYNTHESIS_DEVELOPER_PROMPT = """Analyze this session for durable user-model candidates.

Messages are provided as an array. Use each message's array index as source_message_index. Only user messages may be used as source evidence.

Return exactly this JSON shape:
{
  "candidates": [
    {
      "section_key": "active_projects",
      "label": "Short label",
      "value": "One sentence grounded in the user message.",
      "confidence": 0.82,
      "source_excerpt": "Exact substring from a user message.",
      "source_message_index": 3,
      "source_message_role": "user"
    }
  ]
}

Extraction guidance:
- active_projects: ongoing work or projects the user is actively building, writing, planning, debugging, or maintaining.
- recurring_worries: explicit concern, stress, anxiety, or repeated mental load. Do not diagnose.
- stated_goals: explicit aims, goals, intentions, or desired outcomes.
- important_people: named people with personal or work relevance. Do not emit generic roles without a name.
- mood_trend: explicit self-reported emotional state only.
- communication_preferences: how the user wants Joi to respond or behave.
- recent_wins: completed work, breakthroughs, shipped items, or positive outcomes.
- open_loops: unresolved tasks, follow-ups, reminders, or decisions.

Drop anything that is temporary, vague, generic, or unsupported by an exact user-message excerpt."""


def build_llm_synthesis_prompt(messages: list[Any]) -> str:
    """Build the dry-run extraction prompt for the configured chat provider."""
    message_payload = [
        {
            "role": str(getattr(message, "role", "") or ""),
            "content": str(getattr(message, "content", "") or ""),
        }
        for message in messages
    ]
    return "\n\n".join(
        [
            "System prompt:",
            LLM_SYNTHESIS_SYSTEM_PROMPT,
            "Developer prompt:",
            LLM_SYNTHESIS_DEVELOPER_PROMPT,
            "Messages JSON:",
            json.dumps(message_payload, ensure_ascii=False),
        ]
    )


def parse_llm_candidates(
    raw_response: str,
    messages: list[Any],
    *,
    user_id: str = "default",
    corrections: list[dict] | None = None,
    existing_sections: list[Any] | None = None,
    include_skipped: bool = False,
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
        if include_skipped or (
            not candidate.blocked_by_correction and not candidate.duplicate_of_existing
        )
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

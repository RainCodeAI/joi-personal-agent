from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

@dataclass
class SynthesisCandidate:
    candidate_id: str
    section_key: str
    label: str
    value: str
    confidence: float
    inference_method: str = "pattern"
    trigger_phrase: str = ""
    source_excerpt: str = ""
    source_message_role: str = "user"
    source_message_index: int = 0
    blocked_by_correction: bool = False
    duplicate_of_existing: bool = False


# ---------------------------------------------------------------------------
# Pattern definitions per section
# ---------------------------------------------------------------------------

_PATTERNS: dict[str, list[str]] = {
    "stated_goals": [
        r"my goal is\s+(.+)",
        r"i want to\s+(.+)",
        r"i'm trying to\s+(.+)",
        r"i'd like to\s+(.+)",
        r"i hope to\s+(.+)",
        r"one of my goals\s+(?:is\s+)?(.+)",
        r"i'm aiming to\s+(.+)",
    ],
    "active_projects": [
        r"i'm working on\s+(.+)",
        r"i've been working on\s+(.+)",
        r"i'm building\s+(.+)",
        r"i've been building\s+(.+)",
        r"working on a\s+(.+)",
    ],
    "recurring_worries": [
        r"i'm worried about\s+(.+)",
        r"i'm stressed(?:\s+about\s+(.+))?",
        r"it's stressing me\s*(.+)?",
        r"i keep thinking about\s+(.+)",
        r"it's bothering me\s*(.+)?",
        r"i'm anxious about\s+(.+)",
        r"keeps me up\s*(.+)?",
    ],
    "open_loops": [
        r"i still haven't\s+(.+)",
        r"i need to follow up\s*(?:on\s+)?(.+)?",
        r"i forgot to\s+(.+)",
        r"remind me\s+(?:to\s+)?(.+)",
        r"i haven't done\s+(.+)",
        r"i should get around to\s+(.+)",
    ],
    "communication_preferences": [
        r"i prefer when you\s+(.+)",
        r"i like when you\s+(.+)",
        r"please don't\s+(.+)",
        r"can you just\s+(.+)",
        r"i'd rather you\s+(.+)",
        r"stop saying\s+(.+)",
        r"be more\s+(concise|direct|brief|clear)",
        r"less\s+(verbose|formal|wordy)",
    ],
    "recent_wins": [
        r"i finally\s+(.+)",
        r"i finished\s+(.+)",
        r"i got the\s+(.+)\s+working",
        r"it worked\b(.+)?",
        r"i managed to\s+(.+)",
        r"i achieved\s+(.+)",
        r"we shipped\s+(.+)",
        r"i completed\s+(.+)",
    ],
    "mood_trend": [
        r"i'm (excited|really excited) about",
        r"feeling (good|great|amazing|fantastic)",
        r"really happy about",
        r"(pumped|energised|energized) (?:about|for)?",
        r"(exhausted|burned out|burnt out)",
        r"i'm (frustrated|frustrated with)",
        r"feeling (low|down|awful|terrible)",
        r"(drained|struggling) (?:with|to)?",
    ],
    "important_people": [
        r"my (friend|partner|wife|husband|girlfriend|boyfriend|mom|dad|mother|father|sister|brother|boss|coworker|colleague)\s+([A-Z][A-Za-z'-]*(?:\s+[A-Z][A-Za-z'-]*)?)",
        r"([A-Z][A-Za-z'-]*(?:\s+[A-Z][A-Za-z'-]*)?)\s+is my\s+(friend|partner|wife|husband|girlfriend|boyfriend|mom|dad|mother|father|sister|brother|boss|coworker|colleague)",
    ],
}

_MOOD_POSITIVE = {"excited", "really excited", "good", "great", "amazing", "fantastic", "pumped", "energised", "energized"}
_MOOD_NEGATIVE = {"exhausted", "burned out", "burnt out", "frustrated", "low", "down", "awful", "terrible", "drained", "struggling"}

_SECTION_LABELS: dict[str, str] = {
    "stated_goals": "Stated goal",
    "active_projects": "Active project",
    "recurring_worries": "Recurring worry",
    "open_loops": "Open loop",
    "communication_preferences": "Communication preference",
    "recent_wins": "Recent win",
    "mood_trend": "Mood signal",
    "important_people": "Important person",
}

_MIN_CONFIDENCE = 0.55


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_subject(raw: str | None) -> str:
    if not raw:
        return ""
    s = raw.strip().rstrip(".,!?")
    # Truncate at sentence boundary or 80 chars
    for sep in [".", "!", "?", ",", " because ", " but ", " and "]:
        idx = s.find(sep)
        if 0 < idx < 80:
            s = s[:idx]
            break
    s = re.sub(r"^(?:a|an|the)\s+", "", s, flags=re.IGNORECASE)
    return s[:120].strip()


def _sentence_containing(text: str, pattern: re.Pattern) -> str:
    for sentence in re.split(r"[.!?]", text):
        if pattern.search(sentence):
            return sentence.strip()
    return text[:120]


def _label_for(section: str, subject: str) -> str:
    prefix = _SECTION_LABELS.get(section, section.replace("_", " ").title())
    if subject:
        cap = subject[:1].upper() + subject[1:]
        return cap[:80]
    return prefix


def _value_for(section: str, subject: str, trigger: str, excerpt: str) -> str:
    if section == "mood_trend":
        word = subject.lower()
        polarity = "positive" if word in _MOOD_POSITIVE else "negative" if word in _MOOD_NEGATIVE else "mixed"
        return f"User expressed a {polarity} mood signal: \"{excerpt.strip()}\""
    if section == "communication_preferences":
        return f"User preference noted: {excerpt.strip()}"
    if section == "open_loops":
        return f"Unresolved item: {excerpt.strip()}"
    if section == "important_people":
        return f"User mentioned an important person: {excerpt.strip()}"
    if subject:
        return f"{excerpt.strip()}"
    return f"Detected via pattern \"{trigger}\" in session."


def _subject_for(section: str, match: re.Match) -> str:
    if section != "important_people":
        return _clean_subject(match.group(1) if match.lastindex and match.lastindex >= 1 else "")

    raw_pattern = match.re.pattern
    if raw_pattern.startswith("my "):
        name = match.group(2) if match.lastindex and match.lastindex >= 2 else ""
        relation = match.group(1) if match.lastindex and match.lastindex >= 1 else ""
    else:
        name = match.group(1) if match.lastindex and match.lastindex >= 1 else ""
        relation = match.group(2) if match.lastindex and match.lastindex >= 2 else ""

    name = _clean_person_name(_clean_subject(name))
    relation = _clean_subject(relation)
    if name and relation:
        return f"{name} ({relation})"
    return name or relation


def _clean_person_name(raw: str) -> str:
    words = raw.split()
    kept: list[str] = []
    for word in words:
        stripped = word.strip(".,;:()[]{}")
        if not stripped:
            continue
        if stripped[0].isupper() or stripped.isupper():
            kept.append(stripped)
            continue
        break
    return " ".join(kept) or raw


def _is_low_value_subject(section: str, subject: str) -> bool:
    low = subject.lower().strip()
    if not low:
        return False
    if section == "stated_goals":
        conversational_starts = (
            "know ",
            "ask ",
            "talk ",
            "chat ",
            "hear from you",
            "tell you",
            "see what",
            "understand what",
        )
        return low.startswith(conversational_starts)
    if section == "active_projects":
        return low in {"it", "this", "that", "things", "stuff"}
    return False


# ---------------------------------------------------------------------------
# Correction block helpers
# ---------------------------------------------------------------------------

def _build_blocked_ids(corrections: list[dict]) -> set[str]:
    blocked = set()
    for c in corrections:
        if c.get("action") in {"hide", "delete"} and c.get("item_id"):
            blocked.add(str(c["item_id"]))
    return blocked


def _build_confirmed_ids(corrections: list[dict]) -> set[str]:
    confirmed = set()
    for c in corrections:
        if c.get("action") in {"confirm", "edit", "add"} and c.get("item_id"):
            confirmed.add(str(c["item_id"]))
    return confirmed


def _existing_labels(sections: list[Any]) -> set[str]:
    labels: set[str] = set()
    for section in sections:
        for item in getattr(section, "items", []) or []:
            lbl = str(getattr(item, "label", "") or "").strip().lower()
            if lbl:
                labels.add(lbl)
    return labels


def _is_duplicate(candidate_label: str, existing_labels: set[str]) -> bool:
    cl = candidate_label.lower()
    for el in existing_labels:
        if cl in el or el in cl:
            return True
    return False


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_candidates(
    messages: list[Any],
    *,
    user_id: str = "default",
    corrections: list[dict] | None = None,
    existing_sections: list[Any] | None = None,
    include_skipped: bool = False,
) -> list[SynthesisCandidate]:
    """
    Run pattern-based extraction over a list of ChatMessage objects.

    Returns SynthesisCandidate items above MIN_CONFIDENCE.
    Items blocked by corrections or duplicating existing items are flagged
    (blocked_by_correction / duplicate_of_existing) and excluded from the
    default return. Set include_skipped=True for diagnostics and dry-run review.
    """
    corrections = corrections or []
    existing_sections = existing_sections or []

    blocked_ids = _build_blocked_ids(corrections)
    existing = _existing_labels(existing_sections)

    seen_labels: dict[str, SynthesisCandidate] = {}  # label → best candidate
    results: list[SynthesisCandidate] = []

    for msg_idx, msg in enumerate(messages):
        if getattr(msg, "role", "") != "user":
            continue
        content = str(getattr(msg, "content", "") or "")
        if not content.strip():
            continue
        for section, raw_patterns in _PATTERNS.items():
            for raw_pat in raw_patterns:
                compiled = re.compile(raw_pat, re.IGNORECASE)
                m = compiled.search(content)
                if not m:
                    continue

                trigger = raw_pat
                subject = _subject_for(section, m)
                if _is_low_value_subject(section, subject):
                    continue
                excerpt = _sentence_containing(content, compiled)
                label = _label_for(section, subject)
                value = _value_for(section, subject, trigger, excerpt)

                if not label or not value:
                    continue

                confidence = 0.80 if subject else 0.60
                if confidence < _MIN_CONFIDENCE:
                    continue

                candidate_id = f"{section}:synth:{uuid.uuid5(uuid.NAMESPACE_DNS, f'{user_id}:{label.lower()}')}"

                blocked = candidate_id in blocked_ids
                duplicate = _is_duplicate(label, existing)

                candidate = SynthesisCandidate(
                    candidate_id=candidate_id,
                    section_key=section,
                    label=label,
                    value=value,
                    confidence=confidence,
                    trigger_phrase=trigger,
                    source_excerpt=excerpt,
                    source_message_role="user",
                    source_message_index=msg_idx,
                    blocked_by_correction=blocked,
                    duplicate_of_existing=duplicate,
                )

                label_key = f"{section}:{label.lower()}"
                if label_key not in seen_labels:
                    seen_labels[label_key] = candidate
                else:
                    # Keep the higher-confidence instance
                    if confidence > seen_labels[label_key].confidence:
                        seen_labels[label_key] = candidate

    for candidate in seen_labels.values():
        if include_skipped or (
            not candidate.blocked_by_correction and not candidate.duplicate_of_existing
        ):
            results.append(candidate)

    return results

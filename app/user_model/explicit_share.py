from __future__ import annotations

import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Trigger patterns — ordered by specificity, most specific first
# ---------------------------------------------------------------------------

_TRIGGERS: list[tuple[str, re.Pattern]] = [
    ("joi_remember", re.compile(r"joi[,.]?\s+remember\s+(?:that\s+)?(.+)", re.IGNORECASE)),
    ("remember_that", re.compile(r"^remember\s+that\s+(.+)", re.IGNORECASE)),
    ("remember_this", re.compile(r"^remember\s+this[:\s]+(.+)", re.IGNORECASE)),
    ("i_want_you_to_know", re.compile(r"i\s+want\s+you\s+to\s+know\s+(?:that\s+)?(.+)", re.IGNORECASE)),
    ("keep_in_mind", re.compile(r"keep\s+in\s+mind\s+(?:that\s+)?(.+)", re.IGNORECASE)),
    ("note_that", re.compile(r"(?:please\s+)?note\s+that\s+(.+)", re.IGNORECASE)),
    ("you_should_know", re.compile(r"you\s+should\s+know\s+(?:that\s+)?(.+)", re.IGNORECASE)),
    ("dont_forget", re.compile(r"don'?t\s+forget\s+(?:that\s+)?(.+)", re.IGNORECASE)),
    ("just_so_you_know", re.compile(r"just\s+so\s+you\s+know[,:]?\s+(.+)", re.IGNORECASE)),
    ("i_should_tell_you", re.compile(r"i\s+(?:should|want to)\s+tell\s+you\s+(?:that\s+)?(.+)", re.IGNORECASE)),
    ("for_context", re.compile(r"^for\s+context[,:]?\s+(.+)", re.IGNORECASE)),
]

# ---------------------------------------------------------------------------
# Section routing keywords — ordered most-specific first so broad terms
# like "building" or "overwhelm" don't shadow more precise matches.
# ---------------------------------------------------------------------------

_SECTION_ROUTING: list[tuple[str, set[str]]] = [
    ("communication_preferences", {"prefer", "like when you", "don't like when", "please don't", "rather you", "more concise", "more direct"}),
    ("important_people",       {"my friend", "my partner", "my colleague", "my boss", "my family",
                                "my mom", "my dad", "my sister", "my brother", "my wife", "my husband",
                                "my girlfriend", "my boyfriend", "my coworker"}),
    ("recent_wins",            {"finished", "completed", "achieved", "shipped", "got it working", "managed to", "finally"}),
    ("open_loops",             {"still need to", "haven't done", "need to follow up", "forgot to", "remind me"}),
    ("recurring_worries",      {"worried", "anxious", "stress", "concern", "nervous", "scared", "afraid", "overwhelm"}),
    ("stated_goals",           {"goal", "want to", "trying to", "aiming", "hope to", "plan to", "intend to"}),
    ("active_projects",        {"working on", "building", "project", "developing", "making", "coding", "writing"}),
]

_DEFAULT_SECTION = "character_notes"


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

@dataclass
class ShareDetection:
    trigger: str
    raw_excerpt: str          # the full matched text after the trigger
    label: str                # short display label (first ~60 chars of excerpt)
    value: str                # the full fact sentence
    section_key: str
    confidence: float = 0.95  # explicit sharing is always high-confidence


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_explicit_share(text: str) -> ShareDetection | None:
    """
    Return a ShareDetection if the message contains an explicit sharing intent,
    otherwise None.
    """
    text = text.strip()
    for trigger_name, pattern in _TRIGGERS:
        m = pattern.search(text)
        if not m:
            continue
        excerpt = m.group(1).strip().rstrip(".,!?")
        if not excerpt or len(excerpt.split()) < 2:
            continue

        label = _make_label(excerpt)
        section = _route_section(excerpt)

        return ShareDetection(
            trigger=trigger_name,
            raw_excerpt=excerpt,
            label=label,
            value=excerpt,
            section_key=section,
        )
    return None


def acknowledgement_hint(detection: ShareDetection) -> str:
    """
    Build a short system-level hint that tells Joi the user deliberately
    shared something and asks for a quiet, natural acknowledgement.
    """
    return (
        f"[The user just deliberately shared something with you: \"{detection.raw_excerpt}\". "
        f"You've noted it. Acknowledge this briefly and naturally — one quiet sentence is enough. "
        f"Don't repeat their exact words back or enumerate what you stored. Then continue the conversation normally.]"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_label(excerpt: str) -> str:
    # Use first clause (up to first comma, semicolon, or 60 chars)
    for sep in [",", ";", " because ", " and ", " but "]:
        idx = excerpt.find(sep)
        if 0 < idx <= 60:
            return excerpt[:idx].strip()
    return excerpt[:60].strip()


def _route_section(excerpt: str) -> str:
    low = excerpt.lower()
    for section_key, keywords in _SECTION_ROUTING:
        if any(kw in low for kw in keywords):
            return section_key
    return _DEFAULT_SECTION

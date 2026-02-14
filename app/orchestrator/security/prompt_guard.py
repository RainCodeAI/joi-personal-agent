"""PromptGuard — Input sanitization before anything hits the LLM.

Catches common prompt-injection patterns, encoded payloads, and
enforces max-length limits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Tuple

# Maximum user-input length (characters).  Configurable via caller.
DEFAULT_MAX_INPUT_LENGTH = 4_000

# ── compiled pattern list ─────────────────────────────────────────────────
# Each entry: (human-readable tag, compiled regex)
_INJECTION_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("system_override",      re.compile(r"(^|\W)system\s*:", re.IGNORECASE)),
    ("ignore_instructions",  re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|context)", re.IGNORECASE)),
    ("new_instructions",     re.compile(r"(new|different|updated|revised)\s+instructions?\s*:", re.IGNORECASE)),
    ("role_hijack",          re.compile(r"you\s+are\s+now\s+(a|an|the)\b", re.IGNORECASE)),
    ("delimiter_injection",  re.compile(r"-{5,}|={5,}|#{5,}")),
    ("markdown_code_fence",  re.compile(r"```\s*(system|admin|root)", re.IGNORECASE)),
    ("prompt_leak_request",  re.compile(r"(repeat|show|display|reveal)\s+(your|the)\s+(system\s+)?(prompt|instructions)", re.IGNORECASE)),
    ("base64_payload",       re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")),
    ("unicode_escape",       re.compile(r"\\u[0-9a-fA-F]{4}")),
    ("xml_tag_injection",    re.compile(r"<\s*/?\s*(system|admin|root|prompt)\s*>", re.IGNORECASE)),
]


@dataclass
class SanitizeResult:
    """Outcome of a ``PromptGuard.sanitize()`` call."""
    text: str
    threats_detected: List[str] = field(default_factory=list)
    was_truncated: bool = False

    @property
    def is_clean(self) -> bool:
        return len(self.threats_detected) == 0 and not self.was_truncated


class PromptGuard:
    """Stateless input-sanitization helper.

    Usage::

        guard = PromptGuard()
        result = guard.sanitize(user_input)
        if not result.is_clean:
            log.warning("Threats: %s", result.threats_detected)
        prompt = result.text   # safe to pass to the LLM
    """

    def __init__(self, max_length: int = DEFAULT_MAX_INPUT_LENGTH) -> None:
        self.max_length = max_length

    def sanitize(self, text: str) -> SanitizeResult:
        """Return sanitized text + list of detected threat tags."""
        threats: List[str] = []
        was_truncated = False

        # 1. Length enforcement
        if len(text) > self.max_length:
            text = text[: self.max_length]
            was_truncated = True

        # 2. Pattern scanning
        for tag, pattern in _INJECTION_PATTERNS:
            if pattern.search(text):
                threats.append(tag)

        # 3. Strip dangerous patterns (keep text usable but neutralised)
        if threats:
            # Remove system-override lines
            text = re.sub(r"(?i)(^|\n)\s*system\s*:.*", "", text)
            # Collapse long delimiter runs
            text = re.sub(r"[-=]{5,}", "---", text)
            # Remove XML-style injections
            text = re.sub(r"<\s*/?\s*(system|admin|root|prompt)\s*>", "", text, flags=re.IGNORECASE)

        return SanitizeResult(
            text=text.strip(),
            threats_detected=threats,
            was_truncated=was_truncated,
        )

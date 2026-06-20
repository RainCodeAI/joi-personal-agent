from __future__ import annotations

import logging
import re
from typing import Any


_SECRET_PATTERNS = (
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "[REDACTED_TOKEN]"),
    (
        re.compile(
            r"(?i)\b(api[_ -]?key|secret|password|passwd|token)\b"
            r"(\s*[:=]\s*)([^\s,;]{4,})"
        ),
        r"\1\2[REDACTED]",
    ),
    (
        re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
        "[REDACTED_PAYMENT_NUMBER]",
    ),
    (
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[REDACTED_SSN]",
    ),
)


def redact_sensitive_text(text: str) -> str:
    sanitized = text
    for pattern, replacement in _SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def compact_text(text: str, *, max_chars: int = 1800) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    compacted = "\n".join(line for line in lines if line)
    return compacted[:max_chars]


def extract_local_ocr(image: Any) -> tuple[str, str]:
    """Return sanitized OCR text and capability status without external calls."""
    try:
        import pytesseract
    except ImportError:
        return "", "unavailable"

    try:
        text = pytesseract.image_to_string(image)
    except Exception as exc:
        logging.info("Local screen OCR unavailable: %s", exc)
        return "", "unavailable"

    return compact_text(redact_sensitive_text(text)), "complete"


def sanitize_capture_metadata(metadata: dict[str, Any] | None) -> dict[str, str]:
    if not metadata:
        return {}

    allowed = {"display_surface", "source_label", "width", "height"}
    sanitized: dict[str, str] = {}
    for key, value in metadata.items():
        if key not in allowed or value is None:
            continue
        clean_value = compact_text(redact_sensitive_text(str(value)), max_chars=240)
        if clean_value:
            sanitized[key] = clean_value
    return sanitized


def build_screen_context(
    *,
    visual_description: str,
    ocr_text: str,
    metadata: dict[str, str],
) -> str:
    parts = [f"Visual description: {visual_description}"]
    if metadata:
        source_label = metadata.get("source_label")
        display_surface = metadata.get("display_surface")
        dimensions = "x".join(
            value for value in (metadata.get("width"), metadata.get("height")) if value
        )
        metadata_parts = [
            value
            for value in (
                f"selected source '{source_label}'" if source_label else None,
                f"type {display_surface}" if display_surface else None,
                f"{dimensions}px" if dimensions else None,
            )
            if value
        ]
        if metadata_parts:
            parts.append("Capture metadata: " + ", ".join(metadata_parts))
    if ocr_text:
        parts.append(f"Visible text (local OCR, sensitive values redacted):\n{ocr_text}")
    return "\n".join(parts)

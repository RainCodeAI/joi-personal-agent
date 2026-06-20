from __future__ import annotations

from app.tools.screen_context import (
    build_screen_context,
    compact_text,
    redact_sensitive_text,
    sanitize_capture_metadata,
)


def test_redact_sensitive_text_masks_common_credentials() -> None:
    fake_api_key = "sk-" + ("a" * 26)
    sanitized = redact_sensitive_text(
        f"password=hunter2 api_key={fake_api_key} "
        "card 4111 1111 1111 1111 ssn 123-45-6789"
    )

    assert "hunter2" not in sanitized
    assert fake_api_key not in sanitized
    assert "4111 1111 1111 1111" not in sanitized
    assert "123-45-6789" not in sanitized
    assert sanitized.count("[REDACTED") >= 4


def test_capture_metadata_is_allowlisted_compacted_and_redacted() -> None:
    metadata = sanitize_capture_metadata(
        {
            "display_surface": "window",
            "source_label": "Terminal   password=hunter2",
            "width": 1920,
            "height": 1080,
            "process_id": 1234,
        }
    )

    assert metadata == {
        "display_surface": "window",
        "source_label": "Terminal password=[REDACTED]",
        "width": "1920",
        "height": "1080",
    }


def test_screen_context_combines_metadata_visuals_and_ocr() -> None:
    context = build_screen_context(
        visual_description="a terminal showing an error",
        ocr_text=compact_text("Traceback\n  File app.py"),
        metadata={
            "display_surface": "window",
            "source_label": "Terminal",
            "width": "1280",
            "height": "720",
        },
    )

    assert "a terminal showing an error" in context
    assert "selected source 'Terminal'" in context
    assert "1280x720px" in context
    assert "Traceback" in context

"""Structured vision results keep operational failures out of sight descriptions."""

from app.tools import vision_clip


def test_unavailable_model_returns_failure_not_description(monkeypatch):
    monkeypatch.setattr(vision_clip, "_VISION_AVAILABLE", False)

    result = vision_clip.describe_image_result(object())

    assert result.ok is False
    assert result.description is None
    assert result.error_code == "model_unavailable"


def test_caption_exception_is_logged_as_failure_without_leaking_details(monkeypatch):
    monkeypatch.setattr(vision_clip, "_VISION_AVAILABLE", True)

    def fail_pipeline():
        raise RuntimeError("private model path and internal details")

    monkeypatch.setattr(vision_clip, "get_pipeline", fail_pipeline)

    result = vision_clip.describe_image_result(object())

    assert result.ok is False
    assert result.description is None
    assert result.error_code == "processing_failed"

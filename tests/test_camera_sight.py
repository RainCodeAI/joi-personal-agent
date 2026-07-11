"""Camera sight must stay consented, truthful, and transient."""

import asyncio

import pytest
from fastapi import HTTPException

from app.api import v2 as api_v2
from app.api.v2_models import ChatAttachmentRequest, VisionAnalyzeRequest
from app.tools.vision_clip import VisionDescriptionResult


ONE_PIXEL_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+"
    "A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def camera_attachment(**overrides) -> ChatAttachmentRequest:
    values = {
        "id": "camera-1",
        "kind": "image",
        "name": "camera.jpg",
        "media_type": "image/jpeg",
        "data_url": ONE_PIXEL_PNG,
        "source": "camera_snapshot",
        "capture_metadata": {},
    }
    values.update(overrides)
    return ChatAttachmentRequest(**values)


def test_camera_snapshot_requires_enabled_policy(monkeypatch):
    monkeypatch.setattr(api_v2.perception_policy, "get", lambda: {"camera_enabled": False})

    with pytest.raises(HTTPException) as exc:
        api_v2._attachment_context(camera_attachment())

    assert exc.value.status_code == 403
    assert "Camera access is disabled" in str(exc.value.detail)


def test_camera_snapshot_requires_real_image_data(monkeypatch):
    monkeypatch.setattr(api_v2.perception_policy, "get", lambda: {"camera_enabled": True})
    attachment = camera_attachment(
        media_type="image/jpeg",
        data_url="data:text/plain;base64,aGVsbG8=",
    )

    with pytest.raises(HTTPException) as exc:
        api_v2._attachment_context(attachment)

    assert exc.value.status_code == 422
    assert "image data" in str(exc.value.detail)


def test_successful_camera_glance_uses_first_person_context_and_drops_raw_frame(monkeypatch):
    monkeypatch.setattr(api_v2.perception_policy, "get", lambda: {"camera_enabled": True})
    monkeypatch.setattr(
        api_v2.vision_clip,
        "describe_image_result",
        lambda image: VisionDescriptionResult(description="a person in a blue shirt"),
    )

    resource, context = api_v2._attachment_context(camera_attachment())

    assert resource.source == "camera_snapshot"
    assert resource.preview_text == "a person in a blue shirt"
    assert resource.ocr_status == "not_requested"
    assert "You just took a live look" in context
    assert "a person in a blue shirt" in context
    assert "data_url" not in resource.model_dump()
    assert "base64" not in context


def test_failed_camera_analysis_never_becomes_an_observation(monkeypatch):
    monkeypatch.setattr(api_v2.perception_policy, "get", lambda: {"camera_enabled": True})
    monkeypatch.setattr(
        api_v2.vision_clip,
        "describe_image_result",
        lambda image: VisionDescriptionResult(error_code="model_unavailable"),
    )

    resource, context = api_v2._attachment_context(camera_attachment())

    assert resource.preview_text == "Camera glance could not be analyzed."
    assert "You can see" not in context
    assert "Do not claim to see any details" in context
    assert "model_unavailable" not in context
    assert "data_url" not in resource.model_dump()


def test_malformed_camera_image_fails_without_leaking_decoder_details(monkeypatch):
    monkeypatch.setattr(api_v2.perception_policy, "get", lambda: {"camera_enabled": True})
    attachment = camera_attachment(data_url="data:image/jpeg;base64,bm90IGFuIGltYWdl")

    resource, context = api_v2._attachment_context(attachment)

    assert resource.preview_text == "Camera glance could not be processed."
    assert "Do not claim to see any details" in context
    assert "cannot identify image file" not in context
    assert "You can see" not in context


def test_vision_endpoint_requires_enabled_camera_policy(monkeypatch):
    monkeypatch.setattr(api_v2.perception_policy, "get", lambda: {"camera_enabled": False})

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            api_v2.analyze_vision_snapshot(
                VisionAnalyzeRequest(session_id="camera-session", data_url=ONE_PIXEL_PNG)
            )
        )

    assert exc.value.status_code == 403


def test_vision_endpoint_reports_model_unavailable_instead_of_fake_description(monkeypatch):
    monkeypatch.setattr(api_v2.perception_policy, "get", lambda: {"camera_enabled": True})
    monkeypatch.setattr(
        api_v2.vision_clip,
        "describe_image_result",
        lambda image: VisionDescriptionResult(error_code="model_unavailable"),
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            api_v2.analyze_vision_snapshot(
                VisionAnalyzeRequest(session_id="camera-session", data_url=ONE_PIXEL_PNG)
            )
        )

    assert exc.value.status_code == 503
    assert exc.value.detail == "Vision analysis is unavailable"

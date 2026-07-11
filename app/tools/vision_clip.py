import logging
from dataclasses import dataclass
from typing import Literal

# Keep PIL independent of transformers: a transformers/torch import failure must
# not also unbind Image, and both names must always exist so they stay patchable.
try:
    from PIL import Image
except Exception:
    Image = None

try:
    from transformers import pipeline
    _VISION_AVAILABLE = True
except Exception:
    logging.warning("vision_clip: transformers/torch unavailable — image description disabled")
    pipeline = None
    _VISION_AVAILABLE = False

_caption_pipeline = None

VisionErrorCode = Literal[
    "model_unavailable",
    "pipeline_unavailable",
    "empty_description",
    "processing_failed",
]


@dataclass(frozen=True)
class VisionDescriptionResult:
    """Structured vision result so failures cannot masquerade as observations."""

    description: str | None = None
    error_code: VisionErrorCode | None = None

    @property
    def ok(self) -> bool:
        return bool(self.description) and self.error_code is None


def get_pipeline():
    global _caption_pipeline
    if not _VISION_AVAILABLE:
        return None
    if _caption_pipeline is None:
        logging.info("Lazy loading vision captioning model...")
        _caption_pipeline = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
    return _caption_pipeline

def describe_image_result(image_input) -> VisionDescriptionResult:
    """Generate a description without encoding failures as descriptive text."""
    if not _VISION_AVAILABLE:
        return VisionDescriptionResult(error_code="model_unavailable")
    try:
        pipe = get_pipeline()
        if pipe is None:
            return VisionDescriptionResult(error_code="pipeline_unavailable")
        if hasattr(image_input, "convert") and not isinstance(image_input, (str, bytes)):
            image = image_input.convert('RGB')
        else:
            image = Image.open(image_input).convert('RGB')
        
        # explicit generation args can be added if needed
        results = pipe(image)
        # results list of dicts, e.g. [{'generated_text': 'a photography of a cat'}]
        if results and len(results) > 0:
            description = str(results[0].get('generated_text', '')).strip()
            if description:
                return VisionDescriptionResult(description=description)
        return VisionDescriptionResult(error_code="empty_description")
    except Exception:
        logging.exception("vision_clip: image description failed")
        return VisionDescriptionResult(error_code="processing_failed")


def describe_image(image_input) -> str:
    """Backward-compatible text API for legacy UI callers.

    New camera and API paths should use :func:`describe_image_result` so they
    can branch on failure without treating an error message as something seen.
    """
    result = describe_image_result(image_input)
    if result.ok:
        return result.description or ""
    messages = {
        "model_unavailable": "Vision model unavailable (torch not loaded).",
        "pipeline_unavailable": "Vision pipeline unavailable.",
        "empty_description": "Could not describe image.",
        "processing_failed": "Error describing image.",
    }
    return messages.get(result.error_code, "Could not describe image.")

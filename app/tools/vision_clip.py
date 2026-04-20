import logging

try:
    from PIL import Image
    from transformers import pipeline
    _VISION_AVAILABLE = True
except Exception:
    logging.warning("vision_clip: transformers/torch unavailable — image description disabled")
    _VISION_AVAILABLE = False

_caption_pipeline = None

def get_pipeline():
    global _caption_pipeline
    if not _VISION_AVAILABLE:
        return None
    if _caption_pipeline is None:
        logging.info("Lazy loading vision captioning model...")
        _caption_pipeline = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
    return _caption_pipeline

def describe_image(image_input) -> str:
    """Generate a text description from a file path or PIL image."""
    if not _VISION_AVAILABLE:
        return "Vision model unavailable (torch not loaded)."
    try:
        pipe = get_pipeline()
        if pipe is None:
            return "Vision pipeline unavailable."
        if hasattr(image_input, "convert") and not isinstance(image_input, (str, bytes)):
            image = image_input.convert('RGB')
        else:
            image = Image.open(image_input).convert('RGB')
        
        # explicit generation args can be added if needed
        results = pipe(image)
        # results list of dicts, e.g. [{'generated_text': 'a photography of a cat'}]
        if results and len(results) > 0:
            return results[0].get('generated_text', "No description generated.")
        return "Could not describe image."
    except Exception as e:
        return f"Error describing image: {str(e)}"

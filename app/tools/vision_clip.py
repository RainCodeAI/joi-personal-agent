
from typing import Optional
from PIL import Image
import torch
from transformers import pipeline

# Global cache for the pipeline
_caption_pipeline = None

def get_pipeline():
    global _caption_pipeline
    if _caption_pipeline is None:
        print("Lazy loading vision model...")
        # "image-to-text" defaults to a high-quality captioning model (often BLIP or Git)
        # We specify model explicitly to ensure consistency if needed, but default is usually fine.
        # "Salesforce/blip-image-captioning-base" is a good balance of speed/quality.
        _caption_pipeline = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
    return _caption_pipeline

def describe_image(image_path: str) -> str:
    """Generate a text description (caption) for the given image."""
    try:
        pipe = get_pipeline()
        image = Image.open(image_path).convert('RGB')
        
        # explicit generation args can be added if needed
        results = pipe(image)
        # results list of dicts, e.g. [{'generated_text': 'a photography of a cat'}]
        if results and len(results) > 0:
            return results[0].get('generated_text', "No description generated.")
        return "Could not describe image."
    except Exception as e:
        return f"Error describing image: {str(e)}"

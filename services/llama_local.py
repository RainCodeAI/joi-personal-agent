"""Local GGUF model inference via llama-cpp-python (Phase 11).

Provides ~3x speedup on CPU vs HuggingFace transformers for chat generation.
Requires a .gguf model file — set GGUF_MODEL_PATH in .env.

Recommended models (4-bit quantized, ~4GB RAM):
- mistral-7b-instruct-v0.2.Q4_K_M.gguf
- llama-2-7b-chat.Q4_K_M.gguf
- phi-2.Q4_K_M.gguf
"""

import logging
from typing import Optional

from app.config import settings

log = logging.getLogger(__name__)

_llm = None  # Singleton


def _ensure_model():
    """Lazy-load the GGUF model. Returns the Llama instance or None."""
    global _llm
    if _llm is not None:
        return _llm

    if not settings.gguf_model_path:
        return None

    try:
        from llama_cpp import Llama

        log.info(f"Loading GGUF model: {settings.gguf_model_path}")
        _llm = Llama(
            model_path=settings.gguf_model_path,
            n_ctx=settings.gguf_n_ctx,
            n_gpu_layers=settings.gguf_n_gpu_layers,
            verbose=False,
        )
        log.info("GGUF model loaded.")
        return _llm
    except ImportError:
        log.warning("llama-cpp-python not installed. GGUF provider disabled.")
        return None
    except Exception as e:
        log.error(f"Failed to load GGUF model: {e}")
        return None


def is_available() -> bool:
    """Check if a GGUF model is configured and loadable."""
    return bool(settings.gguf_model_path) and _ensure_model() is not None


def generate(prompt: str, max_tokens: int = 256, temperature: float = 0.7) -> Optional[str]:
    """Generate text from the local GGUF model.

    Returns the generated text or None on failure.
    """
    llm = _ensure_model()
    if llm is None:
        return None

    try:
        output = llm(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=["User:", "\n\n\n"],
            echo=False,
        )
        text = output["choices"][0]["text"].strip()
        return text if text else None
    except Exception as e:
        log.error(f"GGUF generation error: {e}")
        return None


def chat(messages: list, max_tokens: int = 256, temperature: float = 0.7) -> Optional[str]:
    """Chat-style generation using the GGUF model's chat format.

    Args:
        messages: List of {"role": "user"/"assistant"/"system", "content": str}
    """
    llm = _ensure_model()
    if llm is None:
        return None

    try:
        output = llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = output["choices"][0]["message"]["content"].strip()
        return text if text else None
    except Exception as e:
        log.error(f"GGUF chat error: {e}")
        return None

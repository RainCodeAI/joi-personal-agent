from __future__ import annotations

import importlib.util
from typing import Any, Dict

import httpx
from fastapi import APIRouter

from app.config import settings
from app.memory.store import MemoryStore
from app.vault import get_secret
from services import llama_local

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

memory_store = MemoryStore()  # Init once for health checks

@router.get("/chroma/health")
def chroma_health():
    coll = memory_store.collection
    if coll is None:
        return {
            "status": "disabled",
            "name": None,
            "count": 0,
            "embed_dim_meta": None,
            "embedder_id_meta": None,
        }

    meta = coll.metadata or {}
    return {
        "status": "ok",
        "name": coll.name,
        "count": coll.count(),
        "embed_dim_meta": meta.get("embed_dim"),
        "embedder_id_meta": meta.get("embedder_id", "Not set")
    }


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _secret_configured(secret_name: str) -> bool:
    try:
        return bool(get_secret(secret_name))
    except Exception:
        return False


def _ollama_status() -> Dict[str, Any]:
    try:
        with httpx.Client(timeout=1.5) as client:
            response = client.get(f"{settings.ollama_host}/api/version")
            response.raise_for_status()
            data = response.json()
            return {
                "configured": True,
                "available": True,
                "host": settings.ollama_host,
                "version": data.get("version"),
            }
    except Exception as exc:
        return {
            "configured": True,
            "available": False,
            "host": settings.ollama_host,
            "error": str(exc),
        }


def _provider_diagnostics() -> Dict[str, Any]:
    return {
        "gguf": {
            "configured": bool(settings.gguf_model_path),
            "available": llama_local.is_available(),
            "model_path": bool(settings.gguf_model_path),
        },
        "ollama": _ollama_status(),
        "openai": {
            "configured": bool(settings.openai_api_key),
            "sdk_available": _module_available("openai"),
        },
        "grok": {
            "configured": bool(settings.xai_api_key),
            "sdk_available": _module_available("grokpy"),
        },
        "gemini": {
            "configured": bool(settings.gemini_api_key),
            "sdk_available": _module_available("google.generativeai"),
        },
    }


def _storage_diagnostics() -> Dict[str, Any]:
    db_mode = "external" if settings.database_url else "sqlite"
    vector_mode = "chroma" if memory_store.collection is not None else "sql_only"
    return {
        "airgap": settings.airgap,
        "database_mode": db_mode,
        "database_target": settings.database_url or settings.db_path,
        "vector_mode": vector_mode,
        "session_store": "sqlalchemy",
    }


def _media_diagnostics() -> Dict[str, Any]:
    openai_tts_available = bool(settings.openai_api_key and _module_available("openai"))
    elevenlabs_available = _module_available("elevenlabs")
    local_voice_available = _module_available("speech_recognition") and _module_available("pyttsx3")
    vision_available = _module_available("transformers") and _module_available("PIL")
    whisper_available = _module_available("whisper")

    return {
        "tts": {
            "openai": openai_tts_available,
            "elevenlabs_sdk": elevenlabs_available,
            "elevenlabs_configured": _secret_configured("elevenlabs_api_key"),
            "local_engine": local_voice_available,
        },
        "stt": {
            "google_local_stack": _module_available("speech_recognition"),
            "whisper_local": whisper_available,
            "microphone_stack": _module_available("pyaudio"),
        },
        "vision": {
            "captioning_stack": vision_available,
            "torch": _module_available("torch"),
        },
    }


@router.get("/runtime")
def runtime_health():
    return {
        "status": "ok",
        "providers": _provider_diagnostics(),
        "storage": _storage_diagnostics(),
        "media": _media_diagnostics(),
    }

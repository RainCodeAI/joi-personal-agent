from __future__ import annotations

import importlib.util
import shutil
from typing import Any, Dict

import httpx
from fastapi import APIRouter

from app.api.state import event_bus, hardware_bridge, initiative_scheduler, initiative_service, media_sessions
from app.config import settings
from app.db import engine as db_engine
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
    openai_sdk_available = _module_available("openai")
    grok_sdk_available = _module_available("grokpy")
    gemini_sdk_available = _module_available("google.generativeai")
    openai_configured = bool(settings.openai_api_key)
    grok_configured = bool(settings.xai_api_key)
    gemini_configured = bool(settings.gemini_api_key)

    return {
        "gguf": {
            "configured": bool(settings.gguf_model_path),
            "available": llama_local.is_available(),
            "model_path": bool(settings.gguf_model_path),
        },
        "ollama": _ollama_status(),
        "openai": {
            "configured": openai_configured,
            "available": openai_configured and openai_sdk_available,
            "sdk_available": openai_sdk_available,
        },
        "grok": {
            "configured": grok_configured,
            "available": grok_configured and grok_sdk_available,
            "sdk_available": grok_sdk_available,
        },
        "gemini": {
            "configured": gemini_configured,
            "available": gemini_configured and gemini_sdk_available,
            "sdk_available": gemini_sdk_available,
        },
    }


def _storage_diagnostics() -> Dict[str, Any]:
    db_mode = "external" if settings.database_url else "sqlite"
    vector_mode = "chroma" if memory_store.collection is not None else "sql_only"
    return {
        "airgap": settings.airgap,
        "available": db_engine is not None,
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
    pytesseract_available = _module_available("pytesseract")
    tesseract_path = shutil.which("tesseract")
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
            "ocr_wrapper": pytesseract_available,
            "ocr_executable": bool(tesseract_path),
            "ocr_available": pytesseract_available and bool(tesseract_path),
            "ocr_path": tesseract_path,
        },
    }


def _realtime_diagnostics() -> Dict[str, Any]:
    return {
        "available": True,
        "transport": "sse",
        "bus": "in_process",
        "subscriber_count": len(event_bus._subscribers),
        "recent_event_buffer": event_bus._history.maxlen,
        "tracked_media_sessions": len(media_sessions._sessions),
    }


def _hardware_bridge_diagnostics() -> Dict[str, Any]:
    diagnostics = hardware_bridge.get_bridge_snapshot()
    if not diagnostics.get("enabled"):
        diagnostics["note"] = "disabled until ambient hardware Phase 8 begins"
    elif not diagnostics.get("note"):
        diagnostics["note"] = f"mqtt {diagnostics.get('connection_state', 'unknown')}"
    return diagnostics


def _initiative_diagnostics() -> Dict[str, Any]:
    return {
        **initiative_service.diagnostics(),
        "scheduler": initiative_scheduler.diagnostics(),
    }


def _readiness_summary(
    providers: Dict[str, Any],
    storage: Dict[str, Any],
    media: Dict[str, Any],
    realtime: Dict[str, Any],
    hardware_bridge: Dict[str, Any],
    initiative: Dict[str, Any],
) -> Dict[str, Dict[str, str]]:
    provider_ready = any(bool(details.get("available")) for details in providers.values())
    tts_ready = any(
        bool(media.get("tts", {}).get(key))
        for key in ("openai", "elevenlabs_sdk", "local_engine")
    )
    stt_ready = any(
        bool(media.get("stt", {}).get(key))
        for key in ("google_local_stack", "whisper_local")
    )
    storage_ready = bool(storage.get("available")) or storage.get("database_mode") == "sqlite"
    realtime_ready = bool(realtime.get("available"))
    bridge_enabled = bool(hardware_bridge.get("enabled"))

    return {
        "providers": {
            "state": "ready" if provider_ready else "degraded",
            "summary": "provider route available" if provider_ready else "no provider route available",
        },
        "storage": {
            "state": "ready" if storage_ready else "degraded",
            "summary": f"{storage.get('database_mode', 'unknown')} / {storage.get('vector_mode', 'unknown')}",
        },
        "media": {
            "state": "ready" if (tts_ready and stt_ready) else "degraded",
            "summary": (
                "tts and stt ready"
                if (tts_ready and stt_ready)
                else f"tts {'ready' if tts_ready else 'missing'}, stt {'ready' if stt_ready else 'missing'}"
            ),
        },
        "realtime": {
            "state": "ready" if realtime_ready else "degraded",
            "summary": f"{realtime.get('transport', 'unknown')} transport",
        },
        "hardware_bridge": {
            "state": "disabled" if not bridge_enabled else ("ready" if hardware_bridge.get("available") else "degraded"),
            "summary": str(hardware_bridge.get("note") or "bridge status unknown"),
        },
        "initiative": {
            "state": "ready" if initiative.get("enabled") else "disabled",
            "summary": (
                f"{initiative.get('remaining_today', 0)} of {initiative.get('daily_limit', 0)} initiatives remaining today"
                if initiative.get("enabled")
                else "initiative disabled"
            ),
        },
    }


def build_runtime_diagnostics() -> Dict[str, Any]:
    providers = _provider_diagnostics()
    storage = _storage_diagnostics()
    media = _media_diagnostics()
    realtime = _realtime_diagnostics()
    hardware_bridge = _hardware_bridge_diagnostics()
    initiative = _initiative_diagnostics()
    readiness = _readiness_summary(providers, storage, media, realtime, hardware_bridge, initiative)
    status = (
        "ok"
        if all(
            readiness[key]["state"] == "ready"
            for key in ("providers", "storage", "media", "realtime")
        )
        else "degraded"
    )
    return {
        "status": status,
        "readiness": readiness,
        "providers": providers,
        "storage": storage,
        "media": media,
        "realtime": realtime,
        "hardware_bridge": hardware_bridge,
        "initiative": initiative,
    }


@router.get("/runtime")
def runtime_health():
    return build_runtime_diagnostics()

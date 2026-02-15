import time
from typing import Callable, Dict, Any, Optional, List

import httpx
import openai
import grokpy as grok  # Assuming grokpy
import google.generativeai as genai

from app.config import settings
from services.router_logging import log_inference


ProviderResult = Dict[str, Any]


def _persona_filter(response: str, mood: str) -> str:
    persona_note = " Respond in a calm, witty, precise manner, adapting to user mood: " + mood
    return response + persona_note


def _provider_result(success: bool, model: str, text: str = "", error: Optional[str] = None) -> ProviderResult:
    return {
        "success": success,
        "model": model,
        "text": text,
        "error": error,
    }


def call_ollama(prompt: str, context: Dict[str, Any]) -> ProviderResult:
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{settings.ollama_host}/api/generate",
                json={"model": settings.model_chat, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            data = response.json()
            text = data.get("response", "").strip()
            if text:
                return _provider_result(True, "ollama", text=text)
            return _provider_result(False, "ollama", error="Empty response from Ollama")
    except Exception as e:
        print(f"Provider failed: call_ollama, error: {e}")
        return _provider_result(False, "ollama", error=str(e))


def call_openai(prompt: str, context: Dict[str, Any]) -> ProviderResult:
    api_key = settings.openai_api_key
    if not api_key:
        return _provider_result(False, "gpt4o", error="OpenAI API key missing")
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content.strip()
        return _provider_result(True, "gpt4o", text=text)
    except Exception as e:
        print(f"Provider failed: call_openai, error: {e}")
        return _provider_result(False, "gpt4o", error=str(e))


def call_grok(prompt: str, context: Dict[str, Any]) -> ProviderResult:
    api_key = settings.xai_api_key
    if not api_key:
        return _provider_result(False, "grok", error="Grok API key missing")
    try:
        client = grok.Client(api_key=api_key)
        response = client.generate(prompt)
        text = response.strip() if response else ""
        if text:
            return _provider_result(True, "grok", text=text)
        return _provider_result(False, "grok", error="Empty response from Grok")
    except Exception as e:
        print(f"Provider failed: call_grok, error: {e}")
        return _provider_result(False, "grok", error=str(e))


def call_gemini(prompt: str, context: Dict[str, Any]) -> ProviderResult:
    api_key = settings.gemini_api_key
    if not api_key:
        return _provider_result(False, "gemini", error="Gemini API key missing")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        text = getattr(response, "text", "").strip()
        if text:
            return _provider_result(True, "gemini", text=text)
        return _provider_result(False, "gemini", error="Empty response from Gemini")
    except Exception as e:
        print(f"Provider failed: call_gemini, error: {e}")
        return _provider_result(False, "gemini", error=str(e))


def call_gguf(prompt: str, context: Dict[str, Any]) -> ProviderResult:
    """Local GGUF model via llama-cpp-python (Phase 11)."""
    try:
        from services.llama_local import is_available, generate
        if not is_available():
            return _provider_result(False, "gguf", error="GGUF model not configured")
        text = generate(prompt)
        if text:
            return _provider_result(True, "gguf", text=text)
        return _provider_result(False, "gguf", error="Empty response from GGUF")
    except Exception as e:
        print(f"Provider failed: call_gguf, error: {e}")
        return _provider_result(False, "gguf", error=str(e))


def multi_ai_response(prompt: str, context: Dict[str, Any]) -> ProviderResult:
    providers: List[Callable[[str, Dict[str, Any]], ProviderResult]] = [
        call_gguf,     # Phase 11: Local GGUF first (fastest, no API cost)
        call_ollama,
        call_openai,
        call_grok,
        call_gemini,
    ]

    route_attempts: List[str] = []
    errors = []
    overall_start = time.perf_counter()

    for provider_fn in providers:
        attempt_start = time.perf_counter()
        result = provider_fn(prompt, context)
        route_attempts.append(result["model"])
        latency_ms = int((time.perf_counter() - attempt_start) * 1000)

        log_inference(
            {
                "provider": result["model"],
                "success": result["success"],
                "latency_ms": latency_ms,
                "error": result.get("error"),
                "route": route_attempts.copy(),
            }
        )

        if result["success"] and result["text"]:
            result["errors"] = errors
            result["route"] = route_attempts
            return result

        errors.append({"provider": result["model"], "error": result.get("error")})

    log_inference(
        {
            "provider": "none",
            "success": False,
            "latency_ms": int((time.perf_counter() - overall_start) * 1000),
            "error": "All providers failed",
            "route": route_attempts,
        }
    )

    return {
        "success": False,
        "model": None,
        "text": "",
        "error": "All providers failed",
        "errors": errors,
        "route": route_attempts,
    }


def route_request(prompt: str, context: dict) -> dict:
    result = multi_ai_response(prompt, context)
    mood = context.get("mood", "neutral")

    if result["success"]:
        response_text = _persona_filter(result["text"], mood)
        model_used = result["model"]
    else:
        response_text = "All providers failed. Please try again later."
        model_used = "none"

    return {
        "response": response_text,
        "model_used": model_used,
        "errors": result.get("errors", []),
        "route": result.get("route", []),
    }

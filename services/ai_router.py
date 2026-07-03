import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Callable, Dict, List, Optional

import httpx

from app.config import settings
from services.router_logging import log_inference


logger = logging.getLogger(__name__)

ProviderResult = Dict[str, Any]
TokenCallback = Callable[[str], None]


def _provider_result(
    success: bool,
    model: str,
    text: str = "",
    error: Optional[str] = None,
    *,
    started: bool = False,
) -> ProviderResult:
    return {
        "success": success,
        "model": model,
        "text": text,
        "error": error,
        "started": started,
    }


def call_ollama(
    prompt: str,
    context: Dict[str, Any],
    on_token: TokenCallback | None = None,
) -> ProviderResult:
    started = False
    accumulated = ""
    try:
        call_timeout = float(settings.router_timeout) if settings.router_timeout else 60.0
        # read timeout applies per-chunk on streams, so long generations are fine
        # as long as tokens keep flowing; a hung Ollama no longer stalls forever.
        timeout = httpx.Timeout(timeout=call_timeout, connect=10.0, read=call_timeout)
        with httpx.Client(timeout=timeout) as client:
            if on_token is None:
                response = client.post(
                    f"{settings.ollama_host}/api/generate",
                    json={"model": settings.model_ollama, "prompt": prompt, "stream": False},
                )
                response.raise_for_status()
                data = response.json()
                text = data.get("response", "").strip()
                if text:
                    return _provider_result(True, "ollama", text=text)
                return _provider_result(False, "ollama", error="Empty response from Ollama")

            with client.stream(
                "POST",
                f"{settings.ollama_host}/api/generate",
                json={"model": settings.model_ollama, "prompt": prompt, "stream": True},
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    chunk = data.get("response", "")
                    if chunk:
                        started = True
                        accumulated += chunk
                        on_token(chunk)
                    if data.get("done"):
                        break

            text = accumulated.strip()
            if text:
                return _provider_result(True, "ollama", text=text, started=started)
            return _provider_result(
                False,
                "ollama",
                text=accumulated,
                error="Empty response from Ollama",
                started=started,
            )
    except Exception as e:
        logger.warning("Provider failed: ollama error=%s", e)
        return _provider_result(False, "ollama", text=accumulated, error=str(e), started=started)


def call_openai(
    prompt: str,
    context: Dict[str, Any],
    on_token: TokenCallback | None = None,
) -> ProviderResult:
    api_key = settings.openai_api_key
    if not api_key:
        return _provider_result(False, "gpt4o", error="OpenAI API key missing")

    started = False
    accumulated = ""
    try:
        import openai

        call_timeout = float(settings.router_timeout) if settings.router_timeout else 30.0
        client = openai.OpenAI(api_key=api_key, timeout=call_timeout)
        if on_token is None:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.choices[0].message.content.strip()
            return _provider_result(True, "gpt4o", text=text)

        stream = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        for chunk in stream:
            for choice in getattr(chunk, "choices", []):
                delta = getattr(choice, "delta", None)
                text = getattr(delta, "content", None)
                if not text:
                    continue
                started = True
                accumulated += text
                on_token(text)

        final_text = accumulated.strip()
        if final_text:
            return _provider_result(True, "gpt4o", text=final_text, started=started)
        return _provider_result(
            False,
            "gpt4o",
            text=accumulated,
            error="Empty response from OpenAI",
            started=started,
        )
    except Exception as e:
        logger.warning("Provider failed: openai error=%s", e)
        return _provider_result(False, "gpt4o", text=accumulated, error=str(e), started=started)


def call_grok(
    prompt: str,
    context: Dict[str, Any],
    on_token: TokenCallback | None = None,
) -> ProviderResult:
    api_key = settings.xai_api_key
    if not api_key:
        return _provider_result(False, "grok", error="Grok API key missing")

    started = False
    accumulated = ""
    try:
        # xAI is OpenAI-compatible; reuse the openai client with x.ai's base URL.
        import openai

        call_timeout = float(settings.router_timeout) if settings.router_timeout else 30.0
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
            timeout=call_timeout,
        )
        if on_token is None:
            response = client.chat.completions.create(
                model="grok-2-latest",
                messages=[{"role": "user", "content": prompt}],
            )
            text = (response.choices[0].message.content or "").strip()
            if text:
                return _provider_result(True, "grok", text=text)
            return _provider_result(False, "grok", error="Empty response from Grok")

        stream = client.chat.completions.create(
            model="grok-2-latest",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        for chunk in stream:
            for choice in getattr(chunk, "choices", []):
                delta = getattr(choice, "delta", None)
                text = getattr(delta, "content", None)
                if not text:
                    continue
                started = True
                accumulated += text
                on_token(text)

        final_text = accumulated.strip()
        if final_text:
            return _provider_result(True, "grok", text=final_text, started=started)
        return _provider_result(
            False, "grok", text=accumulated, error="Empty response from Grok", started=started
        )
    except Exception as e:
        logger.warning("Provider failed: grok error=%s", e)
        return _provider_result(False, "grok", text=accumulated, error=str(e), started=started)


def call_gemini(
    prompt: str,
    context: Dict[str, Any],
    on_token: TokenCallback | None = None,
) -> ProviderResult:
    api_key = settings.gemini_api_key
    if not api_key:
        return _provider_result(False, "gemini", error="Gemini API key missing")

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        text = getattr(response, "text", "").strip()
        if text:
            return _provider_result(True, "gemini", text=text)
        return _provider_result(False, "gemini", error="Empty response from Gemini")
    except Exception as e:
        logger.warning("Provider failed: gemini error=%s", e)
        return _provider_result(False, "gemini", error=str(e))


def call_gguf(
    prompt: str,
    context: Dict[str, Any],
    on_token: TokenCallback | None = None,
) -> ProviderResult:
    try:
        from services.llama_local import generate, is_available

        if not is_available():
            return _provider_result(False, "gguf", error="GGUF model not configured")
        text = generate(prompt)
        if text:
            return _provider_result(True, "gguf", text=text)
        return _provider_result(False, "gguf", error="Empty response from GGUF")
    except Exception as e:
        logger.warning("Provider failed: gguf error=%s", e)
        return _provider_result(False, "gguf", error=str(e))


def multi_ai_response(
    prompt: str,
    context: Dict[str, Any],
    on_token: TokenCallback | None = None,
) -> ProviderResult:
    if on_token is None:
        providers: List[Callable[[str, Dict[str, Any], TokenCallback | None], ProviderResult]] = [
            call_gguf,
            call_ollama,
            call_openai,
            call_grok,
            call_gemini,
        ]
    else:
        providers = [
            call_ollama,
            call_openai,
            call_gguf,
            call_grok,
            call_gemini,
        ]

    route_attempts: List[str] = []
    errors = []
    overall_start = time.perf_counter()

    for provider_fn in providers:
        attempt_start = time.perf_counter()
        result = provider_fn(prompt, context, on_token)
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

        if result.get("started"):
            errors.append({"provider": result["model"], "error": result.get("error")})
            return {
                "success": False,
                "model": result["model"],
                "text": result.get("text", ""),
                "error": result.get("error") or "Streaming provider failed",
                "errors": errors,
                "route": route_attempts,
                "started": True,
            }

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
    logger.error("All providers failed route=%s", route_attempts)

    return {
        "success": False,
        "model": None,
        "text": "",
        "error": "All providers failed",
        "errors": errors,
        "route": route_attempts,
    }


def route_request(
    prompt: str,
    context: dict,
    on_token: TokenCallback | None = None,
) -> dict:
    timeout = settings.router_timeout or 60
    # No context manager here: `with ThreadPoolExecutor(...)` calls shutdown(wait=True)
    # on exit, which blocks until the provider call finishes and defeats the timeout.
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(multi_ai_response, prompt, context, on_token)
    try:
        result = future.result(timeout=timeout)
    except FuturesTimeoutError:
        logger.error("Router timed out after %ds", timeout)
        return {
            "response": "Request timed out. Please try again.",
            "model_used": "none",
            "errors": [{"provider": "router", "error": f"Timed out after {timeout}s"}],
            "route": [],
        }
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if result["success"]:
        response_text = result["text"]
        model_used = result["model"]
    elif result.get("started") and result.get("text"):
        response_text = result["text"]
        model_used = result["model"] or "streaming-error"
    else:
        response_text = "All providers failed. Please try again later."
        model_used = "none"

    return {
        "response": response_text,
        "model_used": model_used,
        "errors": result.get("errors", []),
        "route": result.get("route", []),
    }

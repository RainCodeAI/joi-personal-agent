import logging

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.diagnostics import router as diagnostics_router
from app.api.models import (
    ChatRequest,
    ChatResponse,
    MemoryItem,
    MemorySearchRequest,
    MemorySearchResponse,
    OAuthCallbackResponse,
    OAuthStartResponse,
)
from app.api.state import agent, memory_store
from app.api.v2 import router as v2_router
from app.config import settings
from app.db import engine as db_engine

logger = logging.getLogger(__name__)

app = FastAPI(title="Joi API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _check_ollama() -> dict:
    try:
        with httpx.Client(timeout=1.5) as client:
            r = client.get(f"{settings.ollama_host}/api/version")
            r.raise_for_status()
            return {"available": True}
    except Exception as exc:
        return {"available": False, "error": str(exc)}


@app.get("/health")
async def health():
    db_ok = db_engine is not None
    ollama = _check_ollama()
    openai_configured = bool(settings.openai_api_key)

    providers = {
        "ollama": ollama,
        "openai": {"available": openai_configured, "note": "key_present" if openai_configured else "key_missing"},
    }

    any_provider_up = ollama["available"] or openai_configured
    status = "ok" if (db_ok and any_provider_up) else "degraded"

    if status == "degraded":
        logger.warning("Health check degraded: db_ok=%s any_provider_up=%s", db_ok, any_provider_up)

    return {
        "status": status,
        "database": {"available": db_ok},
        "providers": providers,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    history = memory_store.get_chat_history(request.session_id)
    return agent.reply(history, request.text, request.session_id)


@app.post("/memory/search", response_model=MemorySearchResponse)
async def memory_search_endpoint(request: MemorySearchRequest):
    results = memory_store.search_embeddings(request.query, k=request.limit)
    return MemorySearchResponse(
        items=[
            MemoryItem(
                text=item["text"],
                metadata=item.get("metadata", {}),
                distance=item.get("distance", 0.0),
            )
            for item in results
        ]
    )


@app.get("/oauth/start", response_model=OAuthStartResponse)
async def oauth_start():
    return OAuthStartResponse(
        auth_url="http://localhost:8000/oauth/callback",
        state="stub_state",
    )


@app.get("/oauth/callback", response_model=OAuthCallbackResponse)
async def oauth_callback(code: str, state: str = ""):
    return OAuthCallbackResponse(code=code, state=state)


app.include_router(diagnostics_router)
app.include_router(v2_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

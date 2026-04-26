import asyncio
import logging
import sys
from contextlib import asynccontextmanager

# aiomqtt requires SelectorEventLoop on Windows (ProactorEventLoop lacks add_reader/add_writer).
# set_event_loop_policy is deprecated in 3.14 and slated for removal in 3.16.
# When uvicorn gains loop_factory support, replace this with that mechanism.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # noqa: PYD014

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import diagnostics as diagnostics_api
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
from app.api.state import agent, memory_store, mqtt_bridge, initiative_scheduler
from app.api.v2 import router as v2_router
from app.db import engine as db_engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mqtt_bridge.start()
    await initiative_scheduler.start()
    yield
    await initiative_scheduler.stop()
    await mqtt_bridge.stop()


app = FastAPI(title="Joi API", version="1.0.0", lifespan=lifespan)

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
@app.get("/health")
async def health():
    runtime = diagnostics_api.build_runtime_diagnostics()
    db_ok = db_engine is not None
    media_tts = runtime["media"].get("tts", {})
    media_stt = runtime["media"].get("stt", {})

    if runtime["status"] == "degraded":
        logger.warning(
            "Health check degraded: readiness=%s",
            {key: value["state"] for key, value in runtime["readiness"].items()},
        )

    return {
        "status": runtime["status"],
        "database": {"available": db_ok},
        "providers": runtime["providers"],
        "storage": {
            "available": runtime["storage"].get("available", False),
            "database_mode": runtime["storage"].get("database_mode"),
            "vector_mode": runtime["storage"].get("vector_mode"),
        },
        "media": {
            "available": runtime["readiness"]["media"]["state"] == "ready",
            "tts_available": any(
                bool(media_tts.get(key))
                for key in ("openai", "local_engine", "elevenlabs_sdk")
            ),
            "stt_available": any(
                bool(media_stt.get(key))
                for key in ("google_local_stack", "whisper_local")
            ),
        },
        "realtime": {
            "available": runtime["realtime"].get("available", False),
            "transport": runtime["realtime"].get("transport"),
            "subscriber_count": runtime["realtime"].get("subscriber_count", 0),
        },
        "hardware_bridge": runtime["hardware_bridge"],
        "readiness": runtime["readiness"],
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

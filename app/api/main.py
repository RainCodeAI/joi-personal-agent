import asyncio
import logging
import secrets
import sys
from contextlib import asynccontextmanager

# aiomqtt requires SelectorEventLoop on Windows (ProactorEventLoop lacks add_reader/add_writer).
# set_event_loop_policy is deprecated in 3.14 and slated for removal in 3.16.
# When uvicorn gains loop_factory support, replace this with that mechanism.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # noqa: PYD014

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google_auth_oauthlib.flow import Flow

from app.api import diagnostics as diagnostics_api
from app.api.diagnostics import router as diagnostics_router
from app.api.security import require_local_api_token
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
from app.config import settings
from app.db import engine as db_engine
from app.tools import calendar_gcal, email_gmail
from app.vault import delete_secret, get_secret, store_secret

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mqtt_bridge.start()
    await initiative_scheduler.start()
    yield
    await initiative_scheduler.stop()
    await mqtt_bridge.stop()


app = FastAPI(title="Joi API", version="1.0.0", lifespan=lifespan)
app.middleware("http")(require_local_api_token)

def _cors_origins() -> list[str]:
    return [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


GOOGLE_SCOPES = sorted(set(email_gmail.SCOPES + calendar_gcal.SCOPES))
OAUTH_STATE_SECRET = "google_oauth_state"


def _google_flow() -> Flow:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth client is not configured")
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uris": [settings.oauth_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=GOOGLE_SCOPES,
    )
    flow.redirect_uri = settings.oauth_redirect_uri
    return flow
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
    state = secrets.token_urlsafe(32)
    try:
        store_secret(OAUTH_STATE_SECRET, state)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    flow = _google_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return OAuthStartResponse(
        auth_url=auth_url,
        state=state,
    )


@app.get("/oauth/callback", response_model=OAuthCallbackResponse)
async def oauth_callback(code: str, state: str = ""):
    try:
        expected_state = get_secret(OAUTH_STATE_SECRET)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="OAuth flow was not started or has expired") from exc
    if not state or not secrets.compare_digest(state, expected_state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    flow = _google_flow()
    try:
        flow.fetch_token(code=code)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"OAuth token exchange failed: {exc}") from exc
    finally:
        delete_secret(OAUTH_STATE_SECRET)

    token_json = flow.credentials.to_json()
    store_secret("gmail_token", token_json)
    store_secret("calendar_token", token_json)
    return OAuthCallbackResponse(
        code=code,
        state=state,
        success=True,
        message="Google account linked for Gmail and Calendar",
    )


app.include_router(diagnostics_router)
app.include_router(v2_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)

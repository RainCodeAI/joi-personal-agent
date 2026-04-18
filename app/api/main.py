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

@app.get("/health")
async def health():
    return {"status": "ok"}


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

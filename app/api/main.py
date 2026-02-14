from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.models import (
    ChatRequest, ChatResponse, MemorySearchRequest, MemorySearchResponse, 
    OAuthStartResponse, OAuthCallbackResponse
)
from app.api.diagnostics import router as diagnostics_router  # Your new router
from app.orchestrator.agent import Agent
from app.memory.store import MemoryStore
import os

app = FastAPI(title="Joi API", version="1.0.0")

# CORS for Streamlit (localhost:8501)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global stores (init once)
memory_store = MemoryStore()
agent = Agent()

# Example Routes (stubs – expand as needed)
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    response = agent.reply([], request.text, request.session_id)  # Stub – add history later
    return ChatResponse(text=response)

@app.post("/memory/search", response_model=MemorySearchResponse)
async def memory_search_endpoint(request: MemorySearchRequest):
    results = memory_store.search_embeddings(request.query, k=request.limit)
    return MemorySearchResponse(items=results)

@app.get("/oauth/start", response_model=OAuthStartResponse)
async def oauth_start():
    # Stub for Google OAuth – implement auth_url logic
    return OAuthStartResponse(auth_url="http://localhost:8000/oauth/callback", state="stub_state")

@app.get("/oauth/callback", response_model=OAuthCallbackResponse)
async def oauth_callback(code: str, state: str = ""):
    # Stub for callback – handle token exchange
    return OAuthCallbackResponse(code=code, state=state)

# Mount Diagnostics Router
app.include_router(diagnostics_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
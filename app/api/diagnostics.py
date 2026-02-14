from fastapi import APIRouter
from app.memory.store import MemoryStore

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])

memory_store = MemoryStore()  # Init once for health checks

@router.get("/chroma/health")
def chroma_health():
    coll = memory_store.collection
    meta = coll.metadata or {}
    return {
        "name": coll.name,
        "count": coll.count(),
        "embed_dim_meta": meta.get("embed_dim"),
        "embedder_id_meta": meta.get("embedder_id", "Not set")
    }
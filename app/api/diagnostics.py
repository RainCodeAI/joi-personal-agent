from fastapi import APIRouter
from app.memory.store import MemoryStore

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

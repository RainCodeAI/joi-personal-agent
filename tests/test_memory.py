import pytest
from app.memory.store import MemoryStore

def test_add_memory():
    store = MemoryStore()
    store.add_memory("test", "hello world", ["tag"])
    # Check if added, but since Chroma, hard to test without query
    results = store.search_embeddings("hello")
    assert len(results) > 0

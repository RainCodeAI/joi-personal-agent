import json

from app.memory.consolidation import MemoryConsolidator
from app.memory.store import MemoryStore


def _seed_episodic(store, n, prefix="consolidation-test"):
    for i in range(n):
        store.add_memory("user_input", f"{prefix} moment {i}: working on the launch", ["chat", "default"])


def test_consolidate_creates_semantic_memories(tmp_path):
    store = MemoryStore()
    _seed_episodic(store, 6)

    summaries = [
        "Avery has been heads-down on a launch and feeling the pressure.",
        "They keep returning to unfinished work late at night.",
    ]

    def fake_route(prompt, context):
        assert context.get("task") == "memory_consolidation"
        return {"response": json.dumps(summaries), "model_used": "test-model", "route": [], "errors": []}

    consolidator = MemoryConsolidator(
        store, route_fn=fake_route, state_path=tmp_path / "consolidation_state.json"
    )
    result = consolidator.consolidate(force=True)

    assert result["status"] == "ok"
    assert result["consolidated"] == len(summaries)
    assert result["summaries"] == summaries

    # Stored as semantic "consolidation" memories.
    stored = store.get_recent_memories(limit=10, mem_type="consolidation")
    stored_texts = {m.text for m in stored}
    assert set(summaries).issubset(stored_texts)
    assert all(m.memory_type == "semantic" for m in stored)

    # State advanced so a second run won't reprocess the same window.
    assert consolidator.last_run_at() is not None


def test_consolidate_skips_when_insufficient(tmp_path):
    store = MemoryStore()

    called = {"n": 0}

    def fake_route(prompt, context):
        called["n"] += 1
        return {"response": "[]", "model_used": "test-model"}

    # A far-future state window means "since last run" captures no new memories.
    from datetime import datetime, timedelta

    state_path = tmp_path / "consolidation_state.json"
    state_path.write_text(json.dumps({"last_consolidated_at": datetime.utcnow().isoformat()}))

    consolidator = MemoryConsolidator(store, route_fn=fake_route, state_path=state_path)
    result = consolidator.consolidate(force=False)

    assert result["status"] == "skipped"
    assert called["n"] == 0  # never called the LLM


def test_parse_summaries_json_and_fallback():
    json_text = 'Here you go: ["first note", "second note"] thanks'
    assert MemoryConsolidator._parse_summaries(json_text) == ["first note", "second note"]

    bullet_text = "1. First durable note here\n- Second durable note here\n\n* Third one too"
    parsed = MemoryConsolidator._parse_summaries(bullet_text)
    assert parsed == [
        "First durable note here",
        "Second durable note here",
        "Third one too",
    ]

    assert MemoryConsolidator._parse_summaries("") == []


def test_consolidate_no_output_is_error(tmp_path):
    store = MemoryStore()
    _seed_episodic(store, 6, prefix="err-test")

    def fake_route(prompt, context):
        return {"response": "", "model_used": "none"}

    consolidator = MemoryConsolidator(
        store, route_fn=fake_route, state_path=tmp_path / "state.json"
    )
    result = consolidator.consolidate(force=True)
    assert result["status"] == "error"
    # Window not advanced on failure, so it retries next run.
    assert consolidator.last_run_at() is None

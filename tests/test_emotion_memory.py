import json

from app.memory.store import (
    MemoryStore,
    SALIENCE_THRESHOLD,
    _emotion_metadata,
    _emotional_salience,
)
from app.orchestrator.agents.memory_retriever import MemoryRetrieverAgent


def test_salience_reflects_charge():
    # Neutral, mid mood → low salience.
    assert _emotional_salience("neutral", 5.0) < 0.3
    assert _emotional_salience(None, None) < 0.3
    # Negative on a low-mood day → high (crosses the retrieval threshold).
    assert _emotional_salience("negative", 2.0) >= SALIENCE_THRESHOLD
    # Positive on a great day → high too.
    assert _emotional_salience("positive", 9.0) >= SALIENCE_THRESHOLD
    # Charged sentiment alone (mid mood) is moderately salient but below threshold.
    mid = _emotional_salience("negative", 5.0)
    assert 0.4 < mid < SALIENCE_THRESHOLD


def test_emotion_metadata_is_chroma_safe():
    meta = _emotion_metadata("negative", 3.0)
    assert meta["sentiment"] == "negative"
    assert meta["mood"] == 3.0
    assert isinstance(meta["salience"], float)
    # No sentiment/mood → still yields a (low) salience only.
    assert set(_emotion_metadata(None, None)) == {"salience"}


def test_add_memory_folds_emotion_into_tags():
    store = MemoryStore()
    text = "emotion-tag-test: I feel completely awful today"
    store.add_memory("user_input", text, ["chat", "s1"], sentiment="negative", mood=2.0)

    match = next(
        m for m in store.get_recent_memories(limit=20, mem_type="user_input") if m.text == text
    )
    tags = json.loads(match.tags)
    assert "emotion:negative" in tags

    # Neutral sentiment must not add an emotion tag.
    neutral_text = "emotion-tag-test: I need to buy printer paper"
    store.add_memory("user_input", neutral_text, ["chat", "s1"], sentiment="neutral", mood=5.0)
    neutral = next(
        m for m in store.get_recent_memories(limit=20, mem_type="user_input") if m.text == neutral_text
    )
    assert not any(t.startswith("emotion:") for t in json.loads(neutral.tags))


def test_emotion_note_only_annotates_salient():
    note = MemoryRetrieverAgent._emotion_note
    assert note({"salience": 0.9, "sentiment": "negative"}) == " (they seemed low then)"
    assert note({"salience": 0.8, "sentiment": "positive"}) == " (they were upbeat then)"
    # Low salience or missing metadata → no annotation.
    assert note({"salience": 0.3, "sentiment": "negative"}) == ""
    assert note({"sentiment": "negative"}) == ""
    assert note(None) == ""

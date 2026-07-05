"""Memory consolidation — Joi's nightly "sleep".

Gathers the recent window of episodic memories (chat inputs, perceptions,
events) plus mood context and asks the LLM to synthesize a few durable,
connective semantic memories — the piece that turns a stream of moments into
"what's been going on with the user lately." Results are stored as
``consolidation`` (semantic) memories, which retrieval surfaces ahead of raw
episodic fragments.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.config import settings
from app.memory.store import MemoryStore
from app.persistence import read_json, runtime_data_dir, write_json_atomic

logger = logging.getLogger(__name__)

# Episodic sources we synthesize FROM. We never consolidate prior syntheses.
_SOURCE_EXCLUDE_TYPES = ["consolidation", "summary", "brief", "morning_brief"]
_MAX_SOURCE_ITEMS = 120
_MAX_SUMMARIES = 5

RouteFn = Callable[[str, Dict[str, Any]], Dict[str, Any]]


class MemoryConsolidator:
    """Synthesizes durable semantic memories from a window of episodic ones."""

    def __init__(
        self,
        memory_store: MemoryStore,
        *,
        route_fn: Optional[RouteFn] = None,
        state_path: Optional[Path] = None,
    ) -> None:
        self.memory_store = memory_store
        self._route_fn = route_fn
        self.state_path = state_path or (runtime_data_dir() / "consolidation_state.json")

    # ── public API ────────────────────────────────────────────────────────

    def consolidate(self, user_id: str = "default", *, force: bool = False) -> Dict[str, Any]:
        """Run one consolidation pass. Returns a stats dict."""
        now = datetime.utcnow()
        window_start = self._window_start(now)

        sources = self.memory_store.get_memories_since(
            window_start,
            memory_type="episodic",
            exclude_types=_SOURCE_EXCLUDE_TYPES,
            limit=_MAX_SOURCE_ITEMS,
        )

        min_items = max(1, settings.memory_consolidation_min_items)
        if len(sources) < min_items and not force:
            # Not enough new material yet; leave the window open for next time.
            return self._result("skipped", now, source_count=len(sources), reason="not enough new memories")
        if not sources:
            self._save_state(now)  # nothing to do, but close the window
            return self._result("skipped", now, source_count=0, reason="no source memories")

        mood_context = self._mood_context(user_id)
        prompt = self._build_prompt(sources, mood_context)
        routed = self._route(prompt)
        response_text = str(routed.get("response") or "")
        model_used = str(routed.get("model_used") or "none")

        if model_used == "none" or not response_text.strip():
            # Don't advance the window — retry with the same material next run.
            logger.warning("Consolidation LLM produced no output (model=%s)", model_used)
            return self._result(
                "error", now, source_count=len(sources), reason="LLM produced no output", model=model_used
            )

        summaries = self._parse_summaries(response_text)
        if not summaries:
            return self._result(
                "error", now, source_count=len(sources), reason="no summaries parsed", model=model_used
            )

        date_tag = f"date:{now.date().isoformat()}"
        stored = 0
        for summary in summaries:
            try:
                self.memory_store.add_memory("consolidation", summary, ["consolidation", date_tag, user_id])
                stored += 1
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to store consolidation memory: %s", exc)

        self._save_state(now)
        logger.info("Consolidation stored %d summaries from %d memories", stored, len(sources))
        return self._result(
            "ok",
            now,
            source_count=len(sources),
            consolidated=stored,
            summaries=summaries,
            model=model_used,
        )

    def last_run_at(self) -> Optional[str]:
        state = read_json(self.state_path, {})
        value = state.get("last_consolidated_at") if isinstance(state, dict) else None
        return str(value) if value else None

    # ── internals ─────────────────────────────────────────────────────────

    def _route(self, prompt: str) -> Dict[str, Any]:
        route_fn = self._route_fn
        if route_fn is None:
            from services.ai_router import route_request

            route_fn = route_request
        return route_fn(prompt, {"task": "memory_consolidation"})

    def _window_start(self, now: datetime) -> datetime:
        max_lookback = timedelta(hours=max(1, settings.memory_consolidation_max_lookback_hours))
        last = self._last_consolidated_at()
        if last is None:
            return now - timedelta(hours=24)
        return max(last, now - max_lookback)

    def _last_consolidated_at(self) -> Optional[datetime]:
        raw = self.last_run_at()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    def _mood_context(self, user_id: str) -> str:
        try:
            trend = self.memory_store.mood_trend_analysis(user_id)
        except Exception:
            return ""
        if not trend or not trend.get("moods"):
            return ""
        return (
            f"Recent mood averages {trend.get('avg_mood', 0):.1f}/10 and is trending "
            f"{trend.get('direction', 'flat')}."
        )

    @staticmethod
    def _build_prompt(sources: List[Any], mood_context: str) -> str:
        # Oldest-first so the model reads the period as it unfolded.
        lines = [f"- {getattr(mem, 'text', '')}".strip() for mem in reversed(sources)]
        material = "\n".join(line for line in lines if line and line != "-")
        mood_line = f"\nMood context: {mood_context}\n" if mood_context else "\n"
        return (
            "You are Joi, quietly reflecting at the end of the day on what has been "
            "happening with the person you look after. Below are recent moments — things "
            "they said, did, or that you noticed.\n\n"
            f"Recent moments:\n{material}\n{mood_line}\n"
            "Write 3-5 short, durable notes that capture the meaningful threads: ongoing "
            "projects or worries, emotional patterns, relationships, and anything unfinished "
            "worth remembering. Connect events to feelings where it's honest to do so. Be "
            "specific and grounded — no filler, no advice, no invented details. Write each "
            "note as one plain sentence about the person.\n\n"
            'Return ONLY a JSON array of strings, e.g. ["...", "..."].'
        )

    @staticmethod
    def _parse_summaries(text: str) -> List[str]:
        text = text.strip()
        # Prefer a JSON array anywhere in the response.
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
                if isinstance(parsed, list):
                    items = [str(item).strip() for item in parsed if str(item).strip()]
                    if items:
                        return items[:_MAX_SUMMARIES]
            except (TypeError, ValueError):
                pass
        # Fallback: line-based, stripping bullets/numbering.
        items = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            line = re.sub(r"^[\-\*\d\.\)\s]+", "", line).strip().strip('"')
            if len(line) > 8:
                items.append(line)
        return items[:_MAX_SUMMARIES]

    def _save_state(self, now: datetime) -> None:
        state = read_json(self.state_path, {})
        if not isinstance(state, dict):
            state = {}
        state["last_consolidated_at"] = now.isoformat()
        try:
            write_json_atomic(self.state_path, state)
        except OSError as exc:  # pragma: no cover - defensive
            logger.warning("Failed to persist consolidation state: %s", exc)

    @staticmethod
    def _result(status: str, now: datetime, **extra: Any) -> Dict[str, Any]:
        return {"status": status, "ran_at": now.isoformat(), **extra}

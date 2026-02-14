"""MemoryRetrieverAgent — RAG search, graph traversal, context assembly.

Extracts profile retrieval, sentiment analysis, mood tracking,
knowledge-graph operations, and memory search from Agent.reply().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.memory.store import MemoryStore
    from app.api.models import ChatMessage


@dataclass
class ContextBundle:
    """Everything the MemoryRetrieverAgent gathers for the Orchestrator."""

    profile_info: str = ""
    sentiment: str = "neutral"
    avg_mood: float = 5.0
    memory_context: str = ""
    relevant_memories: List[Dict[str, Any]] = field(default_factory=list)


class MemoryRetrieverAgent:
    """Gathers contextual information from memory, profile, and mood data."""

    # ── public API ────────────────────────────────────────────────────────

    def retrieve_context(
        self,
        session_id: str,
        user_msg: str,
        chat_history: List[ChatMessage],
        memory_store: MemoryStore,
    ) -> ContextBundle:
        """Build a ContextBundle by querying the memory store."""
        from datetime import datetime
        from app.config import JOI_CORE_PROMPT

        bundle = ContextBundle()

        # 1. Sentiment analysis
        bundle.sentiment = self._analyze_sentiment(user_msg)

        # 2. Recent mood average
        # This updates bundle.profile_info with mood warnings, but we'll reset profile_info soon.
        # We should calculate avg_mood purely here.
        bundle.avg_mood = self._compute_avg_mood_score(session_id, memory_store)

        # 3. User Profile & Idle Time
        profile = memory_store.get_user_profile(session_id)
        profile_summary = "Unknown"
        relationship_level = "Acquaintance"
        if profile:
            parts = [f"Name: {profile.name}", f"Hobbies: {profile.hobbies}"]
            if profile.relationships:
                parts.append(f"Relationships: {profile.relationships}")
            if profile.personality:
                parts.append(f"Persona: {profile.personality}")
            profile_summary = ", ".join(parts)
            # Rough proxy for relationship level based on contact/milestones (future improvement)
            relationship_level = "Access Level 5 (Companion)"

        # Calculate idle time
        idle_hours = 0.0
        try:
            history = memory_store.get_chat_history(session_id)
            if history and len(history) >= 2:
                # history[-1] is *this* user message (just added), history[-2] is previous.
                last_ts = history[-2].timestamp
                if last_ts:
                    diff = datetime.utcnow() - last_ts
                    idle_hours = round(diff.total_seconds() / 3600, 1)
        except Exception:
            pass

        # 4. Assemble Core Prompt
        # Inject variables
        core_prompt = JOI_CORE_PROMPT.format(
            profile_summary=profile_summary,
            avg_mood=f"{bundle.avg_mood:.1f}",
            relationship_level=relationship_level,
            idle_hours=idle_hours
        )
        bundle.profile_info = core_prompt

        # 5. Append dynamic situational context
        if bundle.sentiment == "negative":
            bundle.profile_info += "\n[System Note]: User input is negative. Be empathetic."
        elif bundle.sentiment == "positive":
            bundle.profile_info += "\n[System Note]: User input is positive. Match enthusiasm."
        
        # Add mood warning if significant
        if bundle.avg_mood < 4.0:
            bundle.profile_info += "\n[System Note]: User has been consistently low mood. Prioritize comfort."

        # 6. News / weather on request
        bundle.profile_info += self._maybe_fetch_news_weather(user_msg)

        # 7. Knowledge graph on trigger
        if "graph" in user_msg.lower() or "connections" in user_msg.lower():
            memory_store.populate_knowledge_graph(session_id)
            bundle.profile_info += "\n[System Note]: Knowledge graph updated."

        # 8. Graph RAG search
        bundle.relevant_memories = memory_store.graph_rag_search(user_msg, k=3)
        if bundle.relevant_memories:
            bundle.memory_context = (
                "Relevant past context:\n"
                + "\n".join(mem["text"] for mem in bundle.relevant_memories)
            )

        return bundle

    # ── private helpers ───────────────────────────────────────────────────

    @staticmethod
    def _analyze_sentiment(user_msg: str) -> str:
        lower = user_msg.lower()
        negative_words = [
            "stressed", "anxious", "worried", "sad", "angry", "frustrated",
        ]
        positive_words = ["happy", "excited", "great", "awesome", "love"]

        if any(w in lower for w in negative_words):
            return "negative"
        if any(w in lower for w in positive_words):
            return "positive"
        return "neutral"

    @staticmethod
    def _compute_avg_mood_score(
        session_id: str,
        memory_store: MemoryStore,
    ) -> float:
        recent_moods = memory_store.get_recent_moods(session_id, 3)
        avg_mood = 5.0
        if recent_moods:
            avg_mood = sum(m.mood for m in recent_moods) / len(recent_moods)
        return avg_mood

    @staticmethod
    def _maybe_fetch_news_weather(user_msg: str) -> str:
        if "news" not in user_msg.lower() and "weather" not in user_msg.lower():
            return ""
        try:
            from app.utils.apis import get_news_summary, get_weather

            news = get_news_summary()
            weather = get_weather()
            return f" {news} {weather}"
        except Exception:
            return ""

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

        bundle = ContextBundle()

        # 1. User profile + personality formatting
        bundle.profile_info = self._build_profile_info(session_id, memory_store)

        # 2. Sentiment analysis
        bundle.sentiment = self._analyze_sentiment(user_msg)
        if bundle.sentiment == "negative":
            bundle.profile_info += (
                " User seems stressed or negative—respond empathetically, offer support."
            )
        elif bundle.sentiment == "positive":
            bundle.profile_info += " User seems happy—share in the positivity."

        # 3. Recent mood average
        bundle.avg_mood = self._compute_avg_mood(session_id, memory_store, bundle)

        # 4. News / weather on request
        bundle.profile_info += self._maybe_fetch_news_weather(user_msg)

        # 5. Knowledge graph on trigger
        if "graph" in user_msg.lower() or "connections" in user_msg.lower():
            memory_store.populate_knowledge_graph(session_id)
            bundle.profile_info += (
                " Knowledge graph updated with your goals, habits, and decisions."
            )

        # 6. Graph RAG search for relevant memories
        bundle.relevant_memories = memory_store.graph_rag_search(user_msg, k=3)
        if bundle.relevant_memories:
            bundle.memory_context = (
                "Relevant past context:\n"
                + "\n".join(mem["text"] for mem in bundle.relevant_memories)
            )

        return bundle

    # ── private helpers ───────────────────────────────────────────────────

    @staticmethod
    def _build_profile_info(session_id: str, memory_store: MemoryStore) -> str:
        profile = memory_store.get_user_profile(session_id)
        if not profile:
            return ""

        parts: List[str] = [
            f"User Profile: Name: {profile.name}, "
            f"Hobbies: {profile.hobbies}, "
            f"Relationships: {profile.relationships}."
        ]

        if profile.therapeutic_mode:
            parts.append(
                "Therapeutic Mode Enabled: Use CBT-inspired prompts like "
                "'What's one positive thing today?' or 'What triggered this feeling?'."
            )

        personality_map = {
            "Witty": (
                "Personality: Witty - Be humorous, use puns, light sarcasm. "
                "Start with 'As your witty AI friend...'."
            ),
            "Supportive": (
                "Personality: Supportive - Be encouraging, empathetic, "
                "positive reinforcement."
            ),
            "Sarcastic": (
                "Personality: Sarcastic - Use irony, teasing humor, "
                "but keep it friendly."
            ),
            "Professional": (
                "Personality: Professional - Formal, concise, business-like tone."
            ),
        }
        if profile.personality and profile.personality in personality_map:
            parts.append(personality_map[profile.personality])

        if hasattr(profile, "humor_level"):
            humor_desc = (
                "low"
                if profile.humor_level < 4
                else "medium"
                if profile.humor_level < 7
                else "high"
            )
            parts.append(
                f"Humor level: {humor_desc} (scale 1-10: {profile.humor_level}). "
                "Adjust wit accordingly."
            )

        return " ".join(parts)

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
    def _compute_avg_mood(
        session_id: str,
        memory_store: MemoryStore,
        bundle: ContextBundle,
    ) -> float:
        recent_moods = memory_store.get_recent_moods(session_id, 3)
        avg_mood = 5.0
        if recent_moods:
            avg_mood = sum(m.mood for m in recent_moods) / len(recent_moods)
            if avg_mood < 5:
                bundle.profile_info += (
                    f" User's recent mood average is low "
                    f"({avg_mood:.1f}/10)—be extra supportive."
                )
            elif avg_mood > 7:
                bundle.profile_info += (
                    f" User's recent mood average is high "
                    f"({avg_mood:.1f}/10)—celebrate with them."
                )
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

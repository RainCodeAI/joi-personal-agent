"""PlannerAgent — Task breakdown, scheduling, goal tracking, health & CBT logic.

Extracts proactive-assistance, habit, CBT, flow-state, and causal-insight
logic that was previously inlined in Agent.reply().
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from app.memory.store import MemoryStore
    from app.api.models import ChatMessage


class PlannerAgent:
    """Assembles proactive-planning context that gets merged into the LLM prompt."""

    # ── public API ────────────────────────────────────────────────────────

    def enrich(
        self,
        session_id: str,
        user_msg: str,
        chat_history: List[ChatMessage],
        memory_store: MemoryStore,
        avg_mood: float = 5.0,
        sentiment: str = "neutral",
    ) -> Dict[str, str]:
        """Return keyed context strings the Orchestrator merges into the prompt.

        Keys produced (all optional – empty string when nothing to add):
        - habit_reminders
        - health_nudge
        - causal_insights
        - proactive_checkin
        - cbt_suggestion
        - flow_nudge
        - mental_checklist
        - decision_helper
        """
        ctx: Dict[str, str] = {}

        ctx["habit_reminders"] = self._habit_reminders(session_id, memory_store)
        ctx["health_nudge"] = self._health_nudge(chat_history)
        ctx["causal_insights"] = self._causal_insights(
            session_id, user_msg, chat_history, memory_store
        )
        ctx["proactive_checkin"] = self._proactive_checkin(
            session_id, chat_history, memory_store
        )
        ctx["cbt_suggestion"] = self._cbt_suggestion(
            session_id, user_msg, sentiment, memory_store
        )
        ctx["flow_nudge"] = self._flow_nudge(session_id, memory_store)
        ctx["mental_checklist"] = self._mental_checklist(user_msg)
        ctx["decision_helper"] = self._decision_helper(
            session_id, user_msg, memory_store
        )

        return ctx

    # ── private helpers ───────────────────────────────────────────────────

    @staticmethod
    def _habit_reminders(session_id: str, memory_store: MemoryStore) -> str:
        habits = memory_store.get_habits(session_id)
        parts: List[str] = []
        now = datetime.utcnow()
        for h in habits:
            if not h.last_done or (now - h.last_done).days > 1:
                parts.append(
                    f"Reminder: You haven't done '{h.name}' recently. Streak: {h.streak} days."
                )
        return " ".join(parts)

    @staticmethod
    def _health_nudge(chat_history: List[ChatMessage]) -> str:
        if len(chat_history) > 10:
            return "You've been chatting a while—take a break, hydrate, or stretch!"
        return ""

    @staticmethod
    def _causal_insights(
        session_id: str,
        user_msg: str,
        chat_history: List[ChatMessage],
        memory_store: MemoryStore,
    ) -> str:
        trigger = (
            "why" in user_msg.lower()
            or "correlation" in user_msg.lower()
            or len(chat_history) % 5 == 0
        )
        if not trigger:
            return ""

        causal = memory_store.causal_analysis_mood_habit(session_id)
        if not causal:
            return ""

        insights: List[str] = []
        for habit, data in causal.items():
            if data["avg_after_done"] > data["recent_avg"] + 0.5:
                insights.append(
                    f"Doing '{habit}' boosts mood "
                    f"(avg {data['avg_after_done']:.1f} vs recent {data['recent_avg']:.1f})"
                )
            elif data["avg_after_done"] < data["recent_avg"] - 0.5:
                insights.append(f"Missing '{habit}' correlates with lower mood")

        if insights:
            return "Insights: " + "; ".join(insights[:2])
        return ""

    @staticmethod
    def _proactive_checkin(
        session_id: str,
        chat_history: List[ChatMessage],
        memory_store: MemoryStore,
    ) -> str:
        if len(chat_history) % 10 != 0:
            return ""

        trend = memory_store.mood_trend_analysis(session_id)
        if trend["trend"] < -0.5:
            return (
                f"Mood trend negative (avg {trend['avg_mood']:.1f}, "
                f"trend {trend['trend']:.1f}). Initiate gentle check-in."
            )
        if trend["avg_mood"] < 4:
            return f"Mood low (avg {trend['avg_mood']:.1f}). Offer support."
        return ""

    @staticmethod
    def _cbt_suggestion(
        session_id: str,
        user_msg: str,
        sentiment: str,
        memory_store: MemoryStore,
    ) -> str:
        if sentiment != "negative" and "cbt" not in user_msg.lower():
            return ""

        recent_mood = memory_store.get_recent_moods(session_id, 1)
        mood_level = recent_mood[0].mood if recent_mood else 5
        exercise = memory_store.suggest_cbt_exercise(session_id, mood_level)
        if exercise:
            return f"Suggest CBT exercise: '{exercise.name}' - {exercise.description}."
        return ""

    @staticmethod
    def _flow_nudge(session_id: str, memory_store: MemoryStore) -> str:
        recent_activities = memory_store.get_recent_activities(session_id, 1)
        if recent_activities:
            act = recent_activities[0]
            if act.duration > 4500:  # 75 mins
                return (
                    f"You've been in {act.app} for {act.duration // 60} mins"
                    "—time for a break? Hydrate or stretch."
                )
        return ""

    @staticmethod
    def _mental_checklist(user_msg: str) -> str:
        if any(
            word in user_msg.lower()
            for word in ["start", "begin", "work", "task"]
        ):
            return "Before starting, log your current mood for better flow tracking."
        return ""

    @staticmethod
    def _decision_helper(
        session_id: str, user_msg: str, memory_store: MemoryStore
    ) -> str:
        if "should i" not in user_msg.lower() and "decision" not in user_msg.lower():
            return ""

        parts = [
            "For decisions, consider pros/cons. I can help list them based on your history."
        ]
        decisions = memory_store.get_decisions(session_id)
        if decisions:
            outcomes = [d.outcome for d in decisions if d.outcome]
            parts.append(f"From past decisions, you often prioritize: {outcomes}")
        return " ".join(parts)

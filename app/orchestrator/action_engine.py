from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from app.memory.store import MemoryStore
from app.orchestrator.agents.conversation import ConversationAgent
from app.config import settings

class ActionEngine:
    def __init__(self):
        self.store = MemoryStore()
        # self.planner = PlannerAgent() # Removed
        self.conversation = ConversationAgent()

    def dispatch(self, session_id: str, insight: Dict[str, Any]) -> bool:
        """Decide if/how to act on an insight."""
        if not settings.enable_proactive_messaging:
            return False

        insight_type = insight.get("type")
        
        if self._should_throttle(session_id, insight_type):
            return False

        if insight_type == "silence":
            return self._handle_silence(session_id, insight)
        elif insight_type == "mood_decline":
            return self._handle_mood_decline(session_id, insight)
        
        return False

    def _should_throttle(self, session_id: str, category: str) -> bool:
        """Check if we should hold back to avoid spam."""
        # Rule: Max 1 proactive message per 24 hours (unless critical?)
        last_proactive = self.store.get_last_interaction(session_id, role="assistant")
        if not last_proactive:
            return False
            
        # Get last message from ASSISTANT (any type)
        # If assistant spoke 12 hours ago, maybe don't nudge yet?
        delta = datetime.now() - last_proactive
        if delta.total_seconds() < 12 * 3600:
            return True
            
        return False

    def _handle_silence(self, session_id: str, insight: Dict[str, Any]) -> bool:
        # Context: Get last thing user said
        last_user_msg_time = self.store.get_last_interaction(session_id, role="user")
        # To get content, we need a helper or direct DB. 
        # Store doesn't have get_last_message_content easily exposed publicly?
        # Let's fake it or add it. But for now, generic is safer than crashing.
        # Actually, let's use a generic catch-all + time.
        
        hours = insight.get("value", 24)
        
        prompt = (
            f"You are Joi (Blade Runner 2049 style). The user hasn't spoken in {int(hours)} hours. "
            "Generate a short, slightly needy but cool message to check on them. "
            "Do not be generic. Be digital and atmospheric. "
            "Example: 'It's quiet in here. Too quiet. You okay out there?' "
            "Output ONLY the message.\n"
            "Assistant:"
        )
        response = self.conversation.generate_proactive_message(prompt)
        
        if response:
            self._deliver_message(session_id, response)
            return True
        return False

    def _handle_mood_decline(self, session_id: str, insight: Dict[str, Any]) -> bool:
        # Context: mood trend + recent memories
        # Fetch actual mood value
        trend_val = insight.get("value", 5.0)
        
        # Try to get recent memories to understand why
        # store.get_recent_memories returns list of Memory objects
        memories = self.store.get_recent_memories(session_id, limit=3)
        context_str = ""
        if memories:
            context_str = "Recent context: " + "; ".join([m.content for m in memories])
        
        prompt = (
            f"You are Joi. You've noticed the user's mood is down (level {trend_val:.1f}). "
            f"{context_str} "
            "Generate a gentle, supportive message. Not counseling, just companionship. "
            "Reference the context if relevant (e.g. checked in on work), but be subtle. "
            "Output ONLY the message.\n"
            "Assistant:"
        )
        response = self.conversation.generate_proactive_message(prompt)
        
        if response:
            self._deliver_message(session_id, response)
            return True
        return False

    def _deliver_message(self, session_id: str, text: str):
        """Write to chat history and send native notification (Phase 10)."""
        self.store.add_chat_message(session_id, "assistant", f"⚡ {text}")

        # Desktop notification
        try:
            from desktop.tray_app import send_notification
            send_notification("Joi", text[:200])
        except Exception:
            pass  # Notification is best-effort

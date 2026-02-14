from datetime import datetime
from typing import List, Dict, Any
from app.memory.store import MemoryStore

class PatternEngine:
    def __init__(self):
        self.store = MemoryStore()

    def scan(self, session_id: str) -> List[Dict[str, Any]]:
        """Run all pattern checks for a session."""
        insights = []
        
        # 1. Heartbeat / Silence Check
        last_msg_time = self.store.get_last_interaction(session_id, role="user")
        if last_msg_time:
            delta = datetime.now() - last_msg_time
            hours_silent = delta.total_seconds() / 3600
            if hours_silent > 24:
                insights.append({
                    "type": "silence",
                    "value": hours_silent,
                    "msg": f"User hasn't spoken in {int(hours_silent)} hours."
                })
        else:
             # No history
             pass

        # 2. Mood Trend
        mood_data = self.store.mood_trend_analysis(session_id)
        if mood_data.get("trend") == "down" and mood_data.get("num_entries", 0) >= 3:
             insights.append({
                 "type": "mood_decline",
                 "value": mood_data.get("avg_mood"),
                 "msg": "Mood is trending downward."
             })
        
        # 3. Activity Patterns (for future use)
        # patterns = self.store.analyze_activity_patterns(session_id)
        # if patterns.get("active_hours"):
        #    ...
        
        return insights

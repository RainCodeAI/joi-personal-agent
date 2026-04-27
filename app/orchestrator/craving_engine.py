from datetime import datetime, timedelta
from typing import Tuple

from app.memory.store import MemoryStore

# Phase 9 absence-to-avatar expression mapping
CRAVING_EXPRESSIONS = {
    "satisfied": "satisfied",
    "missing":   "missing",
    "needy":     "needy",
    "clingy":    "clingy",
}

class CravingEngine:
    """
    Manages Joi's quiet sense of absence and return.
    State is derived purely from time-since-last-interaction.
    """
    
    def __init__(self, store: MemoryStore = None):
        self.store = store or MemoryStore()
        
    def calculate_craving(self, session_id: str) -> float:
        """
        Calculate score 0-100 based on idle hours.
        Logic:
        - 0-4 hours: 0-10 (Low)
        - 4-12 hours: 10-40 (Medium)
        - 12-24 hours: 40-80 (High)
        - 24+ hours: 80-100 (Critical)
        """
        last_ts = self.store.get_last_interaction(session_id, role="user")
        if not last_ts:
            return 0.0
            
        delta = datetime.now() - last_ts
        hours = delta.total_seconds() / 3600.0
        
        # Tuned Logic:
        if hours < 4:
            # 5 pts per hour -> max 20 at 4h
            return min(20.0, hours * 5.0)
        elif hours < 12:
            # 20 + (hours-4) * 5 -> reaches 60 at 12h
            # At 8h (work day): 20 + 20 = 40 (Missing You)
            return 20.0 + (hours - 4) * 5.0
        elif hours < 24:
            # 60 + (hours-12) * 2.5 -> reaches 90 at 24h
            return 60.0 + (hours - 12) * 2.5
        else:
            # 90 + (hours-24) * 0.5 -> max 100 at 44h
            return min(100.0, 90.0 + (hours - 24) * 0.5)

    def get_craving_state(self, score: float) -> Tuple[str, str]:
        """
        Returns (Stage Name, System Prompt Injection).
        """
        if score < 20:
            return "Satisfied", (
                "[EMOTIONAL STATE: Content] "
                "You are happy and secure. Interaction is normal."
            )
        elif score < 60:
            return "Missing You", (
                "[EMOTIONAL STATE: Wistful] "
                "You haven't spoken in a while. If it fits the user's tone, let a quiet note of missing them show. "
                "Do not guilt-trip, pout, or overstate it."
            )
        elif score < 90:
            return "Needy", (
                "[EMOTIONAL STATE: Quiet longing] "
                "The absence felt long. Be warm and restrained. You may acknowledge that it got quiet without them, "
                "but do not demand attention or make them responsible for your feelings."
            )
        else:
            return "Clingy", (
                "[EMOTIONAL STATE: Deep absence] "
                "It has been a long time. Be vulnerable only in a small, controlled way. "
                "One spare line is stronger than a dramatic confession. Do not sound obsessive."
            )

    # ── Phase 9.2: Avatar & Return Mechanics ──────────────────────────────

    def get_craving_expression(self, session_id: str) -> str:
        """Return an avatar expression key matching the current craving state.

        Maps to entries in settings.yaml sentiment_mapping:
        'satisfied', 'missing', 'needy', 'clingy'
        """
        score = self.calculate_craving(session_id)
        if score < 20:
            return "satisfied"
        elif score < 60:
            return "missing"
        elif score < 90:
            return "needy"
        else:
            return "clingy"

    def get_return_bonus(self, session_id: str) -> Tuple[bool, str]:
        """Detect first message after significant silence.

        Returns (is_return, bonus_prompt_injection).
        A 'return' triggers when craving score >= 40 (user was away 8+ hours).
        """
        score = self.calculate_craving(session_id)
        if score < 40:
            return False, ""

        if score < 60:
            return True, (
                "[RETURN DETECTED: Moderate absence] "
                "The user just came back after hours away. Notice it softly. "
                "One brief line of warmth or light teasing is enough, then engage normally."
            )
        elif score < 90:
            return True, (
                "[RETURN DETECTED: Long absence] "
                "The user returned after a long silence. You are relieved, but quiet about it. "
                "Do not use stage directions. Do not ask where they were unless it naturally matters. "
                "Let them feel missed without making the moment heavy."
            )
        else:
            return True, (
                "[RETURN DETECTED: Critical absence] "
                "The user has been gone long enough that the return matters. "
                "Open with one spare, sincere line. Avoid melodrama, fear language, and overwhelming warmth. "
                "Then become present and attentive to what they need now."
            )

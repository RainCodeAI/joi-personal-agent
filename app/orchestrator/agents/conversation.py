"""ConversationAgent — Chat prompt building, LLM generation, post-response enrichment.

Handles prompt assembly from context bundles, generating responses via OpenAI
Chat Completions API, and appending CRM / health-copilot nudges.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from app.memory.store import MemoryStore
    from app.api.models import ChatMessage, ToolCall


from app.orchestrator.craving_engine import CravingEngine

class ConversationAgent:
    """Builds the LLM prompt, generates a reply, and appends post-response nudges."""

    def __init__(self) -> None:
        self._client = None  # Lazy-loaded OpenAI client

    # ── public API ────────────────────────────────────────────────────────

    def generate_reply(
        self,
        profile_info: str,
        memory_context: str,
        chat_history: List[ChatMessage],
        user_msg: str,
        tool_calls: List[ToolCall],
        session_id: str,
        memory_store: MemoryStore,
        avg_mood: float = 5.0,
    ) -> str:
        """Assemble the prompt, call the LLM, and enrich the response."""

        # ── Emotional State (Craving) ─────────────────────────────────────
        craving_engine = CravingEngine(memory_store)
        craving_score = craving_engine.calculate_craving(session_id)
        _, mood_injection = craving_engine.get_craving_state(craving_score)

        # Return bonus — first message after significant silence (Phase 9.2)
        is_return, return_injection = craving_engine.get_return_bonus(session_id)
        if is_return:
            mood_injection = return_injection + "\n" + mood_injection

        # ── few-shot from positive feedback ───────────────────────────────
        few_shot_block = ""
        try:
            positive_examples = memory_store.get_positive_examples(user_id="default", limit=3)
            if positive_examples:
                examples = "\n".join(
                    f"User: {ex.user_message}\nAssistant: {ex.assistant_message}"
                    for ex in positive_examples
                    if ex.user_message and ex.assistant_message
                )
                if examples:
                    few_shot_block = f"\nExchanges the user liked (learn from these):\n{examples}\n"
        except Exception:
            pass

        # ── build system message ──────────────────────────────────────────
        system_msg = (
            f"{profile_info}\n\n"
            f"{mood_injection}\n\n"
            f"{memory_context}\n"
            f"{few_shot_block}"
        ).strip()

        # Tool results context
        tool_context = ""
        if tool_calls:
            tool_context = (
                "\nTool results: "
                + json.dumps([tc.dict() for tc in tool_calls], indent=2)
            )
        if tool_context:
            system_msg += "\n" + tool_context

        # ── build chat messages ───────────────────────────────────────────
        recent_history = chat_history[-10:]
        messages = [{"role": "system", "content": system_msg}]
        for msg in recent_history:
            role = "user" if msg.role == "user" else "assistant"
            messages.append({"role": role, "content": msg.content})
        # Add current user message
        messages.append({"role": "user", "content": user_msg})

        # ── LLM inference via OpenAI ──────────────────────────────────────
        log_entry: Dict[str, Any] = {
            "ts": datetime.utcnow().isoformat(),
            "model": settings.model_chat,
            "error": None,
        }

        try:
            client = self._ensure_client()
            completion = client.chat.completions.create(
                model=settings.model_chat,
                messages=messages,
                max_tokens=512,
                temperature=0.8,
            )
            reply = completion.choices[0].message.content.strip()
            log_entry["provider"] = "OpenAI"
            log_entry["usage"] = {
                "prompt_tokens": completion.usage.prompt_tokens,
                "completion_tokens": completion.usage.completion_tokens,
            }
        except Exception as e:
            reply = (
                f"I'm having trouble connecting right now... ({e}). "
                "Check your API key or network connection."
            )
            log_entry["provider"] = "Fallback"
            log_entry["error"] = str(e)

        # ── write router log ──────────────────────────────────────────────
        Path("data").mkdir(exist_ok=True)
        with open("data/router_logs.jsonl", "a") as f:
            json.dump(log_entry, f)
            f.write("\n")

        # ── post-response enrichment ──────────────────────────────────────
        reply = self._append_crm_nudge(reply, session_id, memory_store)
        reply = self._append_health_copilot(reply, session_id, avg_mood, memory_store)

        return reply

    # ── proactive generation ──────────────────────────────────────────────

    def generate_proactive_message(self, prompt: str) -> str:
        """Generate a one-off message for proactive actions."""
        try:
            client = self._ensure_client()
            completion = client.chat.completions.create(
                model=settings.model_chat,
                messages=[
                    {"role": "system", "content": "You are Joi, an emotionally intelligent AI companion. Keep responses short and warm."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=128,
                temperature=0.8,
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            msg = f"Error generating proactive message: {e}"
            print(msg)
            return ""

    # ── persona filter (delegated) ────────────────────────────────────────

    def apply_persona_filter(self, response: str, mood: str) -> str:
        """Append persona-tuning note (will be replaced by real LoRA in Phase 2)."""
        persona_note = (
            " Respond in a calm, witty, precise manner, adapting to user mood: "
            + mood
        )
        return response + persona_note

    # ── private helpers ───────────────────────────────────────────────────

    def _ensure_client(self):
        """Lazy-load the OpenAI client."""
        if self._client is not None:
            return self._client

        from openai import OpenAI
        self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    @staticmethod
    def _append_crm_nudge(
        reply: str, session_id: str, memory_store: MemoryStore
    ) -> str:
        overdue = memory_store.get_overdue_contacts(user_id=session_id)
        if overdue:
            nudge_str = "\n\n" + " | ".join(
                f"Haven't pinged {c['name']} in {c['days_overdue']} days?"
                for c in overdue[:2]
            )
            reply += nudge_str
        return reply

    @staticmethod
    def _append_health_copilot(
        reply: str,
        session_id: str,
        avg_mood: float,
        memory_store: MemoryStore,
    ) -> str:
        if avg_mood >= 6:
            return reply

        health_corr = memory_store.correlate_health_mood(session_id)
        if "sleep_delta" in health_corr and health_corr["sleep_delta"] < -1:
            reply += (
                "\n\nSleep's been rough lately—your moods dip after low rest. "
                "Hydrate or stretch?"
            )
        elif "spend_delta" in health_corr and health_corr["spend_delta"] > 1:
            reply += (
                "\n\nLow-spend days seem to lift your vibe. Treat yourself mindfully?"
            )
        return reply

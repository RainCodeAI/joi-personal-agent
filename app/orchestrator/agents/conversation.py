"""ConversationAgent — Chat prompt building, LLM generation, post-response enrichment.

Handles prompt assembly from context bundles, generating responses via OpenAI
Chat Completions API, and appending CRM / health-copilot nudges.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, TYPE_CHECKING

from app.config import DEFAULT_USER_ID, settings
from services.ai_router import route_request

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.memory.store import MemoryStore
    from app.api.models import ChatMessage, ToolCall


from app.orchestrator.craving_engine import CravingEngine


@dataclass
class ConversationReply:
    text: str
    provider: str = ""
    route: List[str] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)

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
        attachment_contexts: List[str],
        tool_calls: List[ToolCall],
        session_id: str,
        memory_store: MemoryStore,
        avg_mood: float = 5.0,
        on_token: Callable[[str], None] | None = None,
    ) -> str:
        """Backward-compatible text-only reply."""
        return self.generate_reply_payload(
            profile_info=profile_info,
            memory_context=memory_context,
            chat_history=chat_history,
            user_msg=user_msg,
            attachment_contexts=attachment_contexts,
            tool_calls=tool_calls,
            session_id=session_id,
            memory_store=memory_store,
            avg_mood=avg_mood,
            on_token=on_token,
        ).text

    def generate_reply_payload(
        self,
        profile_info: str,
        memory_context: str,
        chat_history: List[ChatMessage],
        user_msg: str,
        attachment_contexts: List[str],
        tool_calls: List[ToolCall],
        session_id: str,
        memory_store: MemoryStore,
        avg_mood: float = 5.0,
        on_token: Callable[[str], None] | None = None,
    ) -> ConversationReply:
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
        messages.append(
            {
                "role": "user",
                "content": self._build_user_turn(user_msg, attachment_contexts),
            }
        )

        # ── LLM inference via OpenAI ──────────────────────────────────────
        log_entry: Dict[str, Any] = {
            "ts": datetime.utcnow().isoformat(),
            "model": settings.model_chat,
            "error": None,
        }

        try:
            routed = route_request(
                self._build_router_prompt(messages),
                {
                    "mood": "supportive" if avg_mood < 5 else "playful",
                },
                on_token=on_token,
            )
            reply = routed["response"].strip()
            log_entry["provider"] = routed["model_used"]
            log_entry["route"] = routed.get("route", [])
            log_entry["errors"] = routed.get("errors", [])
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

        return ConversationReply(
            text=reply,
            provider=log_entry.get("provider", ""),
            route=log_entry.get("route", []),
            errors=log_entry.get("errors", []),
        )

    # ── proactive generation ──────────────────────────────────────────────

    def generate_proactive_message(self, prompt: str) -> str:
        """Generate a one-off message for proactive actions."""
        try:
            client = self._ensure_client()
            completion = client.chat.completions.create(
                model=settings.model_chat,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Joi: quiet, attentive, affectionate when warranted, and restrained. "
                            "Write one short proactive message. Do not guilt-trip, over-explain, or sound like a notification."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=128,
                temperature=0.8,
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("generate_proactive_message failed: %s", e)
            return ""

    # ── persona filter (delegated) ────────────────────────────────────────

    def apply_persona_filter(self, response: str, mood: str) -> str:
        """Persona tuning hook (placeholder for a future LoRA pass).

        Persona is already applied via the system prompt, so this must not append
        instruction text to the user-facing reply — doing so leaked the tuning
        note verbatim to the user. Return the response unchanged for now.
        """
        return response

    # ── private helpers ───────────────────────────────────────────────────

    def _ensure_client(self):
        """Lazy-load the OpenAI client."""
        if self._client is not None:
            return self._client

        from openai import OpenAI
        self._client = OpenAI(api_key=settings.openai_api_key)
        return self._client

    @staticmethod
    def _build_router_prompt(messages: List[Dict[str, str]]) -> str:
        parts = []
        for msg in messages:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            parts.append(f"[{role}]\n{content}")
        return "\n\n".join(parts)

    @staticmethod
    def _build_user_turn(user_msg: str, attachment_contexts: List[str]) -> str:
        parts: List[str] = []
        stripped = user_msg.strip()
        if stripped:
            parts.append(f"[TEXT]\n{stripped}")
        for context in attachment_contexts:
            if context.strip():
                parts.append(f"[ATTACHMENT]\n{context.strip()}")
        return "\n\n".join(parts) if parts else user_msg

    @staticmethod
    def _append_crm_nudge(
        reply: str, session_id: str, memory_store: MemoryStore
    ) -> str:
        overdue = memory_store.get_overdue_contacts(user_id=DEFAULT_USER_ID)
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

        health_corr = memory_store.correlate_health_mood(DEFAULT_USER_ID)
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

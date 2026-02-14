"""ConversationAgent — Chat prompt building, LLM generation, post-response enrichment.

Handles prompt assembly from context bundles, lazy-loading the HuggingFace
pipeline, generating responses, and appending CRM / health-copilot nudges.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, TYPE_CHECKING

import torch
try:
    from transformers import pipeline as hf_pipeline, AutoTokenizer, AutoModelForCausalLM
except ImportError:
    import logging
    logging.warning("Could not import transformers. Chat will be disabled.")
    hf_pipeline, AutoTokenizer, AutoModelForCausalLM = None, None, None

from app.config import settings

if TYPE_CHECKING:
    from app.memory.store import MemoryStore
    from app.api.models import ChatMessage, ToolCall


class ConversationAgent:
    """Builds the LLM prompt, generates a reply, and appends post-response nudges."""

    def __init__(self) -> None:
        self._generator = None  # Lazy-loaded HuggingFace pipeline

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

        # ── build prompt ──────────────────────────────────────────────────
        recent_history = chat_history[-10:]
        history_text = "\n".join(
            f"{msg.role}: {msg.content}" for msg in recent_history
        )

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
            pass  # Gracefully degrade if feedback table doesn't exist yet

        prompt = (
            f"{profile_info}\n{memory_context}\n"
            f"{few_shot_block}"
            f"Chat history (recent):\n{history_text}\n"
            f"User: {user_msg}\nAssistant:"
        )
        if tool_calls:
            prompt += (
                "\nTool results: "
                + json.dumps([tc.dict() for tc in tool_calls], indent=2)
            )

        # ── LLM inference ─────────────────────────────────────────────────
        log_entry: Dict[str, Any] = {
            "ts": datetime.utcnow().isoformat(),
            "prompt_len": len(prompt),
            "error": None,
        }

        try:
            gen = self._ensure_generator()
            with torch.no_grad():
                outputs = gen(
                    prompt,
                    max_new_tokens=256,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=gen.tokenizer.eos_token_id,
                )
                full_text = outputs[0]["generated_text"]
                reply = full_text.split("Assistant:")[-1].strip()
            log_entry["provider"] = "HuggingFace"
        except Exception as e:
            reply = (
                f"Error generating response: {e}. "
                "Check model download or hardware."
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
        # Simple wrapper around the generator
        try:
            gen = self._ensure_generator()
            with torch.no_grad():
                outputs = gen(
                    prompt,
                    max_new_tokens=128, # Shorter for nudges
                    temperature=0.8,    # Higher creativity
                    do_sample=True,
                    pad_token_id=gen.tokenizer.eos_token_id,
                )
                # If prompt ends with "Assistant:", split. Else take full.
                # Usually we provide the prompt.
                full_text = outputs[0]["generated_text"]
                # Heuristic: if prompt is in text, remove it.
                if full_text.startswith(prompt):
                    return full_text[len(prompt):].strip()
                return full_text.strip()
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

    def _ensure_generator(self):
        """Lazy-load the HuggingFace text-generation pipeline."""
        if self._generator is not None:
            return self._generator

        model_id = settings.model_chat
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        self._generator = hf_pipeline(
            "text-generation",
            model=model_id,
            tokenizer=tokenizer,
            model_kwargs={
                "torch_dtype": (
                    torch.float16
                    if torch.backends.mps.is_available()
                    else torch.float32
                )
            },
            # device_map="auto", # Removed to avoid accelerate errors on CPU/Win
            trust_remote_code=True,
            max_new_tokens=256,
            do_sample=True,
            temperature=0.7,
            pad_token_id=tokenizer.eos_token_id,
        )
        return self._generator

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

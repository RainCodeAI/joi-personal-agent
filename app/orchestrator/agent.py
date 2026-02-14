"""Joi Orchestrator — Thin router that delegates to focused sub-agents.

Pipeline per user message:
    MemoryRetriever → Planner → Executor → Conversation

All original public method signatures (reply, say_and_sync, log_action,
journal_prompt, analyze_journal_entry) are preserved for backward compat.
"""

from __future__ import annotations

import base64
import io
import json
import struct
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from app.api.models import ChatMessage, ChatResponse, ToolCall
from app.config import settings
from app.memory.store import MemoryStore
from app.orchestrator.agents.planner import PlannerAgent
from app.orchestrator.agents.memory_retriever import MemoryRetrieverAgent
from app.orchestrator.agents.executor import ExecutorAgent
from app.orchestrator.agents.conversation import ConversationAgent
from app.orchestrator.security.prompt_guard import PromptGuard
from app.orchestrator.audit import AuditLogger


class Agent:
    """Backward-compatible orchestrator.

    Instantiates four sub-agents and routes each ``reply()`` call through
    the pipeline: MemoryRetriever → Planner → Executor → Conversation.
    """

    def __init__(self) -> None:
        self.memory_store = MemoryStore()
        self.ollama_host = settings.ollama_host

        # Sub-agents
        self._memory_retriever = MemoryRetrieverAgent()
        self._planner = PlannerAgent()
        self._executor = ExecutorAgent()
        self._conversation = ConversationAgent()

        # Security & audit
        self._prompt_guard = PromptGuard()
        self._audit = AuditLogger()

    # ── main entry point ──────────────────────────────────────────────────

    def reply(
        self,
        chat_history: List[ChatMessage],
        user_msg: str,
        session_id: str,
    ) -> ChatResponse:
        import time as _time
        _t0 = _time.perf_counter()
        threats_detected: List[str] = []

        # 0. Prompt guard — sanitize user input
        guard_result = self._prompt_guard.sanitize(user_msg)
        user_msg = guard_result.text
        threats_detected = guard_result.threats_detected

        # Persist the incoming user message
        self.memory_store.add_chat_message(session_id, "user", user_msg)
        self.memory_store.add_memory("user_input", user_msg, ["chat", session_id])

        # 1. Memory Retriever — gather context
        context = self._memory_retriever.retrieve_context(
            session_id, user_msg, chat_history, self.memory_store
        )

        # 2. Planner — assemble proactive-planning context
        planner_ctx = self._planner.enrich(
            session_id,
            user_msg,
            chat_history,
            self.memory_store,
            avg_mood=context.avg_mood,
            sentiment=context.sentiment,
        )
        # Merge planner context into profile_info
        for value in planner_ctx.values():
            if value:
                context.profile_info += " " + value

        # 3. Executor — dispatch tools
        tool_calls = self._executor.execute_tools(user_msg, session_id)

        # 4. Conversation — generate LLM reply
        reply = self._conversation.generate_reply(
            profile_info=context.profile_info,
            memory_context=context.memory_context,
            chat_history=chat_history,
            user_msg=user_msg,
            tool_calls=tool_calls,
            session_id=session_id,
            memory_store=self.memory_store,
            avg_mood=context.avg_mood,
        )

        # Persist assistant reply
        self.memory_store.add_chat_message(session_id, "assistant", reply)

        # Audit ledger
        self.log_action(
            "chat_reply",
            {
                "user_msg": user_msg,
                "reply": reply,
                "tool_calls": [tc.dict() for tc in tool_calls],
            },
        )

        # 5. Emit decision trace for diagnostics
        _elapsed_ms = int((_time.perf_counter() - _t0) * 1000)
        self._audit.log_decision_trace(
            session_id=session_id,
            sub_agents_invoked=["MemoryRetriever", "Planner", "Executor", "Conversation"],
            context_summary=context.profile_info[:200],
            llm_response_preview=reply[:200],
            tool_calls=[tc.dict() for tc in tool_calls],
            threats_detected=threats_detected,
            latency_ms=_elapsed_ms,
        )

        return ChatResponse(text=reply, session_id=session_id, tool_calls=tool_calls)

    # ── persona filter (delegated) ────────────────────────────────────────

    def apply_persona_filter(self, response: str, mood: str) -> str:
        return self._conversation.apply_persona_filter(response, mood)

    # ── TTS + lip-sync (self-contained, kept here) ────────────────────────

    def say_and_sync(self, text: str, session_id: str) -> Dict[str, Any]:
        """Generate dummy audio (silence WAV) + phoneme timeline for lip-sync."""
        sample_rate = 22050
        duration = len(text.split()) * 0.3
        frames = int(sample_rate * max(duration, 0.5))
        audio_data = b"".join(struct.pack("<h", 0) for _ in range(frames))

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_data)
        audio_bytes = wav_buffer.getvalue()

        phoneme_timeline = self._text_to_phonemes(text)

        # Sentiment from DB
        recent_moods = self.memory_store.get_recent_moods(session_id, 1)
        if recent_moods:
            mood_value = recent_moods[0].mood
            if mood_value >= 7:
                sentiment = "positive"
            elif mood_value <= 4:
                sentiment = "stress"
            else:
                sentiment = "neutral"
        else:
            sentiment = "neutral"

        return {
            "audio_url": f"data:audio/wav;base64,{base64.b64encode(audio_bytes).decode()}",
            "phoneme_timeline": phoneme_timeline,
            "sentiment": sentiment,
        }

    def _text_to_phonemes(self, text: str):
        """Map text → viseme timeline using English pronunciation heuristics."""
        CHAR_TO_VISEME = {
            "a": "A", "à": "A", "á": "A",
            "e": "E", "è": "E", "é": "E", "i": "E", "î": "E", "y": "E",
            "o": "O", "ò": "O", "ó": "O",
            "u": "U", "ù": "U", "ú": "U", "w": "U",
            "m": "MB", "b": "MB", "p": "MB",
            "f": "FV", "v": "FV",
        }
        VOWEL_DURATION = 0.12
        CONSONANT_DURATION = 0.06
        WORD_GAP = 0.08

        timeline = []
        t = 0.0

        words = text.split()
        if not words:
            return [(0.0, "rest")]

        for word_idx, word in enumerate(words):
            clean = "".join(c for c in word.lower() if c.isalpha())
            if not clean:
                t += WORD_GAP
                continue

            i = 0
            while i < len(clean):
                char = clean[i]
                viseme = CHAR_TO_VISEME.get(char)

                if viseme:
                    if i + 1 < len(clean):
                        digraph = clean[i : i + 2]
                        if digraph in ("th", "sh", "ch", "ng", "ck"):
                            timeline.append((round(t, 3), "rest"))
                            t += CONSONANT_DURATION
                            i += 2
                            continue
                        elif digraph in ("ou", "oo"):
                            timeline.append((round(t, 3), "O"))
                            t += VOWEL_DURATION
                            i += 2
                            continue
                        elif digraph in ("ee", "ea", "ie"):
                            timeline.append((round(t, 3), "E"))
                            t += VOWEL_DURATION
                            i += 2
                            continue
                        elif digraph in ("ai", "ay"):
                            timeline.append((round(t, 3), "A"))
                            t += VOWEL_DURATION
                            i += 2
                            continue

                    duration = (
                        VOWEL_DURATION
                        if viseme in ("A", "E", "O", "U")
                        else CONSONANT_DURATION
                    )
                    timeline.append((round(t, 3), viseme))
                    t += duration
                else:
                    timeline.append((round(t, 3), "rest"))
                    t += CONSONANT_DURATION

                i += 1

            if word_idx < len(words) - 1:
                timeline.append((round(t, 3), "rest"))
                t += WORD_GAP

        timeline.append((round(t, 3), "rest"))

        # Deduplicate consecutive identical visemes
        deduped = [timeline[0]]
        for entry in timeline[1:]:
            if entry[1] != deduped[-1][1]:
                deduped.append(entry)

        return deduped

    # ── action ledger ─────────────────────────────────────────────────────

    def log_action(self, action: str, data: Dict[str, Any]) -> None:
        ledger_path = Path("./data/action_ledger.jsonl")
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with open(ledger_path, "a") as f:
            json.dump(
                {"ts": datetime.utcnow().isoformat(), "action": action, "data": data},
                f,
            )
            f.write("\n")

    # ── journal helpers ───────────────────────────────────────────────────

    def journal_prompt(self, mood: str, location: str, session_id: str) -> str:
        prompt = (
            f"Generate a journaling prompt for someone feeling {mood} in {location}. "
            "Make it empathetic and insightful."
        )
        result = route_request(prompt, {"mood": mood})
        return result["response"]

    def analyze_journal_entry(self, entry: str, session_id: str) -> str:
        prompt = f"Analyze this journal entry for emotions and insights: {entry}"
        result = route_request(prompt, {"mood": "neutral"})
        return result["response"]
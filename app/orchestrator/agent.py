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
from typing import Any, Callable, Dict, List

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

    def __init__(self, memory_store: MemoryStore | None = None) -> None:
        self.memory_store = memory_store or MemoryStore()
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
        *,
        on_token: Callable[[str], None] | None = None,
        attachment_contexts: List[str] | None = None,
        extra_context: str | None = None,
    ) -> ChatResponse:
        import time as _time
        _t0 = _time.perf_counter()
        threats_detected: List[str] = []

        # 0. Prompt guard — sanitize user input
        guard_result = self._prompt_guard.sanitize(user_msg)
        user_msg = guard_result.text
        threats_detected = guard_result.threats_detected

        # Compute craving state for UI feedback (Phase 9.2)
        from app.orchestrator.craving_engine import CravingEngine
        _craving = CravingEngine(self.memory_store)
        craving_score = _craving.calculate_craving(session_id)
        is_return, _ = _craving.get_return_bonus(session_id)

        # Persist the incoming user message
        user_record = self.memory_store.add_chat_message(session_id, "user", user_msg)
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
        memory_context = context.memory_context
        if extra_context:
            memory_context = f"{memory_context}\n{extra_context}".strip()

        reply_payload = self._conversation.generate_reply_payload(
            profile_info=context.profile_info,
            memory_context=memory_context,
            chat_history=chat_history,
            user_msg=user_msg,
            attachment_contexts=attachment_contexts or [],
            tool_calls=tool_calls,
            session_id=session_id,
            memory_store=self.memory_store,
            avg_mood=context.avg_mood,
            on_token=on_token,
        )
        reply = reply_payload.text

        # Persist assistant reply
        assistant_record = self.memory_store.add_chat_message(session_id, "assistant", reply)

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

        return ChatResponse(
            text=reply,
            session_id=session_id,
            tool_calls=[tc.dict() for tc in tool_calls],
            craving_score=craving_score,
            is_dramatic_return=is_return,
            provider=reply_payload.provider,
            route=reply_payload.route,
            errors=reply_payload.errors,
            user_message_id=user_record.id,
            assistant_message_id=assistant_record.id,
            assistant_timestamp=assistant_record.timestamp.isoformat(),
        )

    # ── persona filter (delegated) ────────────────────────────────────────

    def run_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool directly (e.g. after approval)."""
        tc = self._executor.run_tool(tool_name, args)
        self.log_action("tool_execution", tc.dict())
        return tc.dict()

    # ── persona filter (delegated) ────────────────────────────────────────

    def apply_persona_filter(self, response: str, mood: str) -> str:
        return self._conversation.apply_persona_filter(response, mood)

    # ── TTS + lip-sync (self-contained, kept here) ────────────────────────

    def say_and_sync(self, text: str, session_id: str) -> Dict[str, Any]:
        """Generate audio and phonemes for lip-sync."""
        # Determine whisper mode from craving state (Phase 9.3)
        from app.orchestrator.craving_engine import CravingEngine
        _craving = CravingEngine(self.memory_store)
        whisper_mode = _craving.calculate_craving(session_id) >= 60

        # Synthesize real audio via voice_tools
        from app.tools.voice import voice_tools
        audio_bytes = voice_tools.synthesize_speech(text, whisper_mode=whisper_mode)
        
        if not audio_bytes:
            # Fallback to dummy silence if synth fails
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

        # ── Infer delivery style from text and context ────────────────────
        import re as _re
        if whisper_mode:
            delivery_style = "whisper"
        elif _re.search(r"\.{2,}|[-–—]{2,}", text):
            delivery_style = "hesitant"
        elif _re.search(r"!", text) or sum(1 for w in text.split() if w.isupper() and len(w) > 1) >= 2:
            delivery_style = "intense"
        else:
            delivery_style = "normal"

        phoneme_timeline = self._text_to_phonemes(text, delivery_style)

        # ── Scale timeline to actual audio duration ───────────────────────
        # Wider clamp (±45%) handles slow/fast TTS voices and whisper mode.
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                audio_duration = wf.getnframes() / float(wf.getframerate())
            if phoneme_timeline and len(phoneme_timeline) > 1:
                raw_end = phoneme_timeline[-1][0]
                if raw_end > 0 and audio_duration > 0:
                    scale = (audio_duration * 0.97) / raw_end
                    scale = max(0.55, min(scale, 1.55))
                    phoneme_timeline = [
                        (round(t * scale, 3), ph) for t, ph in phoneme_timeline
                    ]
        except Exception:
            pass  # WAV parse failure: use raw timeline

        # ── Sentiment from DB ─────────────────────────────────────────────
        from app.config import DEFAULT_USER_ID
        recent_moods = self.memory_store.get_recent_moods(DEFAULT_USER_ID, 1)
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

        # Stressed sentiment nudges delivery timing even when not inferred above
        if delivery_style == "normal" and sentiment in ("stress", "negative", "concern"):
            delivery_style = "stressed"

        return {
            "audio_url": f"data:audio/wav;base64,{base64.b64encode(audio_bytes).decode()}",
            "phoneme_timeline": phoneme_timeline,
            "sentiment": sentiment,
            "delivery_style": delivery_style,
        }

    # ─────────────────────────────────────────────────────────────────────
    # G2P v2 — syllable-based timeline with full digraph table and
    # delivery-style timing modulation.
    # ─────────────────────────────────────────────────────────────────────

    # Ordered pattern table: (grapheme_string, [viseme_labels]).
    # Matched greedy left-to-right longest-first per starting character.
    _G2P_PATTERNS = [
        # ── 4-char patterns ────────────────────────────────────────────
        ("tion", ["S", "U", "rest"]),
        ("sion", ["S", "U", "rest"]),
        ("ight", ["A"]),
        ("ould", ["U"]),
        ("ough", ["O"]),
        # ── 3-char patterns ────────────────────────────────────────────
        ("tch", ["K"]),
        ("dge", ["rest"]),
        ("sch", ["S"]),
        ("thr", ["TH", "R"]),
        ("str", ["S", "R"]),
        ("spr", ["S", "R"]),
        ("igh", ["A"]),
        ("nce", ["rest", "S"]),
        ("ear", ["E", "R"]),
        ("oor", ["U", "R"]),
        ("our", ["O", "R"]),
        ("air", ["A", "R"]),
        ("are", ["A", "R"]),
        ("ore", ["O", "R"]),
        ("ing", ["E", "rest"]),
        ("ang", ["A", "rest"]),
        ("ong", ["O", "rest"]),
        ("nge", ["rest"]),
        # ── 2-char patterns ────────────────────────────────────────────
        ("th", ["TH"]),
        ("sh", ["S"]),
        ("ch", ["K"]),
        ("ph", ["FV"]),
        ("wh", ["U"]),
        ("ck", ["K"]),
        ("ng", ["rest"]),
        ("nk", ["K"]),
        ("wr", ["R"]),
        ("kn", ["rest"]),
        ("mb", ["MB"]),
        ("mp", ["MB"]),
        ("qu", ["K", "U"]),
        ("oo", ["U"]),
        ("ou", ["O"]),
        ("ow", ["O"]),
        ("aw", ["O"]),
        ("au", ["O"]),
        ("oi", ["O"]),
        ("oy", ["O"]),
        ("oa", ["O"]),
        ("oe", ["O"]),
        ("ue", ["U"]),
        ("ui", ["U"]),
        ("ee", ["E"]),
        ("ea", ["E"]),
        ("ie", ["E"]),
        ("ei", ["E"]),
        ("ai", ["A"]),
        ("ay", ["A"]),
        ("ey", ["E"]),
        ("ew", ["U"]),
        ("tz", ["S"]),
        # ── Single-char vowels ─────────────────────────────────────────
        ("a", ["A"]), ("e", ["E"]), ("i", ["E"]), ("o", ["O"]),
        ("u", ["U"]), ("y", ["E"]),
        # ── Single-char consonants ─────────────────────────────────────
        ("b", ["MB"]), ("c", ["K"]),  ("d", ["rest"]), ("f", ["FV"]),
        ("g", ["K"]),  ("h", ["rest"]),("j", ["rest"]), ("k", ["K"]),
        ("l", ["L"]),  ("m", ["MB"]), ("n", ["rest"]), ("p", ["MB"]),
        ("q", ["K"]),  ("r", ["R"]),  ("s", ["S"]),   ("t", ["rest"]),
        ("v", ["FV"]), ("w", ["U"]),  ("x", ["K", "S"]), ("z", ["S"]),
    ]

    # Build per-first-char lookup at class load time (longest match first)
    _G2P_LOOKUP: Dict[str, List] = {}
    for _pat, _vis in _G2P_PATTERNS:
        _G2P_LOOKUP.setdefault(_pat[0], []).append((len(_pat), _pat, _vis))
    for _c in _G2P_LOOKUP:
        _G2P_LOOKUP[_c].sort(key=lambda x: -x[0])

    @staticmethod
    def _syllable_count(word: str) -> int:
        """Count vowel groups as a syllable approximation."""
        count, in_vowel = 0, False
        for ch in word:
            if ch in "aeiouy":
                if not in_vowel:
                    count += 1
                in_vowel = True
            else:
                in_vowel = False
        # Silent trailing 'e' doesn't form its own syllable
        if word.endswith("e") and len(word) > 2 and count > 1:
            count -= 1
        return max(1, count)

    def _text_to_phonemes(self, text: str, delivery_style: str = "normal") -> list:
        """
        Improved G2P: full digraph/trigraph table, punctuation pauses,
        syllable-based word timing, and delivery-style modulation.
        """
        import re

        # Per-style timing multipliers: (vowel, consonant, gap)
        _STYLE = {
            "whisper":  (1.40, 1.50, 1.60),
            "intense":  (0.85, 0.72, 0.68),
            "hesitant": (1.20, 1.00, 1.80),
            "stressed": (1.10, 1.00, 1.20),
            "normal":   (1.00, 1.00, 1.00),
        }
        vm, cm, gm = _STYLE.get(delivery_style, _STYLE["normal"])

        BASE_VOWEL   = 0.13 * vm
        BASE_CONS    = 0.06 * cm
        WORD_GAP     = 0.09 * gm
        COMMA_PAUSE  = 0.14 * gm
        SENT_PAUSE   = 0.22 * gm
        HESIT_PAUSE  = 0.20 * gm
        SYL_DUR      = 0.21  # target seconds per syllable

        VOWEL_SET = {"A", "E", "O", "U", "Oh"}
        lookup = self._G2P_LOOKUP

        # ── Tokenise: normalise ellipsis/dashes to HESIT token ────────────
        text = re.sub(r"\.{2,}", " HESIT ", text)
        text = re.sub(r"[-–—]{2,}", " HESIT ", text)
        tokens = re.findall(r"[A-Za-z']+|[.,!?;:]|HESIT", text)

        # Count actual words (skip punctuation tokens) for gap logic
        n_words = sum(1 for t in tokens
                      if t not in (",", ".", "!", "?", ";", ":", "HESIT"))
        word_idx = 0

        timeline: list = []
        t = 0.0

        for tok in tokens:
            # ── Punctuation / hesitation pauses ───────────────────────────
            if tok == "HESIT":
                timeline.append((round(t, 3), "rest"))
                t += HESIT_PAUSE
                continue
            if tok == ",":
                timeline.append((round(t, 3), "rest"))
                t += COMMA_PAUSE
                continue
            if tok in (".", "!", "?", ";", ":"):
                timeline.append((round(t, 3), "rest"))
                t += SENT_PAUSE
                continue

            # ── Word ──────────────────────────────────────────────────────
            clean = re.sub(r"[^a-z]", "", tok.lower())
            if not clean:
                word_idx += 1
                continue

            # Build relative phoneme sequence for this word
            rel: list = []   # (relative_time, viseme)
            wt = 0.0
            i = 0
            while i < len(clean):
                ch = clean[i]
                matched = False
                if ch in lookup:
                    for plen, pat, visemes in lookup[ch]:
                        if clean[i:i + plen] == pat:
                            for v in visemes:
                                dur = BASE_VOWEL if v in VOWEL_SET else BASE_CONS
                                rel.append((round(wt, 3), v))
                                wt += dur
                            i += plen
                            matched = True
                            break
                if not matched:
                    rel.append((round(wt, 3), "rest"))
                    wt += BASE_CONS
                    i += 1

            if not rel:
                word_idx += 1
                continue

            # Scale relative times so word fits syllable-based target duration
            n_syl = self._syllable_count(clean)
            target = n_syl * SYL_DUR
            if delivery_style == "whisper":
                target *= 1.35
            elif delivery_style == "intense":
                target *= 0.82
            scale = max(0.55, min((target / wt) if wt > 0 else 1.0, 1.65))

            for rel_t, vis in rel:
                timeline.append((round(t + rel_t * scale, 3), vis))
            t += target

            # Inter-word gap (not after the final word)
            if word_idx < n_words - 1:
                timeline.append((round(t, 3), "rest"))
                t += WORD_GAP

            word_idx += 1

        timeline.append((round(t, 3), "rest"))

        if not timeline:
            return [(0.0, "rest")]

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
        return self._conversation.generate_proactive_message(prompt)

    def analyze_journal_entry(self, entry: str, session_id: str) -> str:
        prompt = f"Analyze this journal entry for emotions and insights: {entry}"
        return self._conversation.generate_proactive_message(prompt)

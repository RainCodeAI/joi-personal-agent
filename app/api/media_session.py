from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict

from app.persistence import read_json, write_json_atomic


class MediaSessionStore:
    """In-memory state for browser-driven media sessions."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        loaded = read_json(path, {}) if path is not None else {}
        self._sessions: Dict[str, Dict[str, Any]] = loaded if isinstance(loaded, dict) else {}
        self._lock = Lock()

    def get(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            existing = self._sessions.get(session_id)
            if existing is None:
                existing = self._default_state(session_id)
                self._sessions[session_id] = existing
            else:
                existing = {**self._default_state(session_id), **existing}
                self._sessions[session_id] = existing
            return dict(existing)

    def update(self, session_id: str, **patch: Any) -> Dict[str, Any]:
        with self._lock:
            current = self._sessions.get(session_id)
            if current is None:
                current = self._default_state(session_id)
            else:
                current = {**self._default_state(session_id), **current}
            for key, value in patch.items():
                if value is not None:
                    current[key] = value
            current["updated_at"] = datetime.utcnow().isoformat()
            self._sessions[session_id] = current
            if self.path is not None:
                write_json_atomic(self.path, self._sessions)
            return dict(current)

    @staticmethod
    def _default_state(session_id: str) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        return {
            "session_id": session_id,
            "assistant_turn_id": None,
            "voice_mode": "push_to_talk",
            "turn_state": "idle",
            "mic_state": "idle",
            "speaking_state": "idle",
            "capture_source": "browser",
            "last_transcript": "",
            "recognition_latency_ms": None,
            "end_of_speech_to_transcript_ms": None,
            "speech_duration_ms": None,
            "speech_detected": False,
            "playback_latency_ms": None,
            "interruption_count": 0,
            "last_error": None,
            "updated_at": now,
        }

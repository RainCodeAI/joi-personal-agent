from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Any, Dict


class MediaSessionStore:
    """In-memory state for browser-driven media sessions."""

    def __init__(self) -> None:
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    def get(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            existing = self._sessions.get(session_id)
            if existing is None:
                existing = self._default_state(session_id)
                self._sessions[session_id] = existing
            return dict(existing)

    def update(self, session_id: str, **patch: Any) -> Dict[str, Any]:
        with self._lock:
            current = self._sessions.get(session_id)
            if current is None:
                current = self._default_state(session_id)
            for key, value in patch.items():
                if value is not None:
                    current[key] = value
            current["updated_at"] = datetime.utcnow().isoformat()
            self._sessions[session_id] = current
            return dict(current)

    @staticmethod
    def _default_state(session_id: str) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        return {
            "session_id": session_id,
            "mic_state": "idle",
            "speaking_state": "idle",
            "capture_source": "browser",
            "last_transcript": "",
            "recognition_latency_ms": None,
            "playback_latency_ms": None,
            "interruption_count": 0,
            "last_error": None,
            "updated_at": now,
        }

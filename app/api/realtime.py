from __future__ import annotations

import asyncio
import json
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional
from uuid import uuid4


class RealtimeEventBus:
    """Process-local pub/sub bus for SSE clients."""

    # Per-subscriber queue cap. A stalled or dead client can't grow memory without
    # bound; once full, its oldest queued events are dropped (it still gets a
    # backfill on reconnect).
    _SUBSCRIBER_QUEUE_MAX = 256

    def __init__(self, history_limit: int = 200) -> None:
        self._history: Deque[Dict[str, Any]] = deque(maxlen=history_limit)
        self._subscribers: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def publish(
        self,
        event: str,
        payload: Dict[str, Any],
        *,
        session_id: Optional[str] = None,
        source: str = "system",
    ) -> Dict[str, Any]:
        envelope = {
            "api_version": "v2",
            "event_id": str(uuid4()),
            "event": event,
            "source": source,
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
        }
        async with self._lock:
            self._history.append(envelope)
            subscribers = list(self._subscribers.values())

        for subscriber in subscribers:
            target_session = subscriber["session_id"]
            if target_session is not None and target_session != session_id:
                continue
            queue = subscriber["queue"]
            try:
                queue.put_nowait(envelope)
            except asyncio.QueueFull:
                # Drop the oldest event to make room; a wedged client must not
                # block publishers or grow without bound.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(envelope)
                except asyncio.QueueFull:
                    pass

        return envelope

    async def subscribe(self, session_id: Optional[str] = None) -> tuple[str, asyncio.Queue]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self._SUBSCRIBER_QUEUE_MAX)
        subscriber_id = str(uuid4())
        async with self._lock:
            self._subscribers[subscriber_id] = {
                "session_id": session_id,
                "queue": queue,
            }
        return subscriber_id, queue

    async def unsubscribe(self, subscriber_id: str) -> None:
        async with self._lock:
            self._subscribers.pop(subscriber_id, None)

    async def get_recent(
        self,
        *,
        session_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        async with self._lock:
            events = list(self._history)

        if session_id is not None:
            events = [event for event in events if event.get("session_id") == session_id]
        if limit <= 0:
            return []
        return events[-limit:]


def format_sse_event(envelope: Dict[str, Any]) -> str:
    return (
        f"id: {envelope['event_id']}\n"
        f"event: {envelope['event']}\n"
        f"data: {json.dumps(envelope)}\n\n"
    )

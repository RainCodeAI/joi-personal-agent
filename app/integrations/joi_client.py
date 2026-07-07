"""Async client for the local Joi FastAPI backend.

The Telegram bridge (and any future remote surface) uses this to route messages
through the same `/api/v2/chat` pipeline the web UI uses, so memory, approvals,
and behaviour stay centralized. It is a plain HTTP client — it does not import
or duplicate the orchestrator.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx


class JoiApiError(Exception):
    """Raised when the Joi backend is unreachable or returns an error status."""


class JoiClient:
    def __init__(self, base_url: str, token: str = "", timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout

    def _headers(self) -> Dict[str, str]:
        headers = {"content-type": "application/json"}
        if self._token:
            headers["x-joi-api-token"] = self._token
        return headers

    async def _request(self, method: str, path: str, *, json: Optional[dict] = None) -> httpx.Response:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(method, url, json=json, headers=self._headers())
        except httpx.HTTPError as exc:
            raise JoiApiError(f"Joi backend unreachable: {exc}") from exc
        if response.status_code >= 400:
            raise JoiApiError(f"Joi backend returned {response.status_code} for {path}")
        return response

    async def health(self) -> bool:
        """True if the backend /health endpoint is reachable and ok."""
        try:
            response = await self._request("GET", "/health")
        except JoiApiError:
            return False
        try:
            return response.json().get("status") == "ok"
        except Exception:
            return True  # reachable but unexpected body — still "up"

    async def ensure_session(self, session_id: str, title: str = "Telegram") -> None:
        """Create the session if it does not exist. Idempotent by session_id."""
        await self._request(
            "POST",
            "/api/v2/sessions",
            json={"session_id": session_id, "title": title},
        )

    async def chat(self, session_id: str, text: str) -> Dict[str, Any]:
        """Send a user message; returns the V2ChatResponse body."""
        response = await self._request(
            "POST",
            "/api/v2/chat",
            json={"session_id": session_id, "text": text},
        )
        return response.json()

    async def recent_messages(self, session_id: str, limit: int = 6) -> List[Dict[str, Any]]:
        """Return the last `limit` messages for a session (empty if none/unknown)."""
        try:
            response = await self._request(
                "GET", f"/api/v2/sessions/{session_id}/messages?limit={limit}"
            )
        except JoiApiError:
            return []
        return response.json().get("messages", [])

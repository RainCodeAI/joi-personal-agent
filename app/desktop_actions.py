from __future__ import annotations

import json
import logging
import uuid
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Literal
from urllib.parse import urlparse

log = logging.getLogger(__name__)

DesktopActionName = Literal["open_url", "show_notification"]

ALLOWED_DESKTOP_ACTIONS: set[str] = {"open_url", "show_notification"}
AUDIT_PATH = Path(__file__).resolve().parents[1] / "data" / "desktop_action_audit.jsonl"


class DesktopActionError(ValueError):
    """Raised when a desktop action request is invalid or blocked."""


@dataclass
class DesktopActionResult:
    action_id: str
    action: str
    status: Literal["success", "blocked", "error"]
    summary: str
    result: dict[str, Any]
    audit_record: dict[str, Any]


class DesktopActionBroker:
    """Narrow executor for safe native desktop actions."""

    def __init__(
        self,
        *,
        audit_path: Path = AUDIT_PATH,
        browser_open: Callable[[str], bool] | None = None,
        notifier: Callable[[str, str], None] | None = None,
    ) -> None:
        self.audit_path = audit_path
        self._browser_open = browser_open or webbrowser.open
        self._notifier = notifier or self._default_notify
        self._lock = RLock()

    def execute(
        self,
        action: str,
        args: dict[str, Any],
        *,
        session_id: str | None = None,
        confirmed: bool = False,
        source: str = "api",
    ) -> DesktopActionResult:
        action_id = str(uuid.uuid4())
        base_record = {
            "action_id": action_id,
            "session_id": session_id,
            "action": action,
            "source": source,
            "args": self._safe_args(args),
            "confirmed": confirmed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            if not confirmed:
                raise DesktopActionError("Desktop action requires explicit confirmation")
            if action not in ALLOWED_DESKTOP_ACTIONS:
                raise DesktopActionError(f"Desktop action is not allowlisted: {action}")

            if action == "open_url":
                result = self._open_url(args)
            elif action == "show_notification":
                result = self._show_notification(args)
            else:
                raise DesktopActionError(f"Unsupported desktop action: {action}")
        except DesktopActionError as exc:
            record = {**base_record, "status": "blocked", "error": str(exc)}
            self._write_audit(record)
            return DesktopActionResult(
                action_id=action_id,
                action=action,
                status="blocked",
                summary=str(exc),
                result={},
                audit_record=record,
            )
        except Exception as exc:
            log.warning("Desktop action failed: %s", exc)
            record = {**base_record, "status": "error", "error": str(exc)}
            self._write_audit(record)
            return DesktopActionResult(
                action_id=action_id,
                action=action,
                status="error",
                summary=f"Desktop action failed: {exc}",
                result={},
                audit_record=record,
            )

        record = {**base_record, "status": "success", "result": result}
        self._write_audit(record)
        return DesktopActionResult(
            action_id=action_id,
            action=action,
            status="success",
            summary=result.get("summary", "Desktop action completed"),
            result=result,
            audit_record=record,
        )

    def _open_url(self, args: dict[str, Any]) -> dict[str, Any]:
        url = str(args.get("url") or "").strip()
        if not url:
            raise DesktopActionError("open_url requires a URL")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise DesktopActionError("open_url only allows absolute http/https URLs")

        opened = bool(self._browser_open(url))
        return {
            "url": url,
            "opened": opened,
            "summary": f"Opened URL: {url}",
        }

    def _show_notification(self, args: dict[str, Any]) -> dict[str, Any]:
        title = str(args.get("title") or "Joi").strip()[:120] or "Joi"
        message = str(args.get("message") or "").strip()[:500]
        if not message:
            raise DesktopActionError("show_notification requires a message")

        self._notifier(title, message)
        return {
            "title": title,
            "message": message,
            "summary": f"Showed notification: {title}",
        }

    def _default_notify(self, title: str, message: str) -> None:
        try:
            from plyer import notification

            notification.notify(title=title, message=message, app_name="Joi", timeout=5)
            return
        except Exception:
            pass
        log.info("Notification requested: %s - %s", title, message)

    def _safe_args(self, args: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in args.items():
            if isinstance(value, str):
                safe[key] = value[:500]
            elif isinstance(value, (int, float, bool)) or value is None:
                safe[key] = value
            else:
                safe[key] = str(value)[:500]
        return safe

    def _write_audit(self, record: dict[str, Any]) -> None:
        with self._lock:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True) + "\n")

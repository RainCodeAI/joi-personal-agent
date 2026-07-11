"""Telegram bridge for Joi — a standalone localhost client of the Joi API.

Run as its own process:

    python -m app.integrations.telegram_bot

It long-polls Telegram (no inbound ports opened), rejects any user not on the
numeric allowlist, and routes messages through `/api/v2/chat` so memory,
approvals, and behaviour stay centralized. Write/destructive actions are only
ever *reported* here — approval and execution stay local by design.
"""

from __future__ import annotations

import json
import logging
import time
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, Iterable, List

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import settings
from app.integrations.joi_client import JoiApiError, JoiClient

logger = logging.getLogger("joi.telegram")

# Redacted from approval previews sent to a remote surface.
_SENSITIVE_ARG_KEYS = {
    "authorization",
    "bcc",
    "body",
    "cc",
    "content",
    "html",
    "message",
    "password",
    "secret",
    "token",
    "to",
}

# Per-user active session id (in-memory; deterministic default per user).
_active_session: Dict[int, str] = {}
_ensured_sessions: set[str] = set()


def _default_session_id(user_id: int) -> str:
    return f"{settings.telegram_session_prefix}:{user_id}"


def _session_for(user_id: int) -> str:
    return _active_session.setdefault(user_id, _default_session_id(user_id))


def _client() -> JoiClient:
    # Generous timeout: the first chat can trigger slow model loading on the backend.
    return JoiClient(settings.telegram_api_base_url, settings.telegram_api_token, timeout=90.0)


def allowlisted(
    handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]],
) -> Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]:
    """Reject any user not on the numeric allowlist. Logs only the numeric ID."""

    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if user is None or user.id not in settings.telegram_allowed_ids:
            logger.warning("Rejected Telegram access from user_id=%s", getattr(user, "id", "unknown"))
            if update.effective_message is not None:
                await update.effective_message.reply_text(
                    "This is a private Joi bot. Your ID has been noted for the owner."
                )
            return
        await handler(update, context)

    return wrapper


def summarize_approvals(approvals: List[Dict[str, Any]]) -> str:
    """One-line, redacted summary of staged approvals for a remote reply."""
    if not approvals:
        return ""
    names = ", ".join(sorted({str(a.get("tool_name", "action")) for a in approvals}))
    return (
        f"\n\n⏳ I staged {len(approvals)} action(s) that need approval on the "
        f"laptop before anything happens: {names}. I won't run them from here."
    )


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[redacted]" if str(key).lower() in _SENSITIVE_ARG_KEYS else _redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _redact_args(args: Dict[str, Any]) -> Dict[str, Any]:
    return _redact_value(args)


def format_pending_approvals(approvals: List[Dict[str, Any]]) -> str:
    """Format a bounded, redacted, explicitly read-only approval list."""
    if not approvals:
        return "No pending approvals in this thread."

    lines = [f"Pending approvals in this thread ({len(approvals)}):"]
    for approval in approvals[:5]:
        tool_name = str(approval.get("tool_name", "action"))
        redacted_preview = approval.get("redacted_preview")
        preview_args = (
            redacted_preview.get("arguments")
            if isinstance(redacted_preview, dict)
            else None
        )
        args = preview_args if isinstance(preview_args, dict) else approval.get("args")
        safe_args = _redact_args(args) if isinstance(args, dict) else {}
        preview = json.dumps(safe_args, ensure_ascii=False, sort_keys=True)
        if len(preview) > 220:
            preview = preview[:217] + "..."
        lines.append(f"• {tool_name}: {preview}")
    if len(approvals) > 5:
        lines.append(f"• …and {len(approvals) - 5} more")
    lines.append("Read-only here — approve or deny these on the laptop.")
    return "\n".join(lines)


async def _ensure_session(client: JoiClient, session_id: str) -> None:
    if session_id in _ensured_sessions:
        return
    await client.ensure_session(session_id)
    _ensured_sessions.add(session_id)


# ── handlers ──────────────────────────────────────────────────────────────

@allowlisted
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "Hey. I'm here.\n\n"
        "Just talk to me and I'll answer with the same memory and context as on the laptop. "
        "Commands: /status, /new, /recent, /memory, /approvals, /help."
    )


@allowlisted
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "/status — is the Joi backend up?\n"
        "/new — start a fresh conversation thread\n"
        "/recent — show the last few messages\n"
        "/memory <query> — search what Joi remembers\n"
        "/approvals — list this thread's pending approvals (read-only)\n"
        "Anything else routes to Joi. Actions like sending email are staged for "
        "approval on the laptop, never run from here."
    )


@allowlisted
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    up = await _client().health()
    await update.effective_message.reply_text("Joi backend: online ✅" if up else "Joi backend: offline ❌")


@allowlisted
async def cmd_new(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    session_id = f"{_default_session_id(user_id)}:{int(time.time())}"
    _active_session[user_id] = session_id
    await update.effective_message.reply_text("Fresh thread started.")


@allowlisted
async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    parts = (message.text or "").split(maxsplit=1)
    query = parts[1].strip() if len(parts) > 1 else ""
    if not query:
        await message.reply_text("Usage: /memory <what to search for>")
        return
    try:
        items = await _client().search_memory(query, limit=5)
    except JoiApiError as exc:
        logger.warning("Memory search failed: %s", exc)
        await message.reply_text("I couldn't reach my memory right now — try again in a moment.")
        return
    if not items:
        await message.reply_text(f"I don't have anything in memory for “{query}”.")
        return
    lines = [f"What I remember about “{query}”:"]
    for item in items[:5]:
        text = str(item.get("text", "")).strip().replace("\n", " ")
        if len(text) > 180:
            text = text[:177] + "..."
        lines.append(f"• {text}")
    await message.reply_text("\n".join(lines))


@allowlisted
async def cmd_recent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session_id = _session_for(update.effective_user.id)
    try:
        messages = await _client().recent_messages(session_id, limit=6)
    except JoiApiError as exc:
        logger.warning("Recent-message lookup failed for session %s: %s", session_id, exc)
        await update.effective_message.reply_text(
            "I couldn't reach this thread's history right now — try again in a moment."
        )
        return
    if not messages:
        await update.effective_message.reply_text("No messages in this thread yet.")
        return
    lines = []
    for m in messages[-6:]:
        who = "You" if m.get("role") == "user" else "Joi"
        text = str(m.get("content", "")).strip().replace("\n", " ")
        if len(text) > 160:
            text = text[:157] + "..."
        lines.append(f"{who}: {text}")
    await update.effective_message.reply_text("\n".join(lines))


@allowlisted
async def cmd_approvals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session_id = _session_for(update.effective_user.id)
    try:
        approvals = await _client().pending_approvals(session_id)
    except JoiApiError as exc:
        logger.warning("Approval lookup failed for session %s: %s", session_id, exc)
        await update.effective_message.reply_text(
            "I couldn't reach the approval queue right now — try again in a moment."
        )
        return
    await update.effective_message.reply_text(format_pending_approvals(approvals))


@allowlisted
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    text = (message.text or "").strip()
    if not text:
        return
    session_id = _session_for(update.effective_user.id)
    client = _client()
    try:
        await _ensure_session(client, session_id)
        response = await client.chat(session_id, text)
    except JoiApiError as exc:
        logger.warning("Chat routing failed for session %s: %s", session_id, exc)
        await message.reply_text("Something's off between me and my backend right now — give me a moment and try again.")
        return

    reply = str(response.get("assistant_message", {}).get("content", "")).strip()
    reply = (reply or "…") + summarize_approvals(response.get("pending_approvals", []))
    await message.reply_text(reply)


# ── proactive delivery ──────────────────────────────────────────────────────

SendFn = Callable[[int, str], Awaitable[None]]


async def deliver_outbox_once(
    client: JoiClient,
    send: SendFn,
    allowed_ids: Iterable[int],
    *,
    limit: int = 10,
) -> int:
    """Claim queued proactive messages, deliver them, and ack the delivered ones.

    Testable core of the poll job: `send(chat_id, text)` does the actual Telegram
    call. A message is acked only if it reached every recipient without error, so
    a transient failure leaves it queued for the next poll (at-least-once).
    """
    recipients = [int(i) for i in allowed_ids]
    if not recipients:
        return 0
    try:
        messages = await client.claim_outbox(limit=limit)
    except JoiApiError as exc:
        logger.warning("Outbox claim failed: %s", exc)
        return 0

    delivered_ids: List[str] = []
    for message in messages:
        text = str(message.get("text", "")).strip()
        message_id = str(message.get("id", ""))
        if not text or not message_id:
            continue
        try:
            for chat_id in recipients:
                await send(chat_id, text)
        except Exception as exc:  # noqa: BLE001 - keep the poll alive; retry later
            logger.warning("Proactive delivery failed for %s: %s", message_id, exc)
            continue
        delivered_ids.append(message_id)

    if delivered_ids:
        try:
            await client.ack_outbox(delivered_ids)
        except JoiApiError as exc:
            # Backend will reissue unacked messages; a duplicate is better than a
            # silent drop, so we just log and move on.
            logger.warning("Outbox ack failed for %d message(s): %s", len(delivered_ids), exc)
    return len(delivered_ids)


async def _poll_outbox(context: ContextTypes.DEFAULT_TYPE) -> None:
    """JobQueue tick: deliver any queued proactive messages to allowlisted users."""

    async def send(chat_id: int, text: str) -> None:
        await context.bot.send_message(chat_id=chat_id, text=text)

    await deliver_outbox_once(_client(), send, settings.telegram_allowed_ids)


# ── entrypoint ─────────────────────────────────────────────────────────────

def _startup_selftest() -> None:
    """Log, at startup, exactly whether the bridge can authenticate to the backend.
    Turns the Joi Telegram window into a self-diagnosis — no message needed."""
    import asyncio

    async def check() -> None:
        token = settings.telegram_api_token
        client = _client()
        # The backend (launched by the same StartJoi.bat) can take 30-60s to load
        # its models, so wait for it rather than failing instantly on a cold start.
        healthy = False
        for _ in range(20):  # ~40s
            if await client.health():
                healthy = True
                break
            await asyncio.sleep(2)
        logger.info(
            "Self-test: base_url=%s | api_token=%s (%d chars) | backend_health=%s",
            settings.telegram_api_base_url,
            "set" if token else "MISSING",
            len(token),
            "ok" if healthy else "unreachable after 40s",
        )
        if not healthy:
            logger.warning(
                "Self-test: backend not reachable yet — it may still be starting. "
                "Chat will work once the API window says 'Application startup complete'."
            )
            return
        try:
            await client.ensure_session("telegram:selftest")
            logger.info("Self-test: AUTH OK — backend accepted the token. Chat should work.")
        except JoiApiError as exc:
            logger.warning("Self-test: BACKEND CALL FAILED — %s", exc)
            logger.warning(
                "Self-test hint: a 401 means the bridge's token != the backend's token "
                "(launch both from ONE StartJoi.bat, or set a fixed JOI_API_TOKEN in .env)."
            )

    try:
        asyncio.run(check())
    except Exception as exc:  # never block startup on the self-test
        logger.warning("Self-test could not run: %s", exc)


BOT_COMMANDS = [
    BotCommand("start", "What I can do"),
    BotCommand("help", "Show commands"),
    BotCommand("status", "Is the Joi backend up?"),
    BotCommand("new", "Start a fresh conversation thread"),
    BotCommand("recent", "Show the last few messages"),
    BotCommand("memory", "Search what Joi remembers"),
    BotCommand("approvals", "List pending approvals (read-only)"),
]


async def _post_init(app: Application) -> None:
    """Publish the command list to Telegram so the "/" menu autocompletes."""
    await app.bot.set_my_commands(BOT_COMMANDS)


def build_application() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).post_init(_post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(CommandHandler("recent", cmd_recent))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("approvals", cmd_approvals))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    if settings.telegram_proactive_enabled:
        if app.job_queue is None:
            logger.warning(
                "Proactive delivery is enabled but the JobQueue is unavailable "
                "(install python-telegram-bot[job-queue]) — messages will queue "
                "on the backend but won't be delivered."
            )
        else:
            interval = max(15, int(settings.telegram_outbox_poll_seconds))
            app.job_queue.run_repeating(_poll_outbox, interval=interval, first=interval, name="joi_outbox_poll")
            logger.info("Proactive delivery enabled — polling the outbox every %ds", interval)

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    # httpx logs each request URL at INFO — for Telegram that URL embeds the bot
    # token. Quiet it so the token never lands in the console/screenshots.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if not settings.telegram_bot_token:
        # Not an error — the bridge is simply disabled until configured. This lets
        # StartJoi.bat launch it unconditionally without a noisy failure.
        logger.info("TELEGRAM_BOT_TOKEN not set — Telegram bridge disabled. Add it to .env to enable.")
        return
    if not settings.telegram_allowed_ids:
        logger.warning("TELEGRAM_ALLOWED_USER_IDS is empty — the bot will reject everyone.")
    logger.info("Starting Joi Telegram bridge (allowlisted users: %d)", len(settings.telegram_allowed_ids))
    _startup_selftest()
    build_application().run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

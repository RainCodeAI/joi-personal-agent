# Telegram Bot Integration Plan

## Objective

Add Telegram as a remote chat and task-direction surface for Joi while keeping the Joi PC as the brain.

The Telegram bot should let the user message Joi from a phone while away from the laptop. The bot should route messages into the existing FastAPI `/api/v2/chat` flow so memory, profile context, approvals, tool proposals, and conversation behavior stay centralized.

The first version should be conservative:

- outbound long-polling from the Joi PC to Telegram
- no public Joi API exposure
- allowlisted Telegram user IDs only
- chat and read-only task direction first
- approval-required actions can be queued, but local approval remains the default

## Target Architecture

```text
Telegram mobile app
        |
        v
Telegram Bot API
        |
        v
Local Telegram bridge process on Joi PC
        |
        v
Joi FastAPI backend on 127.0.0.1
        |
        v
/api/v2/sessions + /api/v2/chat
        |
        v
Existing Joi orchestrator, memory, tools, approvals, events
```

The bridge should not create a second agent pipeline. It should act as a client of the existing Joi API.

## Recommended First Version

Build a standalone Python bot process first. This keeps the work isolated and easier to test before deciding whether the tray/runtime should supervise it.

Suggested file layout:

```text
app/integrations/
  __init__.py
  telegram_bot.py
  telegram_client.py
```

Later, if the bot works well, move process supervision into the native tray launcher or FastAPI lifespan.

## Environment Variables

Add backend/runtime config fields:

```text
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_USER_IDS=
TELEGRAM_SESSION_PREFIX=telegram
TELEGRAM_API_BASE_URL=http://127.0.0.1:8000
TELEGRAM_JOI_API_TOKEN=
```

Notes:

- `TELEGRAM_BOT_TOKEN` comes from BotFather.
- `TELEGRAM_ALLOWED_USER_IDS` should be a comma-separated list of numeric Telegram user IDs.
- `TELEGRAM_JOI_API_TOKEN` can default to `JOI_API_TOKEN` if omitted.
- The Joi API should stay bound to localhost.

## Coding Tasks

### Phase 1 - Bot Skeleton

- Add `python-telegram-bot` or `aiogram` to `requirements.txt`.
- Add `app/integrations/__init__.py`.
- Add `app/integrations/telegram_bot.py` as an executable module.
- Load Telegram settings from `app.config.Settings`.
- Start the bot using long polling.
- Add `/start`, `/help`, and plain text message handlers.
- Reject messages from non-allowlisted Telegram user IDs.
- Log rejected access attempts without storing full message text.

Suggested run command:

```powershell
python -m app.integrations.telegram_bot
```

### Phase 2 - Joi API Client

- Add a small local API client wrapper.
- Implement `create_or_get_session(telegram_user_id)`.
- Use deterministic session IDs such as `telegram:<user_id>`.
- POST to `/api/v2/sessions` before first message.
- POST user text to `/api/v2/chat`.
- Include `X-Joi-Api-Token` when configured.
- Return `assistant_message.content` to Telegram.
- If the backend is down, reply with a short unavailable message.
- Set reasonable timeouts so Telegram handlers do not hang indefinitely.

### Phase 3 - Approval Awareness

- Inspect `pending_approvals` in `/api/v2/chat` responses.
- If approvals are returned, tell the user the action was staged and needs approval.
- Do not approve or execute write actions from Telegram in v1.
- Include the tool name and a short preview of arguments, with sensitive fields redacted where needed.

Example behavior:

```text
I staged an email draft, but it needs approval on the laptop before I send anything.
```

### Phase 4 - Basic Commands

Add a small command surface:

- `/status` checks `/health`.
- `/new` creates a new Telegram chat session.
- `/recent` returns the last few messages from the current Telegram session.
- `/memory <query>` searches `/api/v2/memory/search`.
- `/approvals` lists pending approvals for the Telegram session, read-only.

Keep commands boring and explicit. Avoid natural-language shortcuts for sensitive actions until the tool platform is stronger.

### Phase 5 - Tests

Add focused tests for:

- unauthorized Telegram user rejection
- allowed user message routing
- session ID mapping
- backend unavailable handling
- pending approval response formatting
- no remote approval execution in v1

Mock Telegram and HTTP calls. Do not require a real bot token in tests.

### Phase 6 - Runtime Integration

After the standalone process is stable:

- Add `StartJoiTelegram.bat` for manual launch.
- Optionally add tray controls to start/stop the bot.
- Optionally add a runtime health indicator for Telegram connectivity.
- Decide whether `StartJoiNative.bat` should start the bot automatically.
- Add diagnostics fields for Telegram enabled/running/auth status without exposing the bot token.

## Manual Tasks For Rain

### BotFather Setup

- Open Telegram.
- Message `@BotFather`.
- Run `/newbot`.
- Choose a display name, for example `Joi`.
- Choose a unique bot username ending in `bot`.
- Save the bot token somewhere private.
- Do not paste the token into chat logs, screenshots, GitHub, or docs.

### Get Your Telegram User ID

Use one of these methods:

- Message `@userinfobot` and copy the numeric ID.
- Or temporarily run the bot in debug mode and let it print the sender ID from your first message.

Add only your numeric Telegram user ID to `TELEGRAM_ALLOWED_USER_IDS`.

### Local `.env` Setup

Add values to the local `.env` file:

```text
TELEGRAM_BOT_TOKEN=replace-with-botfather-token
TELEGRAM_ALLOWED_USER_IDS=123456789
TELEGRAM_API_BASE_URL=http://127.0.0.1:8000
```

Make sure `JOI_API_TOKEN` is already set when running Joi. If the Telegram bridge uses a separate variable, add:

```text
TELEGRAM_JOI_API_TOKEN=same-token-as-JOI_API_TOKEN
```

### First Manual Smoke Test

- Start Joi backend normally.
- Start the Telegram bot process.
- Send `/start` to the bot from your phone.
- Send a basic message like `Hey Joi, can you hear me from Telegram?`
- Confirm the reply comes back in Telegram.
- Open the Joi web UI and confirm the Telegram session appears in history or messages.
- Ask something memory-related and confirm it uses the same Joi memory context.

### Security Smoke Test

- Temporarily message the bot from a different Telegram account if available.
- Confirm the bot rejects the message.
- Confirm no unauthorized message is sent into Joi memory.
- Confirm the bot does not expose `JOI_API_TOKEN`, Telegram token, stack traces, or local file paths in Telegram replies.

### Task/Approval Smoke Test

- Ask Joi through Telegram to draft or send an email with complete details.
- Confirm Joi creates a pending approval rather than sending directly.
- Confirm the Telegram reply says approval is needed on the laptop.
- Approve or deny from the local Joi UI.
- Confirm audit/approval behavior remains local.

## Future Enhancements

### Remote Approval Mode

Only add this after v1 is stable.

Requirements:

- explicit setting to enable remote approvals
- allowlist remains mandatory
- approval messages show exact action previews
- destructive/local desktop actions remain blocked remotely
- each approval button expires quickly
- approval decisions are audited with `client_surface="telegram"`

### Proactive Telegram Delivery

Later, the bot could subscribe to Joi initiative or event-bus events and send selected messages to Telegram:

- daily greeting while away
- important reminder
- calendar heads-up
- queued context commentary that is safe for remote delivery

This needs a delivery policy so Telegram does not become noisy.

### Attachments And Voice

Later additions:

- Telegram voice messages routed through `/api/v2/media/transcribe`
- Telegram image attachments routed as chat attachments
- selected file uploads for local memory ingestion

Keep raw media retention explicit and consistent with Joi's privacy settings.

## Guardrails

- Do not expose Joi's FastAPI port to the internet for v1.
- Do not put Telegram token or API token in the frontend bundle.
- Do not allow arbitrary shell, filesystem, mouse, keyboard, or desktop actions from Telegram.
- Do not allow Telegram users outside the allowlist.
- Do not silently execute email/calendar writes.
- Do not duplicate the agent pipeline inside the bot.
- Do not store full unauthorized messages.

## Suggested Definition Of Done For V1

- The bot starts from a documented command.
- Only the allowlisted Telegram user can talk to Joi.
- Telegram messages create/reuse a stable Joi session.
- Replies come from the existing `/api/v2/chat` backend.
- Pending approvals are reported but not remotely executed.
- Backend-down and unauthorized cases fail cleanly.
- Tests cover routing, authorization, and approval formatting.

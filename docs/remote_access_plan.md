# Remote Access Plan

## Objective

Make Joi reachable when the user is away from the laptop while keeping the Joi PC as the trusted brain.

Remote access should be a set of controlled surfaces that route into the existing FastAPI backend, memory, approvals, and event system. Telegram is the first target, with a phone-friendly web/PWA surface possible later.

## Current Fit

What exists:

- FastAPI `/api/v2/chat` session contract.
- Token-protected local API.
- Session and message persistence.
- Approval queue for sensitive tool proposals.
- Realtime event bus that can later feed remote notifications.
- Telegram long-polling bridge launched alongside Joi when configured.
- Allowlisted Telegram identities with stable Joi sessions.
- `/status`, `/new`, `/recent`, `/memory`, and read-only `/approvals` commands.
- Mocked authorization, routing, redaction, failure, and approval-safety coverage.

Main gaps:

- No remote delivery policy for proactive messages.
- No shared remote-surface identity/audit abstraction yet.
- No Telegram voice-note or image-attachment routing yet.

## Coding Tasks

### Phase 1 - Telegram V1

Status: implemented; real-device smoke testing remains a manual validation item.

- Implement the plan in `docs/telegram_bot_plan.md`.
- Add a local long-polling Telegram bridge process.
- Restrict access to `TELEGRAM_ALLOWED_USER_IDS`.
- Route text messages into `/api/v2/chat`.
- Report pending approvals without executing them remotely.
- Add `/status`, `/new`, `/recent`, `/memory`, and `/approvals` commands.

### Phase 2 - Remote Surface Abstraction

- Add a small `app/remote/` package for shared remote-surface logic.
- Define remote identity fields: provider, provider user id, display name, session id.
- Normalize remote messages into a common internal shape.
- Add remote audit records for message ingress, rejected senders, and delivery errors.
- Keep full unauthorized message bodies out of logs.

### Phase 3 - Proactive Delivery

- Subscribe to selected event-bus or initiative events.
- Add a delivery policy for remote notifications.
- Only deliver events marked safe for remote surfaces.
- Respect quiet hours, DND, focus mode, daily caps, and category settings.
- Add an explicit setting for remote proactive delivery.

### Phase 4 - Phone Web/PWA

- Evaluate whether the existing Next.js UI can expose a phone-friendly remote route.
- Keep API access behind authentication.
- Avoid exposing the local backend directly to the internet in the first version.
- Consider a future relay only after local Telegram is stable.

## Manual Tasks

- Create and configure the Telegram bot with BotFather.
- Add the bot token and allowlisted user IDs to local `.env`.
- Confirm the bot only responds to the intended Telegram account.
- Test from phone while the laptop is awake and Joi is running.
- Test laptop sleep/off behavior so limitations are clear.
- Decide whether remote proactive messages should be enabled by default or opt-in.

## Security Guardrails

- Do not expose FastAPI directly to the public internet in v1.
- Do not put bot tokens in Git, docs, screenshots, or frontend bundles.
- Do not allow remote arbitrary desktop, shell, mouse, or keyboard control.
- Keep local approval as the default for write and destructive actions.
- Add remote approvals only after exact previews, expiry, audit, and allowlist are reliable.

## Definition Of Done

- Joi can be messaged remotely through Telegram.
- Only the allowlisted user can access the bot.
- Messages use Joi's existing memory and chat pipeline.
- Approval-required actions are staged but not remotely executed.
- Backend-down, unauthorized, and timeout cases fail cleanly.
- Remote access can be started and stopped deliberately.

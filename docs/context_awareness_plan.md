# Context Awareness Plan

## Objective

Give Joi a controlled understanding of the user's current context without turning the app into passive surveillance.

Screen, camera, calendar, active app, hardware, and remote surfaces should publish normalized context events. Joi should only use those events after policy, confidence, sensitivity, expiry, and relevance checks.

## Current Fit

What exists:

- Context event service and persisted short event buffer.
- Screen capture attachment path with manual consent.
- Camera perception provider and local MediaPipe assets.
- Browser presence and initiative activity events.
- Settings for context commentary.
- Event bus and initiative gate.

Main gaps:

- Context sources are still uneven.
- Active app/window metadata is not fully integrated.
- Calendar and connector context are not normalized into context events.
- Relevance scoring needs more real-world tuning.
- Context is not yet a cohesive "world model."

## Coding Tasks

### Phase 1 - Event Schema Review

- Audit existing context event fields.
- Ensure every event has source, kind, category, confidence, sensitivity, observed time, expiry, session, and sanitized payload.
- Add schema tests.
- Add redaction tests for payloads.

### Phase 2 - Source Normalization

- Normalize these sources:
  - browser presence
  - manual screen capture
  - camera presence/expression signals
  - calendar upcoming events
  - Telegram/remote activity
  - hardware node presence
  - active app/window metadata when available
- Add source-specific dedupe keys.
- Add TTL defaults per source.

### Phase 3 - Context Snapshot

- Add an API endpoint that summarizes current context.
- Include only non-expired, policy-allowed events.
- Group by category and source.
- Provide a compact prompt-ready context block.
- Avoid raw image/audio or sensitive text unless explicitly attached by the user.

### Phase 4 - Relevance And Commentary Gate

- Score events for novelty, reliability, usefulness, and interruption suitability.
- Keep appearance and inferred emotion commentary off by default.
- Queue commentary until a natural pause.
- Add user feedback handling into future scoring.

### Phase 5 - UI And Diagnostics

- Add a context dashboard in diagnostics or settings.
- Show accepted, suppressed, expired, queued, and emitted events.
- Show why an event was suppressed.
- Add controls for category allow/deny and sensitivity behavior.

## Manual Tasks

- Enable and disable context commentary.
- Trigger screen capture and confirm it becomes a context event.
- Test camera presence/away/return events.
- Test calendar-related context once connected.
- Mark commentary useful/wrong/too much/never comment.
- Restart Joi and confirm persisted context/feedback behaves correctly.

## Privacy Guardrails

- Manual screen capture only until a stronger policy exists.
- No continuous desktop capture in this phase.
- No raw camera frames sent to the backend for routine presence.
- Redact OCR, window titles, and payloads before prompt or persistence.
- Expire context quickly unless explicitly saved as memory.

## Definition Of Done

- Major context sources publish normalized events.
- The current context endpoint is policy-filtered and prompt-ready.
- Commentary decisions are explainable.
- User feedback affects future delivery.
- Sensitive raw media is not retained.

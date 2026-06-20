# Joi Always-On Companion Upgrade Plan

## Objective

Move Joi from a capable local companion app into an always-available desktop presence that can:

- understand explicitly permitted desktop and camera context
- hold low-friction spoken conversations with interruption
- comment occasionally when something genuinely relevant happens
- use connected apps and local computer tools to complete reviewed tasks
- continue operating safely when the main chat window is hidden

The existing architecture should be extended, not replaced. Joi already has useful foundations in FastAPI, Next.js, the native tray/window shell, SSE events, media-session state, browser perception, initiative policy, approvals, memory, user-model synthesis, desktop actions, and MQTT hardware state.

## Current State by Lane

### 1. Native and always-on runtime

Status: **foundation present; not yet dependable as an unattended companion**

What exists:

- Tray-managed FastAPI and Next.js processes.
- Pywebview native window shell.
- Global open-window and push-to-talk hotkeys.
- Start-minimized, always-on-top, window-state persistence, and process cleanup.
- Runtime diagnostics and health checks.
- Background initiative scheduler.

What is missing:

- Reliable packaged production build from a non-OneDrive workspace.
- Launch-on-login installation and removal.
- A real show/hide window contract instead of starting or killing a separate window process.
- Service watchdog/restart policy and visible degraded-state notification.
- Single-instance enforcement.
- Background delivery when the frontend is hidden: native notification, optional speech, and action entry point.
- Persistent media/event state across backend restarts.

### 2. Camera awareness

Status: **useful local prototype; only active inside the mounted chat UI**

What exists:

- Browser-side MediaPipe face landmarks and blendshapes at roughly 4 FPS.
- Local signals for presence, return, looking away, leaning, smile, stress, surprise, and neutral expression.
- Signals affect avatar expression and feed return/away state into initiative.
- Camera master switch and retention policy.
- Explicit snapshot capture and backend image description.
- Snapshot descriptions can be retained without storing the image.

What is missing:

- Perception does not run when chat is closed, hidden, suspended, or not mounted.
- MediaPipe model and WASM assets are loaded from external CDNs, so the path is not fully local/offline.
- Expression labels are rough heuristics and should not be treated as emotional truth.
- There is no event quality layer for confidence, duration, deduplication, or “safe to comment” decisions.
- Snapshot analysis uses a basic BLIP captioner and is not automatically supplied as conversational context.
- No object, gesture, hand, posture, activity, or multi-person event model.
- No camera indicator in the native tray.

### 3. Desktop/screen awareness

Status: **not implemented**

What exists:

- A narrow desktop action broker.
- Browser tab visibility and input-idle tracking.
- Manual image-analysis infrastructure that can be reused for screenshots.
- A perception privacy-policy pattern that can be extended.

What is missing:

- One-shot screenshot capture.
- User-selected window or region capture.
- Active-window/application metadata.
- OCR and UI-element extraction.
- Screen-change detection.
- Rules for when Joi may inspect, summarize, comment, or remember screen context.
- Redaction for password fields, notifications, private windows, and excluded applications.

This is the largest functional gap compared with an Omi-style desktop companion.

### 4. Voice

Status: **working push-to-talk loop; not strong conversational voice mode**

What exists:

- Browser MediaRecorder capture.
- Click-to-record and hold `Ctrl+Shift+Space`.
- Local/native hotkey bridge into the web recorder.
- Browser audio conversion and transcription.
- Whisper and Google STT paths.
- OpenAI, ElevenLabs, and pyttsx3 TTS paths.
- Spoken replies, auto-send, cancel recording, and interrupt playback.
- Media-session and avatar/lip-sync state.

What is missing:

- Streaming STT and partial transcripts.
- Voice activity detection in the active Next.js path.
- Automatic turn detection.
- Full-duplex barge-in while Joi is speaking.
- Low-latency streaming TTS; current synthesis produces a complete audio data URL first.
- Durable audio session state and recovery.
- Local high-quality TTS as a first-class supported path.
- Wake word and passive listening policy.
- Native microphone capture independent of the visible browser component.
- Acoustic echo cancellation and explicit speaker/microphone device selection.

### 5. App connections and task execution

Status: **approval infrastructure exists; integrations are prototype-grade**

What exists:

- Google OAuth for Gmail and Calendar.
- Gmail thread listing/summarization and email sending.
- Calendar event reads and writes.
- Approval queue and UI.
- Tool and desktop-action audit records.
- Local file ingestion/search foundations.
- Desktop `open_url` and notification actions.

What is missing or unsafe:

- Tool selection is based on keyword checks rather than typed model tool calls.
- Email and calendar write arguments are currently demo/mock extracted.
- Unauthenticated paths can return fake “sent” or “created” success results.
- Calendar date parsing falls back to a fabricated time instead of failing safely.
- Gmail uses a broad modify scope even for read operations.
- Calendar uses a write-capable scope for all access.
- Approval state is in-memory and disappears on restart.
- No draft-first workflow for email/calendar.
- No connector status/revoke surface in the primary Next.js settings UI.
- No Slack, Discord, Notion, Obsidian, browser, or task-manager connector.
- Desktop broker supports only URL opening and notifications.

These gaps should be fixed before adding many more connectors.

### 6. Initiative and commentary

Status: **strong policy gate and scheduler; weak context selection and delivery**

What exists:

- Daily limits, quiet hours, focus mode, DND, spacing, expiry, and media-state suppression.
- Scheduled greeting, return, late-night, silence, and memory follow-up candidates.
- Browser presence feeds absence/return state.
- SSE delivery and optional spoken initiative while the page is visible.
- User-model and memory foundations.

What is missing:

- Initiative is mostly timer/template driven.
- Calendar, screen, camera, connected-app, and active-task context are not part of the quality decision.
- No relevance/confidence score or “do not comment on this” category policy.
- Hidden-window initiative does not reliably become a native notification or spoken line.
- No acknowledgement/feedback loop to learn which comments were useful or annoying.
- No queue that waits for an appropriate interruption point.

### 7. Hardware and ambient presence

Status: **PC-side contract and MQTT output exist; sensory input is incomplete**

What exists:

- Disabled-by-default MQTT bridge.
- Canonical Joi states and LED output contract.
- Reconnect and current-state replay.
- Node heartbeat diagnostics.
- Presence telemetry contract.

What is missing:

- The bridge currently subscribes only to heartbeat telemetry.
- Presence, distance, health, and availability payloads are not parsed into realtime or initiative events.
- No completed ESP32 firmware is present in this repository.
- No multi-node registry or stale-node expiry.

## Target Architecture

```text
Native Runtime Supervisor
  tray, startup, single instance, watchdog, notifications
  native mic and screen/camera permission indicators
              |
              v
Local Context Event Bus
  normalized events with confidence, sensitivity, expiry, and source
              |
      +-------+--------+----------------+
      |                |                |
      v                v                v
 Perception       Voice Session     Connectors/Tools
 camera events    streaming STT     Gmail/Calendar
 screen events    turn detection    local desktop broker
 snapshots/OCR    streaming TTS     notes/tasks/apps
      |                |                |
      +-------+--------+----------------+
              |
              v
 Context and Initiative Coordinator
  relevance scoring
  privacy policy
  interruption policy
  memory policy
  approval policy
              |
       +------+------+
       |             |
       v             v
 Conversation     Action Execution
 avatar/voice     preview -> approve -> execute -> audit
```

The important new boundary is a normalized **context event**. Camera, screen, browser activity, calendar, hardware, and voice should not directly trigger personality behavior. They should publish structured observations to one coordinator.

Suggested envelope:

```json
{
  "event": "context.observed",
  "source": "screen",
  "kind": "active_application_changed",
  "confidence": 0.98,
  "sensitivity": "private",
  "observed_at": "2026-06-18T20:00:00Z",
  "expires_at": "2026-06-18T20:05:00Z",
  "session_id": "default",
  "payload": {
    "application": "Visual Studio Code",
    "window_title": "personal-agent"
  }
}
```

## Delivery Plan

### Phase A — Reliability and truthful tools

Priority: **first**

Goal: make the current runtime safe to leave running and remove misleading task behavior.

Status as of 2026-06-18: **implemented in source; packaged-build and long-duration soak QA remain**

Work:

- Complete the packaged build outside OneDrive.
- Add single-instance locking and show/hide/focus commands.
- Add launch-on-login setup and removal.
- Add process watchdog with bounded restart attempts.
- Persist approval requests and media-session state.
- Replace mock success responses with explicit `not_authenticated` or `invalid_request` failures.
- Remove fabricated email recipients, subjects, event titles, and dates.
- Split connector scopes into read-only and write authorization where providers allow it.
- Add connector status, reconnect, and revoke controls.
- Add native delivery for initiative events while the window is hidden.

Exit criteria:

- Joi can run for a full day, recover from one child-process failure, and never report a task completed when it was not.

Implementation update:

- Removed fabricated email recipients/content and calendar titles/times from the keyword tool path.
- Removed fake unauthenticated “sent” and “created” success responses.
- Invalid calendar dates now fail instead of silently substituting a future time.
- Gmail and Calendar expose explicit read/write scope sets.
- Added local connector status and confirmed disconnect controls in the API and Next.js settings.
- Approval requests and media-session state now survive backend restarts through atomic JSON persistence.
- Scheduled initiative events can produce native notifications when launched by the desktop runtime.
- Added tray/window localhost control channels for single-instance focus and show/hide/quit behavior.
- Added a bounded child-process watchdog: three restart attempts per process within five minutes.
- Added install/remove launch-on-login scripts.
- Remaining gates:
  - rebuild the packaged application outside the OneDrive workspace
  - run a full-day soak test with deliberate API/frontend crashes
  - manually verify Windows startup shortcut, hidden-window notification delivery, and connector OAuth/revocation

### Phase B — Strong voice mode

Priority: **highest user-facing upgrade**

Goal: make speaking with Joi feel faster and more natural than typing.

Status as of 2026-06-20: **closeout implemented; device QA remains**

Work:

- Introduce a dedicated voice-session state machine:
  `idle -> listening -> speech_detected -> transcribing -> thinking -> speaking`.
- Add browser AudioWorklet capture with local VAD.
- Stream audio chunks to a WebSocket endpoint.
- Emit partial and final transcript events.
- Start response generation from finalized turns without waiting for file conversion.
- Stream TTS audio chunks and viseme timing.
- Implement true barge-in: detected speech cancels generation/playback and starts the next turn.
- Add device selection, echo-cancellation controls, latency metrics, and fallback diagnostics.
- Support three explicit modes:
  - push-to-talk
  - conversation mode while the Joi window is open
  - optional wake-word mode later

Recommended local stack evaluation:

- STT: faster-whisper or whisper.cpp for practical local streaming.
- VAD: Silero VAD or WebRTC VAD.
- TTS: Piper for offline fallback; evaluate a higher-quality local engine separately.

Exit criteria:

- Median end-of-speech to first audible response is measured and acceptable.
- The user can interrupt Joi naturally without pressing Escape.

Foundation update:

- Added explicit persisted voice modes: `push_to_talk` and `conversation`.
- Added a voice turn-state contract covering listening, speech detection, transcription, thinking, speaking, interruption, and errors.
- Added local browser energy-based VAD to identify speech.
- Conversation mode now stops recording automatically after sustained silence or a bounded maximum turn.
- Conversation mode now re-arms capture between turns and uses browser echo cancellation while Joi is responding.
- Detected conversation-mode speech immediately stops local playback, aborts the active browser request, and ignores stale per-turn realtime events.
- Interrupted assistant replies are removed from persisted chat history and cannot create approvals or completion/avatar events after barge-in.
- Assistant turn IDs and interruption state are persisted with the media session so barge-in telemetry survives restart.
- Added speech-duration, end-of-speech-to-transcript, model, TTS-generation, first-audio, and estimated end-to-end latency metrics to the media session.
- Energy VAD now requires consecutive speech frames and uses a higher threshold during assistant playback to reduce speaker-feedback interruptions.
- Existing push-to-talk, transcription, auto-send, TTS, and interruption behavior remain intact.
- Next implementation slice:
  - replace energy-only VAD with a more robust local VAD
  - add streaming audio transport and partial transcripts
  - validate barge-in thresholds, echo handling, and latency readings with real microphone and speaker hardware

### Phase C — Screen understanding v1

Priority: **highest capability gap**

Goal: let Joi understand the desktop only when the user permits it.

Work:

- Extend perception policy with:
  - screen access disabled
  - ask each time
  - manual capture only
  - allow selected applications while active
- Add broker actions:
  - `screenshot_once`
  - `capture_window`
  - `get_active_window_metadata`
- Keep screenshots in memory only for the active analysis request.
- Add OCR and compact visual description.
- Add application/window allowlist and denylist.
- Add visible native indicator while capture is happening.
- Add “Look at this” hotkey and selected-region workflow.
- Feed the resulting structured description into the next conversation turn.
- Do not add continuous capture in this phase.

Exit criteria:

- “Joi, look at this” captures an approved screen/window, describes it, and can answer a follow-up without storing the image.

### Phase D — Context event layer and restrained commentary

Priority: **after voice and one-shot screen capture**

Goal: allow Joi to notice and comment without becoming noisy.

Work:

- Add the normalized context-event schema and persistent short event buffer.
- Normalize camera, browser idle, active-window, snapshot, calendar, hardware, and connector events.
- Add deduplication, confidence thresholds, sensitivity labels, and expiry.
- Add a commentary quality gate:
  - Is the observation reliable?
  - Is it new?
  - Is it useful or emotionally relevant?
  - Is interruption appropriate?
  - Has Joi commented on this category recently?
- Add category controls:
  - work/activity
  - wellbeing
  - appearance
  - entertainment
  - reminders
  - social/app activity
- Default appearance and inferred-emotion commentary to off.
- Queue non-urgent comments until a natural pause.
- Add feedback actions: useful, wrong, too much, never comment on this.
- Route accepted commentary through the existing initiative limit, DND, and quiet-hours policy.

Exit criteria:

- Joi can make a small number of accurate context-aware observations while respecting category and interruption settings.

### Phase E — Camera awareness v2

Priority: **after the context event gate**

Goal: improve visual presence without continuous server-side video.

Work:

- Bundle MediaPipe WASM and models locally.
- Move perception into an app-level service so it survives route changes.
- Add signal duration and confidence smoothing.
- Add optional hand/gesture and posture events.
- Use neutral terms such as `possible_tension` instead of asserting emotional state.
- Add explicit snapshot escalation when local events are insufficient.
- Add native tray camera indicator and one-click suspend.

Exit criteria:

- Camera awareness remains local for routine events and produces stable, low-noise context events across the app.

### Phase F — Real connector and task platform

Priority: **after truthful tool execution**

Goal: make app tasks reliable, typed, reviewable, and extensible.

Work:

- Define a central tool registry with JSON/Pydantic schemas.
- Let the model produce typed tool proposals rather than keyword-triggered demos.
- Separate operations into:
  - read
  - draft
  - write
  - destructive
- Require preview and approval for writes.
- Use idempotency keys and post-execution verification.
- Add draft-first Gmail and Calendar workflows.
- Feed read-only calendar context into initiative timing.
- Add connectors in this order:
  1. local notes/approved folders
  2. Gmail and Calendar hardening
  3. task manager
  4. Notion or Obsidian
  5. Slack/Discord if still useful
- Keep credentials in the vault and expose revoke/delete controls.

Exit criteria:

- Joi can read context, prepare a task, show the exact intended change, execute after approval, and verify the result.

### Phase G — Optional wake word and ambient mode

Priority: **last**

Goal: make Joi available without a keyboard while preserving an obvious privacy boundary.

Work:

- Evaluate a local wake-word engine.
- Run wake-word detection locally and discard non-trigger audio.
- Add hardware/tray listening indicator and audible activation cue.
- Add quiet hours, physical mute, and timeout.
- Keep wake-word mode off by default.
- Never enable continuous cloud audio streaming.

Exit criteria:

- Wake word can be disabled instantly, has clear state indicators, and does not retain non-trigger audio.

## Recommended Next Three Implementation Sprints

### Sprint 1 — Truthful always-on base

- Remove mock email/calendar successes and fabricated arguments.
- Persist approvals.
- Add hidden-window native notification delivery for initiative.
- Add single-instance and show/hide window commands.
- Add launch-on-login script.
- Add runtime soak-test checklist.

### Sprint 2 — Voice session v2 foundation

- Add VAD and explicit voice-session state machine.
- Add WebSocket audio transport and partial transcripts.
- Instrument end-of-speech, STT, model, TTS, and first-audio latency.
- Add playback cancellation from detected user speech.

### Sprint 3 — “Look at this”

- Add screen policy fields and settings UI.
- Implement one-shot screen/window capture in the desktop broker.
- Add OCR and image description.
- Attach the resulting context to chat.
- Add audit records and immediate deletion of raw captures.

These three sprints produce the largest practical change: Joi becomes reliable in the background, easier to speak with, and able to understand what the user explicitly shows her.

## Features to Defer

- Continuous desktop recording.
- Continuous server-side webcam frames.
- Autonomous clicking or arbitrary mouse/keyboard control.
- Shell command execution generated directly by the model.
- Appearance commentary by default.
- High-autonomy email/calendar writes.
- Wake word before voice interruption and privacy indicators are reliable.

## Measurements

Track these rather than judging the system only by demos:

- runtime uptime and child-process restart count
- voice end-of-speech to first audio
- transcription error rate
- barge-in cancellation latency
- perception false-event rate
- comments emitted, suppressed, dismissed, and marked useful
- tool proposal validation failures
- approval-to-execution success rate
- verified versus unverified external actions
- number of raw images/audio buffers retained after request completion

## Immediate Decision

The next major product milestone should be:

**Reliable background runtime + strong voice mode + explicit “look at this” desktop vision.**

That combination reaches the useful core of the Omi-style experience without prematurely enabling passive surveillance or broad computer control.

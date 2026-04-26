# Joi Master Presence Roadmap

## Purpose

This roadmap merges the software platform plan, the 3D avatar plan, and the ambient hardware plan into one dependency-aware direction.

The goal is to move Joi from an app you open into a presence that feels available, embodied, and continuous while still being reliable, private, and controllable.

## Source Tracks

- `Joi_v2_plan.md` defines the app platform: backend contracts, Next.js UI, realtime events, voice/media, memory, diagnostics, and reliability.
- `joi_avatar_3D_plan.md` defines the screen embodiment: projection chamber, VRM/GLB runtime, idle life, expression, gaze, lip-sync, and visual polish.
- `docs/ambient_presence_plan.md` defines the physical embodiment: ESP32 presence nodes, MQTT, sensors, LED/servo output, and future Pi artifact nodes.

Keep these tracks separate for implementation detail. Use this document to decide ordering, dependencies, and integration boundaries.

## Core Principle

Joi should feel like one AI presence expressed through several surfaces:

- the desktop app
- the realtime avatar
- voice
- local perception
- subtle physical nodes in the room

Hardware nodes and UI surfaces should not make independent personality decisions. Joi's PC runtime is the brain. Nodes are senses, signals, and ambient body language.

## Architecture

```text
Joi PC Runtime
  FastAPI backend
  memory and orchestration
  realtime event bus
  voice/media session
  avatar state
  privacy and permission policy
  MQTT hardware bridge

Joi Web Surface
  Next.js shell
  chat
  avatar projection chamber
  mini/floating presence mode
  diagnostics and settings

Avatar Presence
  idle state machine
  expression weights
  gaze and posture
  speech/lip-sync
  perception reactions

Ambient Presence Nodes
  ESP32 desk node
  LEDs
  ultrasonic presence sensing
  optional servo motion
  future Pi/e-paper artifact node
```

## Shared Event Vocabulary

Use structured events as the merge point between app, avatar, voice, perception, and hardware.

Initial event/state vocabulary:

- `joi_state_changed`
- `joi_idle`
- `joi_listening`
- `joi_thinking`
- `joi_speaking`
- `joi_sleeping`
- `voice_capture_started`
- `voice_capture_stopped`
- `user_present`
- `user_away`
- `user_returned`
- `user_leaned_in`
- `user_looked_away`
- `presence_confidence_changed`
- `ambient_node_online`
- `ambient_node_offline`
- `ambient_node_presence_changed`
- `initiative_allowed`
- `initiative_suppressed`

These should eventually flow through the realtime event layer and, where appropriate, through MQTT.

## Merged Delivery Order

### Phase 1 - Avatar Finish Pass

Goal: make the current on-screen embodiment feel stable and worth building around.

Scope:

- lock projection chamber framing
- finish material, lighting, bloom, scanline, and noise tuning
- keep GLB fallback available
- keep VRM audit documented
- refine expression presets around the actual VRM capabilities
- refine idle, gaze, breathing, and lip-sync smoothing

Why first:

The avatar is the visible emotional anchor. Hardware presence will feel disconnected if the primary embodiment still feels unstable.

### Phase 2 - Runtime Reliability

Goal: make the app safe to leave running for long sessions.

Scope:

- clean backend startup and health reporting
- clear frontend degraded/offline mode
- stable session bootstrap
- diagnostics for provider, media, vector, memory, and hardware bridge status
- avoid confusing "booting" states during avatar testing

Why second:

Always-on presence should not be built on a runtime that fails unclearly.

### Phase 3 - Mini Presence Mode

Goal: make Joi feel present without requiring the full chat screen.

Scope:

- docked/floating compact avatar window
- compact status and voice controls
- idle state visible outside full app mode
- optional launch-on-startup only after reliability is acceptable

Why third:

Floating mode is the bridge between "app" and "ambient presence" before physical hardware enters the room.

Status as of 2026-04-21:

- Mini presence mode is implemented and committed in `fc855dd4 Add mini presence mode`.
- The `Mini` toggle moves the avatar panel into a docked bottom-right compact panel through a body portal, with a `Full` return control.
- The current mini framing needs a follow-up pass: the attached screenshot from 2026-04-21 shows the full chamber view zoomed too far into Joi's face/head in the status panel.
- Next visual task: tune the full and compact avatar camera/framing constants so full mode shows a stable upper/full-body chamber view, while mini mode shows a readable bust or half-body presence without cropping the face.

Status as of 2026-04-22:

- Avatar framing regression is fixed and accepted against the 2026-04-22 visual review screenshot.
- Accepted VRM full framing constants: look-at `(0, 2.22, 0)`, camera position `(0, 2.24, 6.18)`, FOV `34`.
- Accepted VRM compact framing constants: look-at `(0, 2.14, 0)`, camera position `(0, 2.18, 5.35)`, FOV `32`.
- Camera selection is centralized in `getAvatarCameraConfig` so the renderer and camera rig use the same full/compact asset-specific presets.

### Phase 4 - Voice-First Access

Goal: reduce friction from typing to speaking.

Scope:

- push-to-talk hotkey
- browser or desktop mic capture path
- STT pipeline
- spoken response by default
- interrupt/stop speaking control
- quiet transcript display

Avoid early:

- passive listening
- wake word
- background microphone without a strong permission story

Status as of 2026-04-22:

- Push-to-talk hotkey path started on the existing browser voice capture flow.
- Current hotkey behavior: hold `Ctrl+Shift+Space` to start browser recording, release to stop and transcribe into the draft.
- Spoken replies now default to on in the voice UI, persist across reloads, and can be muted explicitly without changing the rest of the voice capture flow.
- Existing manual `Record voice` / `Stop recording` button flow remains available.
- Explicit `Stop speaking` control is available while speech is queued or playing; it clears active playback locally and records an interrupted media session.
- Transcript preview is intentionally quiet in the UI: low-contrast, compact, and clamped so spoken interaction stays primary.
- Phase 4 voice-first access is functionally complete enough to move into the runtime reliability gate before hardware work.

### Phase 5 - Idle Life State Machine

Goal: create life between messages.

Scope:

- states: `calm`, `observant`, `curious`, `resting`, `engaged`
- time-of-day modifiers
- listening/thinking/speaking transitions
- subtle avatar and hardware output changes

Rule:

Motion should stay restrained. Constant animation will cheapen the presence.

### Phase 6 - Situational Awareness

Goal: make Joi context-aware without becoming intrusive.

Scope:

- desk presence from browser perception and/or ESP32 ultrasonic sensing
- away/return events
- time spent working or inactive
- late-night and morning context
- privacy policy controls

Avoid early:

- frequent appearance comments
- unreliable emotion claims
- continuous raw webcam upload

### Phase 7 - Initiative Layer

Goal: let Joi occasionally speak first in a controlled way.

Scope:

- daily greeting
- return-after-absence check-in
- late-night check-in
- prolonged silence prompt
- memory-linked follow-up
- user-tunable daily limit

Initial rule:

- default max: 1 to 3 unsolicited moments per day
- quiet hours respected
- initiative suppressed during focus or do-not-disturb state

### Phase 8 - Ambient Hardware V1

Goal: add physical presence without building a generic smart home project.

Scope:

- ESP32 desk node
- local MQTT
- LED state output
- ultrasonic desk presence sensing
- node health and availability
- optional servo after LED/presence behavior feels right

Why after voice and reliability:

The hardware should extend a stable Joi runtime, not compensate for an unstable app.

## Dependency Rules

- Do not add launch-on-startup until degraded mode is clear.
- Do not add passive listening until push-to-talk is reliable and permissions are explicit.
- Do not add proactive initiative until quiet hours, limits, and suppression rules exist.
- Do not add servo motion until LED behavior and presence sensing are stable.
- Do not add multi-node hardware until one ESP32 node is boringly reliable.

## Immediate Next Work

Handoff as of the 2026-04-22 night session:

- Committed `fed1cc9d Fix avatar presence framing`.
- Committed `133e7bdc Add browser push-to-talk hotkey`.
- Committed `af652cbb Add stop speaking control`.
- Worktree was clean at handoff.
- No local Node server was left running.

Thursday 2026-04-23 code focus:

1. Finish the remaining Phase 4 voice polish: spoken response defaults and quieter transcript display.
2. Do a runtime reliability pass before hardware enters the loop:
   - backend health and startup state should be clear
   - frontend degraded/offline state should not look like avatar failure
   - diagnostics should show provider, media, memory/vector, realtime, and hardware-bridge readiness
3. Add a short avatar/voice tuning checklist for future visual QA.
4. Define the first hardware state contract in code before writing firmware:
   - allowed Joi state names
   - LED-only output states
   - feature flag / disabled-by-default behavior
   - diagnostics shape for bridge availability

Hardware window target:

- Friday 2026-04-24 through Sunday 2026-04-26 can move into Phase 8 if the Thursday code gates are done.
- Start hardware with LED-only state output.
- Do not start ultrasonic sensing until LED state output and node health are stable.
- Do not start servo motion until LED behavior feels restrained and reliable.

Must finish before touching hardware:

1. Runtime can be left running without confusing startup/offline failures.
2. The PC runtime owns the Joi state model; hardware nodes must not invent personality or behavior.
3. A feature flag keeps the hardware bridge disabled by default when no node is connected.
4. Diagnostics can report hardware bridge status without crashing when MQTT or hardware is unavailable.
5. The first hardware contract is LED-only and maps from shared Joi state events, not ad hoc firmware decisions.
6. Voice/presence UI should be stable enough that hardware is an extension of Joi, not a workaround for app instability.

Update from Thursday 2026-04-23:

- Committed `2195f7a3 Set spoken replies on by default`.
- Committed `53b6ba8e Quiet voice transcript display`.
- Phase 4 voice-first access is now closed enough to stop adding voice UI surface area for the moment.
- Runtime reliability pass completed:
  - `/health` and `/diagnostics/runtime` now expose readiness buckets for providers, storage, media, realtime, and hardware bridge.
  - Chat sidebar status now distinguishes degraded runtime state from full backend offline.
  - Diagnostics page now shows readiness, realtime transport details, and disabled-by-default hardware bridge state.
- `npm run typecheck` passed.
- `npm run build` passed.
- Python API tests were updated, but local `pytest` verification could not run in this shell because the available interpreter does not have a working project pytest environment.

Start here next:

1. Add the short avatar and voice QA checklist promised above:
   - full mode framing
   - mini mode framing
   - VRM fallback
   - GLB fallback
   - idle motion
   - speech and lip-sync
   - narrow viewport behavior
2. Define the first hardware state contract in code before firmware:
   - canonical Joi runtime state names
   - LED-only hardware output states
   - disabled-by-default bridge feature flag
   - diagnostics contract for bridge readiness
3. Only after that, begin the first ESP32 or MQTT implementation pass.

Update from Thursday 2026-04-23, late session:

- First hardware state contract is now defined in code before firmware work:
  - canonical states: `sleeping`, `idle`, `listening`, `thinking`, `speaking`, `user_returned`, `user_away`, `error`
  - LED-only output states are mapped on the PC side and exposed through a stable contract
  - bridge config is disabled by default and exposed through runtime settings
  - diagnostics now have a concrete bridge shape: connection state, node count, heartbeat, publish time, and bridge error
- New contract endpoint: `GET /api/v2/hardware/contract`
- Runtime transitions now emit `joi.state.changed` so the future MQTT bridge has one command signal to mirror.

Revised next start:

1. Add the short avatar and voice QA checklist.
2. Decide whether to expose the hardware contract in the diagnostics/settings UI any further, or leave the current API surface as the source of truth.
3. Begin the first MQTT bridge implementation pass:
   - publish the current hardware command to `joi/nodes/{node_id}/cmd/state`
   - keep the bridge disabled by default
   - report disconnected vs connected cleanly
4. Only after that, start the first ESP32 LED node bring-up.

Update from Thursday 2026-04-23, close-of-night session:

- First MQTT bridge implementation pass is complete and smoke tested.
- `aiomqtt>=2.0` added to requirements; `aiomqtt 2.5.1` installed.
- `app/hardware/mqtt_bridge.py` created: `MqttBridge` class with reconnect loop, birth/LWT to `joi/bridge/status`, publishes `joi/nodes/{node_id}/cmd/state` on every `joi.state.changed` event, subscribes to `joi/nodes/{node_id}/telemetry/heartbeat` for node tracking.
- `HardwareBridgeStore` extended with `set_connection_state()`, `record_publish()`, `record_heartbeat()`.
- `mqtt_node_id` config field added (default: `desk`); public runtime settings exposure is still a follow-up.
- `MqttBridge` wired into `app/api/state.py` singleton and FastAPI lifespan in `app/api/main.py`.
- Windows fix: `SelectorEventLoop` policy applied at module load in `main.py` (aiomqtt requires `add_reader`/`add_writer` which `ProactorEventLoop` does not implement). Smoke test uses `loop_factory=asyncio.SelectorEventLoop` directly to avoid the deprecated policy API.
- Smoke test `smoke_mqtt.py` passes 6/6: birth message, state command delivery, diagnostics timestamps, clean shutdown.
- Mosquitto 2.1.2 installed locally via winget for broker testing.
- Follow-up fix after review:
  - bridge enable/disable now applies live through runtime settings without requiring an API restart
  - current hardware command is replayed on MQTT connect/reconnect so the node does not wait for the next state transition

Start here next:

1. Start the first ESP32 LED node bring-up:
   - Flash ESP32 with firmware that subscribes to `joi/nodes/desk/cmd/state`
   - Parse the `led_state` field and drive LED output
   - Publish heartbeat to `joi/nodes/desk/telemetry/heartbeat` so node_count increments in diagnostics
   - Do not add ultrasonic sensing until LED state output and node health are stable

Update from Friday 2026-04-24:

- Added the pre-hardware avatar and voice QA checklist in `docs/avatar_voice_qa_checklist.md`.
- Locked the firmware-facing MQTT contract in `docs/hardware_firmware_contract.md`.
- `/api/v2/hardware/contract` now includes explicit node-to-PC payload contracts for heartbeat, health, and optional presence telemetry.
- Updated and reran `smoke_mqtt.py` against the current contract:
  - bridge starts live
  - bridge stops live
  - reconnect replays the current command
  - non-default `mqtt_node_id` publishes to the expected node topic

## Success Definition

Joi reaches the target direction when:

- she can be left running without confusing failures
- she feels visually alive when idle
- voice access is faster than typing for casual interaction
- she can acknowledge presence and absence with restraint
- physical nodes express her state subtly
- hardware events feed the same state model as the avatar and voice systems
- all sensing and memory behavior is explicit, private, and user-controllable

## Phase 7 Initiative Layer Start

Initial implementation direction:

- Added a dedicated initiative policy/gating layer rather than extending the older proactive action helper directly.
- Runtime settings now expose:
  - `initiative_enabled`
  - `initiative_daily_limit`
  - `initiative_quiet_hours_start`
  - `initiative_quiet_hours_end`
  - `initiative_focus_mode`
  - `initiative_do_not_disturb`
- The central gate suppresses initiative when disabled, over daily limit, inside quiet hours, during focus/DND, while mic/speech is active, too soon after the last initiative, or when a trigger already emitted today.
- `GET /api/v2/initiative/diagnostics` exposes policy state, daily count, remaining allowance, quiet-hours status, and last suppression.
- `POST /api/v2/initiative/daily-greeting?session_id=default&emit=false` evaluates the first low-risk trigger without emitting by default.
- `emit=true` records the assistant message, updates the initiative ledger, and publishes `initiative.emitted`.
- Future triggers should reuse this gate before adding scheduling:
  - return-after-absence
  - late-night check-in
  - prolonged silence prompt
  - memory-linked follow-up

Update:

- Added activity tracking to the initiative ledger.
- `/api/v2/chat` now records user activity before processing a message.
- Added `POST /api/v2/initiative/activity?state=active|away` so future presence, perception, or hardware hooks can mark active/away without knowing initiative internals.
- Added `POST /api/v2/initiative/return-after-absence?session_id=default&emit=false`.
- Return-after-absence currently requires at least 45 minutes away and still passes through the same central gate before it can emit.
- User activity clears the pending absence marker, preventing stale return prompts.

# Embodiment Plan

## Objective

Make Joi feel like one coherent presence across avatar, voice, tray, desktop window, notifications, and optional hardware nodes.

Embodiment should express state and attention. It should not become decoration disconnected from the runtime.

## Current Fit

What exists:

- Avatar renderer and assets.
- VRM/avatar planning docs.
- TTS and lip-sync path.
- Media session states for listening/thinking/speaking.
- Life state engine.
- Tray/window shell.
- MQTT hardware bridge foundation.
- Ambient presence hardware plan.

Main gaps:

- Avatar behavior is not fully tied to all runtime states.
- Voice and expression timing need real-device validation.
- Hardware node telemetry is incomplete.
- Native notification, tray, avatar, and hardware state need one shared state vocabulary.
- E-paper or secondary physical artifacts are future work.

## Coding Tasks

### Phase 1 - Unified State Vocabulary

- Define canonical Joi states:
  - sleeping
  - idle
  - listening
  - thinking
  - speaking
  - away
  - user_returned
  - focus
  - error
- Map media session, initiative, hardware, avatar, and tray states to this vocabulary.
- Add tests for state transitions.

### Phase 2 - Avatar State Integration

- Tie avatar expression, pose, gaze, and idle behavior to canonical state.
- Avoid over-animated idle loops.
- Add subtle return/absence behavior.
- Ensure text, controls, and avatar do not overlap in desktop/mobile layouts.
- Validate VRM loading and fallback assets.

### Phase 3 - Voice And Lip Sync

- Align TTS delivery style with avatar expression.
- Improve viseme timing after voice QA.
- Handle interrupted speech visually.
- Add diagnostics for TTS/lip-sync fallback.

### Phase 4 - Tray And Notifications

- Make tray state reflect listening, thinking, speaking, hidden, degraded, camera active, and capture active.
- Use native notifications for safe initiative events while hidden.
- Avoid notification spam through initiative policy.

### Phase 5 - Hardware Presence Nodes

- Continue from `docs/ambient_presence_plan.md`.
- Bring up ESP32 LED state node.
- Add MQTT availability and heartbeat.
- Add presence telemetry.
- Convert presence telemetry into context events.
- Add hardware diagnostics.

### Phase 6 - Future Artifacts

- Evaluate Raspberry Pi e-paper display for low-frequency ambient messages.
- Keep it passive and subtle.
- Do not move decision-making into hardware nodes.

## Manual Tasks

- Test avatar in browser and native shell.
- Test speaking, interruption, idle, and return visual states.
- Test tray indicators while recording, speaking, hidden, and degraded.
- Test native notifications while the window is hidden.
- Flash and validate ESP32 hardware node when ready.
- Confirm hardware behavior is subtle and not distracting.

## Design Guardrails

- State-driven over random animation.
- Subtle over flashy.
- Rare over constant.
- One coherent Joi presence across all surfaces.
- Hardware nodes should express state, not make independent decisions.

## Definition Of Done

- Avatar, voice, tray, notifications, and hardware use one state vocabulary.
- Runtime state changes are visible in appropriate surfaces.
- Interruptions and errors are expressed clearly.
- Hardware node v1 reflects Joi state and reports presence.
- Embodiment improves presence without adding noise.

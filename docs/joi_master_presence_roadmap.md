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

Recommended next sequence:

1. Commit the current avatar framing/audit/material pass once visually approved.
2. Add a short avatar tuning checklist for the next visual pass.
3. Create the ESP32 firmware skeleton only after hardware work resumes.
4. Add a backend MQTT bridge behind a feature flag.
5. Start with LED-only state output before ultrasonic sensing.

## Success Definition

Joi reaches the target direction when:

- she can be left running without confusing failures
- she feels visually alive when idle
- voice access is faster than typing for casual interaction
- she can acknowledge presence and absence with restraint
- physical nodes express her state subtly
- hardware events feed the same state model as the avatar and voice systems
- all sensing and memory behavior is explicit, private, and user-controllable

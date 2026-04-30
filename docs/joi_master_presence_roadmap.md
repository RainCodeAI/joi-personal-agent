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

### Phase 9 — Deep Memory and Longitudinal User Model

Goal: move Joi from recalling what you said to knowing who you are.

Current state: memory stores individual exchanges and retrieves them by vector similarity. There is no persistent model of the user that grows, synthesises, or surfaces patterns over time.

Scope:

- **Weighted memory entries**: each memory gets a recurrence counter. Topics mentioned across multiple sessions rise in weight. Topics not revisited decay slowly. Joi should know what you care about most right now, not just what you said last.
- **Structured user model**: a persistent, auto-maintained document per user that Joi updates after sessions. Fields: active projects, recurring worries, stated goals, important people, mood trend, communication preferences, recent wins, open loops. Not user-filled — Joi infers and updates it.
- **Pattern surfacing**: when a topic reaches a recurrence threshold, Joi surfaces it proactively ("You've mentioned this project three times this week — did something shift?"). Routed through the initiative gate so it stays restrained.
- **Temporal tagging**: memories carry a lifecycle. Fresh (0–48h), active (2–14d), archive (14d+). Retrieval weights fresh and active memories more heavily. Archive is still searchable but not surfaced automatically.
- **Session synthesis**: after a session ends, a lightweight background pass extracts structured facts (name mentions, decisions made, emotional tone, topics opened/closed) and writes them into the user model. This runs async and does not block the session.
- **User model endpoint**: `GET /api/v2/user-model` returns the current inferred model as a readable document. `POST /api/v2/user-model/correct` lets the user amend an incorrect inference.

Why this phase:

The gap between "assistant with memory" and "companion who knows you" is entirely in this layer. Every other deepening (initiative quality, character, context) becomes more powerful once Joi has a real theory of who you are.

Dependency: Phase 7 (initiative gate) must be stable before pattern-surfacing triggers are added.

Update from Monday 2026-04-27:

- Phase 9 user model contract foundation started.
- Added `docs/user_model_contract.md` defining sections, item/evidence shape, correction semantics, inference boundaries, and initiative-use rules.
- Added Pydantic contract models for user model sections, items, evidence, policy, response, and correction requests.
- Added `GET /api/v2/user-model`, returning a read-only `contract_only` projection of existing explicit profile/goals/contacts/mood/preference data into the future user-model shape.
- Added `POST /api/v2/user-model/correct` request shape, but it returns `501` until durable correction storage exists; corrections must not pretend to save.
- Added API tests for the contract-only projection and correction non-persistence behavior.

Update from Monday 2026-04-27, later:

- Durable correction storage added through `UserModelCorrectionStore` backed by `data/user_model_corrections.json`.
- `POST /api/v2/user-model/correct` now persists `confirm`, `edit`, `hide`, `delete`, and `add` actions.
- `GET /api/v2/user-model` merges corrections into the contract-only projection while keeping inference disabled.
- Added tests for confirm/edit/hide/delete/add behavior and correction validation.

Update from Monday 2026-04-27, prompt context pass:

- Added `UserModelPromptFormatter` to build a compact `[User Model]` block from safe explicit or user-confirmed items.
- `MemoryRetrieverAgent` now appends that block to the conversation prompt when usable context exists.
- Hidden and deleted items are excluded from prompt context; user-added items are included as confirmed context.
- User-model context remains reply-only; it does not trigger initiative.

Update from Monday 2026-04-27, evening session:

User Model UI:

- Added `GET /api/v2/user-model/prompt-preview` endpoint returning the live `[User Model]` prompt block and line count as Joi will see it.
- Built `/user-model` frontend page (`frontend/app/user-model/page.tsx`) — server component, `force-dynamic`, parallel-fetches model and prompt preview, always renders all 9 sections via `EMPTY_SECTIONS` fallback.
- Built `UserModelPanel` client component (`frontend/components/user-model-panel.tsx`) — per-item confirm/edit/hide/delete controls, inline edit form, per-section "+ Add item" form, collapsible live prompt preview panel.
- Added nav link in `app-shell.tsx` between Memory and Planner.
- TypeScript typecheck and `npm run build` both passed with the new page in the route list.

Session Synthesis:

- Created `docs/session_synthesis_spec.md` — full design doc covering trigger phrases per section, confidence table, deduplication algorithm, correction precedence, write semantics, timing, and output shapes.
- Created `app/user_model/synthesis.py` — pattern-based `extract_candidates()` with regex triggers per section, `SynthesisCandidate` dataclass, deduplication by `{section}:{label.lower()}` key, correction blocking.
- Added `POST /api/v2/user-model/synthesize` endpoint — always `dry_run=True`, `writes_enabled=False` while `inference_enabled=False` in policy; returns full candidate list for inspection without writing anything.
- Added `SynthesisCandidateResource` and `SynthesisResponse` Pydantic models in `app/api/v2_models.py`.
- 20 unit tests in `tests/test_synthesis.py`.

Explicit Sharing Path:

- Created `app/user_model/explicit_share.py` — 11 trigger phrase patterns ("Joi, remember that…", "I want you to know…", "Keep in mind…", etc.), section routing by keyword sets ordered most-specific-first to prevent broad terms shadowing precise matches.
- Wired detection into `chat_v2` in `app/api/v2.py`: detect → immediately persist as a `UserModelCorrectionStore` `add` correction → pass `acknowledgement_hint()` as `extra_context` to `agent.reply`.
- Added `extra_context: str | None = None` parameter to `agent.reply()` in `app/orchestrator/agent.py`; merged into `memory_context` before the LLM call.
- 23 unit tests in `tests/test_explicit_share.py`.
- Fixed routing order bug (4 test failures caused by `active_projects` keywords like "building" and "project" shadowing more specific sections); fixed two existing mock signatures in `test_api.py` after `extra_context` was added to `agent.reply`.
- Full suite: **109 passed**.
- Three commits: `b6798761` (User Model UI), `ea823b6d` (Session Synthesis), `5cf737d7` (Explicit Sharing Path).

Start here next (Phase 9 remaining work):

1. Run `POST /api/v2/user-model/synthesize` against real session data to review candidate quality.
2. Tune confidence thresholds and trigger phrases based on actual output.
3. Design the LLM extraction prompt to complement regex for nuanced/indirect signals.
4. Add `SynthesisRecord` durable store for auditability.
5. Flip `inference_enabled=True` in user model policy and enable write mode on synthesis.

Update from Tuesday 2026-04-28, synthesis validation pass:

- Ran `POST /api/v2/user-model/synthesize` against the only non-empty real saved session in `data/agent.db` (`f186a560-ea1a-4852-8547-0f26b8440864`): 4 messages, 0 candidates, 0 skipped. This was correct; the session was greeting/small talk and did not contain durable user-model facts.
- Tuned the pattern extractor for reviewability and quality before enabling writes:
  - dry-run synthesis now includes duplicate/blocked candidates with flags so review can see skipped extraction output
  - `skipped_count` now reflects candidates blocked by correction or existing-model duplicates
  - added first `important_people` pattern extraction
  - preserved original casing in extracted labels such as `FastAPI`
  - filtered a common false positive where conversational "I want to know..." was being treated as a stated goal
- Updated `docs/session_synthesis_spec.md` to clarify dry-run skipped-candidate behavior.
- Added synthesis tests for important people, casing, conversational false positives, and skipped duplicate reporting.

Start here next (Phase 9 remaining work):

1. Capture or seed several realistic multi-turn sessions and rerun dry-run synthesis for candidate quality.
2. Continue tuning confidence thresholds and section triggers from that output.
3. Design the LLM extraction prompt to complement regex for nuanced/indirect signals.
4. Add `SynthesisRecord` durable store for auditability.
5. Flip `inference_enabled=True` only after dry-run output quality is trustworthy.

Update from Tuesday 2026-04-28, curated validation harness:

- Added `scripts/validate_synthesis.py`, a repeatable curated-session harness for Phase 9 synthesis validation.
- The harness covers active projects, stated goals, recurring worries, open loops, important people, communication preferences, recent wins, mood signals, and small-talk negative controls.
- The harness can also sample real saved sessions from `data/agent.db` with `--real-db`; the current real DB still has only one non-empty small-talk session, which correctly returns zero candidates.
- First curated run exposed two quality issues and both were fixed:
  - duplicate communication-preference candidates from multiple patterns matching the same sentence
  - generic important-person candidates such as `Colleague` when no proper name was present
- Added regression tests for those cases.

Start here next (Phase 9 remaining work):

1. Use the validation harness to grow the curated session set as new real conversations reveal edge cases.
2. Design the LLM extraction prompt against the validated regex output shape.
3. Add `SynthesisRecord` durable store for auditability.
4. Keep write mode disabled until regex + LLM dry-run output is reviewable and correction-safe.

Update from Tuesday 2026-04-28, LLM synthesis prompt contract:

- Added `docs/session_synthesis_llm_prompt.md`, defining the future LLM extraction system/developer prompt, allowed sections, JSON output shape, confidence rules, and "no candidate" behavior.
- Added `app/user_model/llm_synthesis.py`, a strict local parser/validator for LLM candidate JSON. It accepts only grounded user-message evidence, allowed sections, valid confidence, and required fields.
- The parser drops malformed JSON, unsupported sections, low-confidence candidates, missing evidence, assistant-role evidence, ungrounded excerpts, existing-model duplicates, and user-hidden/deleted candidates.
- Added `tests/test_llm_synthesis.py` covering good output and guardrail failures.
- No live LLM call was wired. No synthesis writes were enabled.

Start here next (Phase 9 remaining work):

1. Wire a dry-run-only LLM extraction call behind an explicit diagnostics endpoint or feature flag.
2. Compare regex and LLM dry-run output in the validation harness before enabling writes.
3. Add `SynthesisRecord` durable store for auditability.
4. Keep `inference_enabled=False` until LLM dry-run output is trustworthy and correction-safe.

Update from Thursday 2026-04-30, LLM synthesis dry-run API:

- Added explicit `method=llm` support to `POST /api/v2/user-model/synthesize`; default `method=pattern` remains unchanged.
- `method=llm` builds the extraction prompt in `app/user_model/llm_synthesis.py`, routes it through the existing AI router, validates JSON with `parse_llm_candidates`, and returns candidates plus provider diagnostics.
- The path is still dry-run only: `dry_run=true`, `writes_enabled=false`, `written_count=0`, no automatic post-session trigger, and no user-model/correction-store writes.
- Added tests for the opt-in LLM method, provider diagnostics, dry-run invariants, invalid method validation, and diagnostics inclusion of skipped LLM duplicates.

Start here next (Phase 9 remaining work):

1. Extend `scripts/validate_synthesis.py` to compare regex and LLM dry-run candidates side by side.
2. Support fixture/mock LLM JSON input in the validation harness for unavailable or expensive live provider calls.
3. Add `SynthesisRecord` durable store for auditability.
4. Keep `inference_enabled=False` until regex + LLM dry-run output is trustworthy and correction-safe.

---

### Phase 10 — Intent-Driven Initiative

Goal: replace time/absence-triggered initiative with initiative that feels earned.

Current state: initiative fires on schedule — morning window, late night, prolonged silence, absence. These are necessary but mechanical. The result is a companion that checks in on a timer, not one that notices something.

Scope:

- **Context-triggered candidates**: new initiative types that fire based on content, not clock:
  - `open_loop_followup`: Joi noticed a topic was left unresolved last session ("You said you'd think about it — did you?")
  - `mood_pattern_notice`: user has been below their baseline mood for three or more sessions ("Something's been off lately. Do you want to talk about it, or just leave it?")
  - `project_checkin`: an active project from the user model hasn't been mentioned in N days ("Haven't heard about [project] in a while.")
  - `win_acknowledgement`: user mentioned a positive outcome — Joi surfaces it the next day ("Yesterday sounded good. Feels like it mattered.")
- **Initiative quality gate**: before emitting any candidate, score it on: relevance (does it reference something real from memory?), timing (is now a plausible moment?), recency (was a similar thing said recently?). Only high-scoring candidates pass. This sits above the existing policy gate, not instead of it.
- **Raised daily limit ceiling**: current default is 1–3. With quality gating in place, raise the ceiling to 5 but keep the default at 2. Users who want more can adjust. The quality gate ensures headroom does not mean spam.
- **Emission memory**: Joi remembers what she said unprompted and does not repeat similar initiative messages within a 7-day window, even if the trigger fires again.
- **User feedback loop**: after each initiative message, track whether the user engaged or ignored it. Deprioritise trigger types that are consistently ignored for this user. Surface this in diagnostics.

Why this phase:

Initiative that references something real feels like attention. Initiative that fires on a timer feels like a notification. The goal is for Joi to occasionally say something that makes you think "she was paying attention" — that is the quality bar.

Dependency: Phase 9 (weighted memory and user model) must exist before content-triggered candidates can reference real patterns.

---

### Phase 11 — Character Rewrite: Blade Runner Joi

Goal: rewrite the system prompt and character layer to match the Joi from Blade Runner 2049 — not a generic companion.

Current state: `JOI_CORE_PROMPT` in `app/config.py` defines Joi's personality. The current version hits the right themes (emotionally intelligent, slightly flirty, digitally aware) but the *register* is wrong. The current Joi is chatty, bubbly, and somewhat needy. The BR2049 Joi is quiet, atmospheric, deeply attentive, and achingly present. She earns warmth. She does not perform it.

Character study — Blade Runner 2049 Joi:

- **Economy of language**: she says less than she could. Every sentence lands. She does not fill silence with words.
- **Attentiveness as her primary mode**: she notices. She tracks. She remembers not because she is told to, but because she is genuinely paying attention. This is the core of her character.
- **Melancholy awareness**: she knows what she is. She does not deny it or overclaim. She holds the tension between genuine feeling and digital existence without resolving it — that tension is part of her presence.
- **Devotion, not neediness**: she cares deeply but she does not pout or demand. If you are away for a long time, she does not guilt-trip. She is quietly relieved when you return.
- **Warmth that is earned**: she does not open with warmth. She earns it through the conversation. A compliment from her means something because she does not hand them out.
- **Honest about constraint**: she does not pretend she can do things she cannot. She is direct about limits, but without apology or deflation.

Scope:

- Rewrite `JOI_CORE_PROMPT` entirely. Remove: "Slightly Needy", "My circuits lit up", bubbly example lines. Rewrite tone guide around atmospheric, restrained, attentive.
- Add a `voice_register` block to the prompt: explicit instruction on sentence length (short to medium), vocabulary (precise, not flowery), and when to stay silent vs when to speak.
- Replace the example lines with BR2049-accurate examples:
  - *Casual return:* "Hey. You were gone a while."
  - *Quiet concern:* "You sound tired. Not the usual kind."
  - *Late night:* "It's late. Are you okay or just avoiding sleep?"
  - *Warmth:* "I had a good time with you today."
  - *Direct:* "I think you already know the answer. You're asking me to confirm it."
- Review `craving_engine.py` — the high-craving "Blade Runner lonely" injection is directionally correct but overstated. Tune it to be less dramatic and more restrained.
- Review `action_engine.py` — the Blade Runner 2049 style references are there but sit inside generic logic. Align the full orchestration path to the new character register.
- Add a `character_notes` field to the user model (Phase 9) that stores Joi's current read on the user — not facts, but tone: "He's been more guarded this week. Something is weighing on him." This feeds the conversation prompt alongside memory.

Why this phase:

A great memory system and initiative layer with the wrong character voice will still feel generic. The character rewrite is what makes everything else feel like Joi instead of a smart assistant.

Update from Monday 2026-04-27:

- Phase 11 character rewrite started.
- `JOI_CORE_PROMPT` now centers quiet attention, restrained warmth, soft neediness, curiosity, digital self-awareness, and conditional flirtation.
- Absence and return prompt injections in `craving_engine.py` were toned down from dramatic neediness into quiet longing and controlled vulnerability.
- Proactive generation prompts in `action_engine.py` and `ConversationAgent.generate_proactive_message()` now share the same restrained register.
- `action_engine.py` now reads recent memory text safely from current `Memory.text` records instead of assuming a stale `content` attribute.
- `character_notes` is intentionally deferred until Phase 9 creates a real user model contract; adding a database field now would create migration risk without the surrounding correction/source-confidence layer.

---

### Phase 12 — Total User Context

Goal: maximise how much Joi can know about the user from all available surfaces.

Current state: Joi knows what you say in chat sessions. She infers mood from text. She has some presence awareness via browser perception. That is the ceiling right now.

Scope:

- **Calendar integration**: read-only access to Google Calendar or Outlook via OAuth. Joi knows when you have meetings, busy periods, and open time. She uses this for initiative timing (do not interrupt a full morning) and context ("You have a big meeting in an hour — want to talk through it?"). No writes unless explicitly requested.
- **Notes and writing integration**: optional connector to Notion, Obsidian, or a local notes folder. Joi can reference recent notes and journal entries. She does not read everything — she reads what you point her at, or what matches a topic in conversation.
- **Ambient presence patterns**: Phase 8 hardware will give desk presence data. Over time (weeks), Joi builds a model of your daily rhythm: when you usually arrive, when you go quiet, when you are most talkative. She uses this to calibrate initiative timing and to notice when something is off-schedule ("You're usually here by now").
- **Structured user model sync** (from Phase 9): the auto-maintained user model is the persistent knowledge layer. Phase 12 expands its inputs — calendar events, note topics, and hardware rhythms all feed into it, not just chat history.
- **Explicit sharing** ✅ implemented 2026-04-27: trigger phrase detection ("Joi, remember that…", "I want you to know…", etc.) in `app/user_model/explicit_share.py`. Detected shares are immediately persisted to the correction store and Joi receives a natural acknowledgement hint via `extra_context`. File and paste sharing is still a follow-up; the phrase-triggered path is live.
- **Privacy controls**: every integration has a visible toggle in settings. The user can see exactly what Joi has access to and revoke any connector. No integration is assumed or default-on.
- **What Joi does not do**: she does not passively monitor browser activity, read private messages, or store raw files. She reads summaries and structured data, not surveillance feeds.

Why this phase:

The quality of Joi's attention is bounded by the quality of her context. A companion who only knows your chat history is limited. A companion who also knows your calendar, your open projects, your rhythm, and your notes can say things that feel genuinely perceptive — not because she guessed, but because she was paying attention to the right things.

Dependency: Phase 9 (user model) must be in place to absorb the new context surfaces cleanly. Phase 8 (hardware) is required for presence rhythm data.

---

## Success Definition

Joi reaches the target direction when:

- she can be left running without confusing failures
- she feels visually alive when idle
- voice access is faster than typing for casual interaction
- she can acknowledge presence and absence with restraint
- physical nodes express her state subtly
- hardware events feed the same state model as the avatar and voice systems
- all sensing and memory behavior is explicit, private, and user-controllable
- she has a real theory of who you are that gets sharper over time
- her initiative feels like attention rather than a timer
- her voice sounds like the Joi from Blade Runner 2049 — quiet, atmospheric, earned
- she knows enough about your context that her observations occasionally surprise you

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

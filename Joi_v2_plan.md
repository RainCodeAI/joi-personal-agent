# Joi v2 Plan

## Objective
Joi v2 should move from an ambitious Streamlit prototype into a stable product platform with three clear properties:

1. A reliable backend contract that can support multiple clients.
2. A modern frontend in Next.js that handles chat, state, media, and presence cleanly.
3. A much stronger avatar stack so Joi feels like a live holographic companion instead of a themed chatbot UI.

This plan is intentionally ordered by dependency, not by novelty. The hologram and webcam work should happen after the backend and runtime are trustworthy enough to support them.

Related roadmap docs:

- `docs/joi_master_presence_roadmap.md` merges the v2 platform, avatar, voice, perception, initiative, and ambient hardware tracks.
- `joi_avatar_3D_plan.md` covers the realtime avatar embodiment track.
- `docs/ambient_presence_plan.md` covers ESP32/Pi physical presence nodes.

---

## Priority Ranking

### Critical
- Fix broken backend contracts and runtime errors before starting the frontend migration.
- Make FastAPI the real application boundary instead of letting Streamlit pages own business logic.
- Align the real chat execution path with the advertised router and fallback model behavior.
- Remove current "demo path" assumptions from tools, approvals, diagnostics, and chat responses.

### High
- Extract the frontend into Next.js while keeping Python as the orchestration and tools backend.
- Replace Streamlit-owned voice, image, and approval flows with API-driven flows.
- Build a reusable realtime transport layer for chat, TTS events, approvals, typing, and avatar state.
- Ship a first serious hologram renderer in the browser.

### Medium
- Add webcam presence and expression awareness in a privacy-safe way.
- Add event-driven perception so Joi reacts to presence, gaze, posture, and emotion without constantly sending raw video to a model.
- Improve lip-sync from heuristic timing toward real alignment or better viseme timing.

### Low
- Expand to richer desktop packaging once the web stack is stable.
- Add premium hologram effects, advanced idle behaviors, room awareness, and ambient intelligence layers.
- Add more cinematic interaction patterns after the platform is reliable.

---

## Guiding Rules For v2

### Rule 1: Do not rewrite the brain in Node
Keep Python for orchestration, memory, tools, routing, scheduling, TTS/STT adapters, and vision services. Move the UI to Next.js, not the full application.

### Rule 2: Make the API real before making the frontend beautiful
If the API contracts are weak, the Next.js app will become another tightly coupled client with the same problems Streamlit has today.

### Rule 3: Build "she can see me" as structured perception, not raw continuous surveillance
Most of the time Joi should react to events like "user present", "smiling", "leaning in", or "holding an object", not to nonstop raw webcam uploads.

### Rule 4: Hologram quality is animation quality plus rendering quality
The final effect comes from motion systems, responsiveness, lighting, timing, gaze, and micro-behaviors. Better shaders alone will not get there.

---

## Phase 0: Stabilize The Core
### Goal
Fix the current issues that would make any frontend migration fragile or misleading.

### Why this phase exists
Right now the product promise is ahead of the runtime reality in a few important places. v2 should start by closing those gaps.

### Sprint 0.1 - Contract Repair
#### Priority
Critical

#### Scope
- Fix `/chat` so it returns the actual structured response object.
- Add a real `/health` endpoint.
- Make diagnostics safe in SQL-only and safe-mode environments.
- Review all public FastAPI routes for response-model correctness.

#### Instructions
- Treat FastAPI responses as the source of truth for every future client.
- Remove stub behavior where it can break contract expectations.
- Add narrow tests around chat, health, diagnostics, and error payloads.

#### Exit criteria
- A web client can call chat, health, and diagnostics without special-case handling.
- Safe mode does not crash diagnostics.

### Sprint 0.2 - Runtime Truthfulness
#### Priority
Critical

#### Scope
- Route the main chat path through the actual multi-provider router or reduce the product claims until the implementation matches.
- Fix missing imports and broken code paths in tool execution.
- Fix legacy helper references like `self.conversation_agent`.
- Identify any other "README says yes, runtime says maybe" mismatches.

#### Instructions
- Decide whether `ConversationAgent` owns direct provider calls or the router owns them. Do not keep both stories alive.
- Make provider logs, fallback behavior, and selected model visible in a structured way.
- Audit every user-facing feature claim that depends on a fallback or safe-mode path.

#### Exit criteria
- The main conversation path matches the documented architecture.
- Tool execution paths do not fail on first use due to missing symbols.

### Sprint 0.3 - Boundary Cleanup
#### Priority
Critical

#### Scope
- Move business logic currently living in Streamlit pages behind backend services or API endpoints.
- Stop using UI-layer temp-file hacks as the normal product flow.
- Separate frontend state from backend state assumptions.

#### Instructions
- Streamlit pages should become thin callers, even before Next.js lands.
- Any logic that will be needed by Next.js should be extracted now rather than reimplemented later.
- Create a short inventory of what still lives in `Chat.py` that belongs in the backend.

#### Exit criteria
- The chat page is no longer the place where core orchestration rules live.

---

## Phase 1: Define The v2 Backend Surface
### Goal
Create a clean backend API that both Streamlit and Next.js could use during the migration window.

### Sprint 1.1 - Core API Surface
#### Priority
Critical

#### Scope
- Add endpoints for sessions, chat history, messages, approvals, avatar sync, and settings.
- Add a structured response shape for tool calls, pending approvals, emotions, and avatar cues.
- Define versioned response schemas.

#### Instructions
- Prefer explicit payloads over implicit session-state behavior.
- Include message IDs, session IDs, timestamps, source model/provider, and tool-call metadata.
- Keep this boring and predictable. Fancy can come later.

#### Suggested endpoints
- `POST /chat`
- `GET /sessions/{id}/messages`
- `POST /sessions`
- `GET /approvals`
- `POST /approvals/{id}/approve`
- `POST /approvals/{id}/deny`
- `POST /avatar/sync`
- `GET /settings`
- `PATCH /settings`

### Sprint 1.2 - Realtime Event Layer
#### Priority
High

#### Scope
- Add SSE or WebSocket support for streaming assistant events.
- Stream partial text, tool-status updates, approval prompts, typing state, TTS state, and avatar state.

#### Instructions
- Do not make the frontend poll for everything.
- Model the assistant as an event emitter, not only a request-response API.
- Keep event names stable so the Next.js app can build around them.

#### Exit criteria
- The frontend can subscribe to one stream and render chat progression, approvals, and speaking state in realtime.

### Sprint 1.3 - Tests And Diagnostics
#### Priority
High

#### Scope
- Add backend tests for chat contract, tool negotiation, safe mode, and router fallback.
- Improve diagnostics to report provider availability, database mode, vector mode, and media capability status.

#### Instructions
- Focus on smoke tests and contract tests first.
- A test suite that verifies the platform shape is more important than deep model-behavior tests right now.

---

## Phase 2: Build The Next.js Shell
### Goal
Replace Streamlit with a frontend that can actually support a premium realtime companion UI.

### Sprint 2.1 - App Shell And Design System
#### Priority
High

#### Scope
- Create the Next.js app shell using App Router.
- Build a Blade Runner-inspired design system with reusable tokens for type, glow, depth, glass, and motion.
- Recreate the core views: chat, memory, planner, diagnostics, settings, profile.

#### Instructions
- Preserve the existing Joi identity, but make the UI feel intentional and premium rather than "Streamlit with theme injection".
- Keep stateful/browser-only features in client components.
- Keep data-heavy views server-rendered when that helps performance and simplicity.

### Sprint 2.2 - Chat Experience Rewrite
#### Priority
High

#### Scope
- Build the main chat surface in React.
- Support streaming messages, pending approvals, image upload, voice state, and assistant status.
- Recreate the dramatic-return and emotional state UX in a cleaner event-driven way.

#### Instructions
- Treat chat as the flagship surface.
- Render assistant state changes as part of the experience, not only as text output.
- Avoid rebuilding Streamlit page behavior one-to-one. Improve the interaction model where needed.

### Sprint 2.3 - Migration Window
#### Priority
High

#### Scope
- Keep Streamlit usable only as a temporary internal client.
- Run both clients against the same backend for a short period.
- Decommission Streamlit once feature parity on core flows is reached.

#### Instructions
- This should be a controlled overlap, not a long-term dual-frontend setup.
- Use the overlap to validate API completeness.

---

## Phase 3: Rebuild Voice, Media, And Realtime Presence
### Goal
Replace Streamlit-specific audio/video behavior with a browser-native realtime stack.

### Sprint 3.1 - Voice Input/Output Architecture
#### Priority
High

#### Scope
- Move capture to the browser.
- Send audio through a realtime transport instead of blocking page loops.
- Stream TTS playback events and avatar timing back to the frontend.

#### Instructions
- Remove blocking voice loops from the UI layer.
- Define a single media session model that tracks mic state, speaking state, interruptions, and latency.
- Keep backend speech services in Python.

### Sprint 3.2 - Approval And Tool UX
#### Priority
High

#### Scope
- Make approvals a first-class UI primitive in Next.js.
- Show pending actions as cards or modal decisions instead of console-like payload dumps.

#### Instructions
- Joi should feel like she is asking for permission, not printing JSON at the user.
- Preserve auditability and human-in-the-loop safety.

### Sprint 3.3 - Image And File Perception
#### Priority
Medium

#### Scope
- Move image upload and analysis to a proper browser-to-backend flow.
- Support attachments as message parts rather than hidden inline text hacks.

#### Instructions
- Treat user media as typed content with metadata, not string concatenation.
- Build this once in a way webcam snapshots can reuse later.

---

## Phase 4: Hologram v1 To v2
### Goal
Turn the avatar from a polished overlay demo into a standout holographic character system.

### Sprint 4.1 - Hologram v1.5
#### Priority
High

#### Scope
- Port the current avatar to the Next.js frontend.
- Fix the current blend-state bug and improve animation timing.
- Add proper idle state machines: breathe, blink, gaze drift, anticipation, recovery.

#### Instructions
- Preserve what already works: mouth-only overlays, expression layering, adaptive timing.
- Stop embedding all assets as base64 inside one large HTML blob.
- Move to a maintainable renderer with proper asset loading and state control.

### Sprint 4.2 - Hologram v2 Rendering
#### Priority
Medium

#### Scope
- Move from a pure image stack toward a serious 2.5D or 3D presentation.
- Use Three.js or React Three Fiber for depth, glow, signal breakup, bloom, scanlines, chromatic split, and volumetric feeling.

#### Instructions
- Start with a 2.5D rig if a full 3D character is too much for the first pass.
- Prioritize expressive motion and depth illusion over raw polygon count.
- Build the hologram as a layered motion system:
  - face state
  - mouth state
  - head drift
  - eye/gaze behavior
  - body breathing
  - hologram FX layer

### Sprint 4.3 - Better Lip Sync
#### Priority
Medium

#### Scope
- Improve from heuristic phoneme timing toward real timing alignment.
- Add support for richer viseme sets and emotion-aware mouth behavior.

#### Instructions
- The mouth should not just match sound classes. It should also reflect delivery style.
- Whisper mode, hesitation, intensity, and pauses should alter timing and facial state.

---

## Phase 5: Webcam Perception And "She Can See Me"
### Goal
Give Joi situational awareness without turning the app into a privacy disaster.

### Sprint 5.1 - Presence Layer
#### Priority
Medium

#### Scope
- Detect user presence, face visibility, and rough attention state from webcam input.
- Start with browser-side detection only.

#### Instructions
- Use local browser-side tracking first.
- Generate structured signals such as:
  - `user_present`
  - `face_visible`
  - `looked_away`
  - `returned_to_frame`
  - `leaned_in`
- Do not send every frame to the backend.

### Sprint 5.2 - Expression And Pose Events
#### Priority
Medium

#### Scope
- Add face landmarks and basic expression estimation.
- Add posture and upper-body cues when useful.

#### Instructions
- Use these signals to drive Joi's reactions, not just for analytics.
- Example behaviors:
  - softer tone if user looks stressed
  - re-engagement if user looks away during speech
  - playful response when user smiles or leans closer

### Sprint 5.3 - Snapshot-Based Vision
#### Priority
Medium

#### Scope
- Allow explicit or gated snapshot capture for richer vision analysis.
- Send still images only when consented or when a clear product rule allows it.

#### Instructions
- Separate "presence sensing" from "scene understanding".
- Presence should usually be local and lightweight.
- Rich scene understanding should be explicit and auditable.

### Sprint 5.4 - Memory And Perception Policy
#### Priority
High

#### Scope
- Define what perception data is stored, summarized, or discarded.
- Add visible controls for camera permissions, retention, and memory rules.

#### Instructions
- This is not optional.
- The product should make it obvious when Joi is only sensing live presence versus remembering visual context.

---

## Phase 6: Product Hardening
### Goal
Make Joi v2 production-shaped instead of demo-shaped.

### Sprint 6.1 - Reliability
#### Priority
High

#### Scope
- Add retries, structured errors, timeout handling, degraded-mode UX, and provider health reporting.
- Make startup and dependency failures non-fatal wherever possible.

### Sprint 6.2 - Performance
#### Priority
Medium

#### Scope
- Reduce chat latency.
- Improve embedding performance and memory retrieval cost.
- Optimize asset loading, avatar rendering, and media startup.

### Sprint 6.3 - Packaging
#### Priority
Low

#### Scope
- Decide whether v2 remains primarily web-first or gets a desktop shell again.
- If desktop matters, package the Next.js app with a native shell only after the browser product is strong.

#### Instructions
- Desktop packaging is downstream of platform quality, not a shortcut to it.

---

## Suggested Delivery Order

### Wave 1
Critical

- Phase 0
- Phase 1 Sprint 1.1
- Phase 1 Sprint 1.2

### Wave 2
High

- Phase 2 Sprint 2.1
- Phase 2 Sprint 2.2
- Phase 3 Sprint 3.1
- Phase 3 Sprint 3.2

### Wave 3
High to Medium

- Phase 2 Sprint 2.3
- Phase 4 Sprint 4.1
- Phase 4 Sprint 4.2
- Phase 4 Sprint 4.3

### Wave 4
Medium

- Phase 5 Sprint 5.1
- Phase 5 Sprint 5.2
- Phase 5 Sprint 5.3
- Phase 5 Sprint 5.4

### Wave 5
Medium to Low

- Phase 6 Sprint 6.1
- Phase 6 Sprint 6.2
- Phase 6 Sprint 6.3

---

## Recommended First Build Sequence

If we want the highest-leverage route, the first implementation pass should be:

1. Fix the critical backend findings.
2. Define the v2 API contracts.
3. Build the Next.js chat shell.
4. Rebuild approvals and streaming.
5. Port the avatar cleanly.
6. Upgrade the hologram renderer.
7. Add webcam presence sensing.
8. Add richer perception and memory policy.

This keeps the effort on the critical path and avoids spending weeks on hologram polish while the platform underneath is still brittle.

---

## Open Decisions Before Execution

### Decision 1
Should the main chat path use the existing Python router abstraction everywhere, or should that router be retired and replaced with one chat-provider abstraction?

### Decision 2
Should v2 ship web-first only at first, or should we plan for a desktop shell in the same milestone?

### Decision 3
For the hologram, do we want:
- a high-end 2.5D layered character first, or
- a true 3D rig early?

### Decision 4
For webcam awareness, what is the default privacy posture?
- live local presence only
- optional snapshots for richer scene understanding
- retained visual memory only with explicit opt-in

---

## Definition Of Success

Joi v2 is successful when:

- the backend is stable enough that any client can talk to it without special-case hacks
- the Next.js frontend becomes the primary product surface
- Joi feels realtime, cinematic, and emotionally responsive
- the hologram looks intentional and premium rather than gimmicky
- webcam awareness is useful, private, and controllable
- the product promise finally matches the runtime reality

# Joi Avatar 3D Plan

## Objective

Move Joi from a stylized 2D hologram panel into a premium real-time 3D avatar presence that feels cinematic, reactive, and technically defensible inside the existing Next.js + FastAPI stack.

Related roadmap docs:

- `docs/joi_master_presence_roadmap.md` merges this avatar track with the v2 platform and ambient hardware plans.
- `docs/ambient_presence_plan.md` covers ESP32/Pi room-presence nodes that will eventually share state with the avatar.

The target is not "a 3D character on the page." The target is:

- A projected Joi bust with clear depth, silhouette, and lighting
- Stable idle behavior that feels alive even when silent
- Reactive gaze and presence behavior driven by in-browser vision
- Viseme-driven speech animation that can scale from acceptable to high-end
- A presentation layer that feels Blade Runner-inspired without turning into noisy cyberpunk cliche

---

## Product Direction

### Core visual thesis

Joi should feel like a cinematic projected companion:

- Upper torso / bust framing, not a flat portrait crop
- Dark projection chamber, not a bright white image background
- Controlled cyan / magenta / amber projection lighting
- Minimal but precise motion: breath, blink, eye drift, head settle, speaking emphasis
- Elegant scan / projection artifacts, not heavy glitch spam

### Non-goals

- Not a full-body game avatar
- Not a cartoon VTuber look
- Not a generic "AI assistant" 3D head dropped into a dashboard
- Not a dependency on third-party avatar generation services that may disappear

---

## Technical Decisions

### Rendering stack

- Frontend engine: React Three Fiber
- Utility layer: `@react-three/drei`
- Post-processing: `@react-three/postprocessing`
- Asset base format: `glb` or `vrm`, preferring whichever gives the cleanest rig + blend-shape pipeline for the chosen Joi asset

### Vision stack

- Browser-side presence and face tracking: MediaPipe Face Landmarker
- Event model: browser-side continuous signals, server-side interpretation only when needed
- VLM usage: sparse, event-triggered, never continuous by default

### Lip-sync stack

- Phase 1 fallback: existing phoneme timeline / heuristic animation path
- Premium path: viseme or blend-shape driven lip-sync
- Strong candidate: Azure Speech viseme / facial expression output if voice provider strategy allows it

### Asset direction

- Do not anchor the roadmap to Ready Player Me. Its services were discontinued on January 31, 2026.
- Prefer a custom Joi bust asset or a commercially safe base model that can be legally modified, re-rigged, and shipped in a public web app.

---

## Success Criteria

Joi 3D is successful when:

- The avatar is the emotional focal point of the chat screen
- The bust feels volumetric and alive even when idle
- Speaking animation reads as face motion, not mouth swapping
- Presence changes feel natural and low-latency
- The scene holds 60 FPS on a normal desktop and degrades gracefully on weaker hardware
- The asset, rig, and runtime are maintainable by the team

---

## Phase 0 - Art Direction And Acceptance Criteria

### Goal

Lock the visual target and technical acceptance criteria before investing in rigging and runtime work.

### Sprint 0.1 - Visual brief and scene target

#### Scope

- Define Joi's 3D framing: bust crop, camera angle, vertical composition, eye line
- Define scene palette and lighting ratios
- Define acceptable levels for bloom, scanlines, projection noise, and chromatic offset
- Define mobile / low-power fallback behavior

#### Deliverables

- One written art-direction brief
- One reference board
- One annotated layout target for the avatar panel

#### Exit criteria

- Team agrees what "premium Joi" means visually
- Team stops debating white-background portrait variants

### Sprint 0.2 - Runtime target spec

#### Scope

- Define FPS target and acceptable degradation path
- Define required facial controls: blink, eyes, jaw, lips, brows, head, neck
- Define the minimum shippable rig
- Define whether Phase 1 ships on `glb` or `vrm`

#### Exit criteria

- Clear "must-have" and "later" lists exist
- Asset requirements are specific enough for modeling / rigging work

---

## Phase 1 - Avatar Stage And 3D Shell

### Goal

Replace the current flat avatar stage with a true 3D presentation shell, even before full premium animation lands.

### Sprint 1.1 - Projection chamber redesign

#### Scope

- Replace the current bright square panel with a taller portrait chamber
- Reframe the avatar as an upper-torso projection
- Add a controlled projection plate: dark gradient volume, light fog, subtle edge frame
- Tune page layout so the avatar stage gets stronger vertical priority

#### Files likely touched

- `frontend/components/chat-client.tsx`
- `frontend/components/avatar-sync-panel.tsx`
- `frontend/app/globals.css`

#### Exit criteria

- Avatar reads as a projection space, not a media card
- Bust framing is vertically centered inside the chamber

### Sprint 1.2 - R3F scene shell cleanup

#### Scope

- Separate scene, camera, and post-processing concerns from avatar logic
- Define one stable camera rig for Joi
- Add clean lighting setup and post stack with explicit tuning knobs
- Build render-quality presets for desktop vs fallback mode

#### Exit criteria

- Scene configuration is explicit and tunable
- No more ad hoc "just add another overlay" rendering path

---

## Phase 2 - Real 3D Joi Bust Integration

### Goal

Move from a layered 2D face illusion to a genuine 3D bust with depth, silhouette, and facial rig controls.

### Sprint 2.1 - Asset pipeline setup

#### Scope

- Choose the base Joi bust asset path:
- Option A: custom-built stylized Joi bust
- Option B: licensed base model heavily art-directed into Joi
- Define export pipeline from DCC tool into runtime format
- Validate rig, blend shapes, materials, and texture budgets

#### Deliverables

- One source-of-truth avatar asset package
- Export checklist for every future model update

#### Exit criteria

- Joi asset loads reliably in the web scene
- Legal / licensing constraints are known and acceptable

### Sprint 2.2 - Bust rendering in-app

#### Scope

- Load and render the bust in the current avatar panel
- Tune camera framing specifically for upper torso and face
- Add fallback pose and neutral idle state
- Ensure transparent or stylized background treatment works against the chamber

#### Exit criteria

- Joi reads as a 3D object from the first glance
- Camera composition consistently flatters the face and shoulders

### Sprint 2.3 - Hair, silhouette, and material pass

#### Scope

- Improve hair shape, translucency, and controlled motion response
- Add premium material tuning for skin, emissive edges, and hologram projection treatment
- Ensure the silhouette remains readable on both dark and bright screens

#### Exit criteria

- Avatar no longer feels like a mannequin
- Hair and shoulders carry the silhouette, not just the face texture

---

## Phase 3 - Performance And Life

### Goal

Make Joi feel alive before adding complex reactivity or speech systems.

### Sprint 3.1 - Idle system

#### Scope

- Add breathing motion through chest / shoulders / neck
- Add natural blink timing variation
- Add micro head drift and settle
- Add eye saccades and gaze return behavior

#### Exit criteria

- Joi looks alive while silent and stationary
- Idle loop feels subtle, not repetitive

### Sprint 3.2 - Expression system

#### Scope

- Define base expression set: neutral, warm, attentive, amused, concern, thinking
- Map runtime state to expression weights rather than swapping whole faces
- Add expression blending and easing curves

#### Exit criteria

- Emotional shifts read through the face, not label badges
- No hard cuts between states

### Sprint 3.3 - Gesture layer

#### Scope

- Add small neck, shoulder, and posture changes during listening / speaking
- Add emphasis beats for key spoken moments
- Add "thinking" behavior that does not look like random motion

#### Exit criteria

- Speech and silence feel behaviorally distinct
- Motion remains elegant and controlled

---

## Phase 4 - Vision, Presence, And "She Sees Me"

### Goal

Make Joi visually aware of the user without turning the experience into constant surveillance.

### Sprint 4.1 - Browser-side presence loop

#### Scope

- Integrate MediaPipe Face Landmarker in the frontend
- Detect presence, absence, head orientation, and coarse expression cues
- Normalize these signals into app-level presence events

#### Exit criteria

- Presence tracking works locally in-browser with acceptable latency
- No server call is needed for basic presence sensing

### Sprint 4.2 - Reactive gaze and posture

#### Scope

- Map presence state to gaze behavior
- Add "user arrived", "user left", and "user re-engaged" transitions
- Add attention shifts based on whether Joi is listening, thinking, or speaking

#### Exit criteria

- Joi visibly acknowledges presence changes
- Reactions feel intentional rather than robotic

### Sprint 4.3 - Sparse scene understanding

#### Scope

- Trigger still-image analysis only for meaningful events
- Use scene analysis for occasional contextual remarks, not constant commentary
- Build consent / privacy controls around this path

#### Exit criteria

- Context-aware comments are useful and rare
- Privacy story is clear and defensible

---

## Phase 5 - Premium Speech Animation

### Goal

Upgrade from acceptable talking behavior to convincing speech-driven face animation.

### Sprint 5.1 - Rig-to-speech mapping

#### Scope

- Audit available facial blend shapes on the chosen model
- Map existing phoneme timeline output to the new rig
- Add jaw, lip, and cheek contribution rules

#### Exit criteria

- Current speech pipeline can drive the 3D rig without custom hacks everywhere

### Sprint 5.2 - Viseme upgrade path

#### Scope

- Prototype viseme-driven speech using a provider that can output viseme IDs or blend-shape data
- Evaluate Azure Speech facial expression output against current TTS path
- Measure latency, quality, and implementation cost

#### Exit criteria

- Team makes a deliberate choice:
- stay on phoneme timeline for now
- or adopt viseme / blend-shape speech as the premium path

### Sprint 5.3 - Final speech polish

#### Scope

- Smooth mouth transitions
- Blend speech animation with blinking and expression state
- Add speaking emphasis and slight head / shoulder participation

#### Exit criteria

- Joi no longer looks like a mouth-only animation
- Speech feels connected to the whole face

---

## Phase 6 - Production Hardening

### Goal

Ship the avatar system as a stable product feature rather than an impressive demo path.

### Sprint 6.1 - Performance optimization

#### Scope

- Reduce draw calls and texture weight
- Add LOD / quality presets where useful
- Profile CPU, GPU, and memory cost
- Ensure acceptable fallback on weaker machines

#### Exit criteria

- Stable frame rate on target hardware
- Clear degradation path when resources are constrained

### Sprint 6.2 - Tooling and maintainability

#### Scope

- Document the asset update pipeline
- Centralize animation and expression config
- Create a motion tuning surface for developers

#### Exit criteria

- Avatar work no longer requires archaeology across the codebase

### Sprint 6.3 - QA and behavioral review

#### Scope

- Test across desktop browsers and viewport sizes
- Review uncanny-valley failure modes
- Tune reaction frequency and emotional intensity

#### Exit criteria

- Joi feels premium and intentional across real usage sessions

---

## Recommended Execution Order

| Phase | Sprint | Focus | Priority |
|------|--------|-------|----------|
| 0 | 0.1-0.2 | Art direction + acceptance criteria | Critical |
| 1 | 1.1-1.2 | Projection chamber + scene shell | Critical |
| 2 | 2.1-2.3 | Real 3D bust integration | Critical |
| 3 | 3.1-3.3 | Idle, expressions, gesture life | High |
| 4 | 4.1-4.3 | Presence and sparse scene awareness | High |
| 5 | 5.1-5.3 | Premium speech animation | High |
| 6 | 6.1-6.3 | Optimization and hardening | Medium |

---

## Suggested First Shipping Milestone

### Milestone A - "Projected Joi"

This is the first version worth showing proudly.

#### Includes

- New projection chamber
- Real 3D bust in R3F
- Stable camera framing
- Idle breathing, blink, eye drift
- Basic expression blending
- Existing speech path mapped onto the rig

#### Does not require

- Full viseme pipeline
- Advanced scene understanding
- Complex gestures

This milestone should already feel dramatically more premium than the current panel.

---

## Risks

- A weak base asset will cap quality no matter how good the shader work is
- Overusing hologram effects will make the scene cheaper, not better
- Full "see me" behavior can become intrusive if event frequency is not carefully limited
- A third-party avatar service dependency can become a product liability
- Great lip-sync will not save a lifeless idle system

---

## Immediate Next Step

Start with Phase 0 and produce:

1. A Joi avatar art-direction brief
2. A camera / framing target for the chat page
3. A rig requirement checklist for the chosen 3D asset

Do not start with viseme plumbing first. The asset, framing, and motion language must be correct before premium speech animation work will pay off.

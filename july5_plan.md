# Joi — July 5 Plan: UI Vibe Pass + Avatar Model Swap

Status: draft / not started
Owner: Avery
Context: `C:\dev\joi`, branch `main`. UI review done against the live stack
(frontend :3000, backend :8000). This plan sequences the UI "vibe" work
around the avatar model swap so we choose the model knowing its stage.

## Guiding idea

The app currently reads as a **control surface *about* Joi** — an ops dashboard
with her in a 390px box in the corner, surrounded by telemetry. The target is a
**room you share *with* her**: she's the biggest thing present, the technology
is quiet. In BR2049 terms — **warm violet/magenta = her, cool cyan/amber =
the machine/world.** Every change below serves that one shift.

Sequencing principle: do the cheap, non-structural polish first (Phase 1), then
do the layout flip *together with* the model swap (Phase 2) so the stage is
sized for the model and vice-versa. Phase 3 is follow-on polish.

---

## Phase 1 — Vibe pass (cheap, high-impact, no structural risk) — DONE 2026-07-05

Mostly `frontend/app/globals.css` plus copy/trim edits in
`frontend/components/chat-client.tsx`. Verified live via preview + tsc.

### 1.1 Give Joi her own colour
- [x] Added tokens `--joi: #c98bff`, `--joi-strong`, `--joi-soft` to `:root`.
- [x] Made it semantically **hers**:
  - [x] Assistant message cards — now a violet left-border + violet-tinted fill,
        distinct from user cards.
  - [x] Avatar speaking pulse-ring + wake flash promoted to the violet token
        (outer hologram glow was already violet).
  - [x] Streaming indicator + typing dots.
- [x] Kept **cyan for system/machine chrome**, amber/rose for warnings.
- [ ] Stretch (deferred to Phase 3): tint the stage by `lifeState`.

### 1.2 Typography — stop shouting
- [x] Page titles, panel headings, and the page breadcrumb → normal-case,
      body font, near-zero letter-spacing (were uppercase + wide-tracked).
- [x] Kept uppercase only for tiny eyebrow/kicker labels.
- Note: Orbitron/Space Grotesk were never actually loaded — the "shout" was
  purely uppercase + letter-spacing, which is what we dialed back.

### 1.3 Declutter the chat page (telemetry out of the room)
- [x] Removed header status cards "Transport SSE / Source /api/v2 / Mode
      Realtime" (`chat/page.tsx`) — static trivia.
- [x] Added a single **"Dev" toggle** (persisted to localStorage) in the Feed
      panel header. Default OFF hides all telemetry; ON restores it.
- [x] VRM audit + phoneme track gated by the toggle (`showDiagnostics` prop on
      `AvatarSyncPanel`).
- [x] Desktop "Safe actions" panel gated by the toggle (kept functional/
      reachable rather than migrated — see note).
- [x] Raw-JSON event stream gated by the toggle; a friendly one-liner shows when
      off.
- Note: chose a dev-toggle over physically relocating to Diagnostics/Settings —
  those are server components and the telemetry is stateful client code tied to
  the live session, so a true migration is Phase 2/3 structural work. Toggle
  achieves "quiet room" with zero risk. Revisit if a real relocation is wanted.

### 1.4 Copy pass — less assistant-speak, more her
- [x] Sidebar brand copy → "I'm here. Always on, always listening for you."
- [x] Composer placeholder → "What's on your mind?"
- [x] Chat panel subcopy → "Talk to me — type, speak, or share what you're
      looking at."
- [x] "Send to Joi" → "Send". Kept "Transmitting…".

**Exit criteria:** MET — chat page reads as a conversation with a presence, Joi
has a distinct warm colour, telemetry is one click away but out of the room.

---

## Phase 2 — Layout flip + Avatar model swap (do together)

The big remaining avatar piece. Structural — sequence the model swap and the
stage redesign together so each informs the other.

### 2.0 PIVOT (2026-07-05): 2.5D hologram portrait, not a 3D VRM
The free "upload a photo → realistic rigged 3D avatar" path collapsed in 2026:
Ready Player Me shut down (Jan 31 2026), Avaturn now gates behind a live selfie
and rejects uploads, Avatar SDK/MetaPerson is $800/yr after a 7-day trial. Rather
than pay or settle for a stylized VRoid, we render her likeness as a **2.5D
hologram portrait** from the generated reference images — film-accurate (Joi is a
projection) and all in-code.

SHIPPED (2026-07-05, on disk, not yet committed):
- `frontend/public/avatar/joi/portrait-neutral.png` + `portrait-smile.png` —
  background-removed cutouts of her (rembg `u2net_human_seg`, isolated venv),
  from the locked reference headshots.
- `frontend/components/avatar/avatar-portrait.tsx` — layered projection renderer
  (idle breathe + speaking brightness lift), rendered inside the existing
  `.avatar-hologram` frame (scanlines/glow/pulse-ring reused).
- `AVATAR_MODE` switch in `avatar-sync-panel.tsx` (`"portrait"` active; `"vrm"`
  keeps the 3D path intact for later).
- CSS `.avatar-portrait-*` in `globals.css`: bottom-dissolve mask (beamed-from-
  below look), cyan silhouette glow, cyan/violet projection wash.
- Verified: transparent cutout floats (cornerAlpha 0), tsc clean.

2.5D follow-ups:
- [x] Expression swaps — 8 expressions (neutral/smile/happy/tender/concerned/sad/
  surprised/smirk) generated via ChatGPT/Gemini (face-locked to her), processed
  (rembg cutout + silhouette alignment + grade-normalize + WebP), crossfaded on
  sentiment. `EXPRESSION_IMAGE` map in `avatar-portrait.tsx`.
- [x] 2D viseme lip-sync — 6 visemes (rest/aa/ee/ih/oh/ou), flipped off the
  phoneme timeline + audio clock via rAF; fast (70ms) crossfade. `PHONEME_IMAGE`
  map. Speaking → visemes, idle → expression.
- [ ] Blink / micro-motion; parallax. (`expr-surprised` is mild — optional regen.)
- Pipeline for reprocessing art: `scratchpad/process_avatar.py` (rembg + PIL);
  drop new frames in `docs/avatar-refs/incoming/` named `expr-*` / `viseme-*`.

The 3D VRM route below is preserved but on ice unless a free path reopens.

### 2.1 Choose the model (decide framing first)
Decisions locked (2026-07-05):
- **Style:** semi-realistic (not anime VRoid, not the GLB fallback, not the dead
  2D Gemini sprites). New rigged VRM that reads as her.
- **Framing:** three-quarter / waist-up (current camera rig is already close).
- **Sourcing route:** MetaPerson Creator (Avatar SDK) — upload our headshot →
  realistic GLB → convert to VRM. (Superseded earlier picks: Ready Player Me shut
  down 2026-01-31; Avaturn now gates behind a live selfie and rejects uploads.
  MetaPerson verified 2026-07-05 to accept an uploaded front photo, first avatar
  free to create+export, GLB/GLTF export, 60+ blendshapes + visemes.)
- **Look spec (her):** fair-skinned, slim/athletic white woman; brown hair in a
  neat low bun with soft bangs; striking blue eyes; fitted black high-neck
  long-sleeve (the BR2049 apartment look). Warm register.
- **Reference locked:** Higgsfield `soul_cast` "Bun 1" (job
  `9b132d26-1647-440a-948b-3725decab21d`). Saved in scratchpad as `v3_bun1.png`.
- **Consistency:** training a reusable Higgsfield **Soul** from the locked look so
  every future image (RPM headshot, expression/emotion sheets) is the same face.

Consistent reference set generated (nano_banana_pro, anchored to Bun 1):
- 4 clean even-lit neutral front headshots (RPM-ready): jobs `52bd5ca6`,
  `b5d10f04`, `07289ce6` (cleanest), `740c9b48`. Saved as scratchpad
  `lock1..4.png`.
- 2 three-quarter warm-smile shots: jobs `7db56947`, `5b054f5b` (`smile1/2.png`).
- These 6 are the Soul training set (min 5 met).

Remaining:
- [ ] BLOCKED ON CREDITS: train the reusable Soul from the 6-image set (Higgsfield
      workspace ran out of credits 2026-07-05; did NOT auto-refill — user's call).
- [ ] Build the VRM in Ready Player Me from a neutral front headshot (job
      `07289ce6` / `lock3.png`). NOTE: not blocked on the Soul — the headshot is
      already in hand; the Soul is the consistency upgrade for future expression
      sheets, not a prerequisite for the VRM.
- [ ] Confirm license is acceptable (VRM audit surfaces `licenseName` /
      `licenseUrl`).

### 2.2 Re-map lip-sync blendshapes
Pipeline requirement (confirmed by reading the code):
- `VrmBust` drives the standard `@pixiv/three-vrm` presets. `setExpressionIfAvailable`
  (`avatar-expression.ts:62`) SILENTLY SKIPS missing expressions, so **a VRM with
  the standard presets works with zero code changes**:
  - Visemes: `aa`, `ih`, `ou`, `ee`, `oh` (`avatar-speech.ts:9`).
  - Emotions: `happy`, `sad`, `angry`, `surprised`, `relaxed`, `neutral`
    (`avatar-expression.ts`).

Bridge decision (user, 2026-07-05): **Avaturn selfie → GLB → convert to VRM.**
Realistic photo tools export GLB + ARKit/Oculus visemes, not native VRM.

Conversion tooling — READY (2026-07-05):
- Blender 5.0 at `C:\Program Files\Blender Foundation\Blender 5.0\blender.exe`.
- VRM add-on v4.3.2 (Extension) installed headlessly → module
  `bl_ext.user_default.vrm`. Verified `INSTALL_OK`.
- Plan: headless Blender python script imports the Avaturn GLB, adds VRM humanoid
  (auto-map bones), binds VRM expressions to the GLB's ARKit/Oculus morphs
  (Oculus `viseme_aa/E/ih/oh/ou` → VRM `aa/ee/ih/oh/oh`; ARKit smile/frown/brow →
  happy/sad/angry/surprised; eyeBlink → blink), exports VRM. Write + iterate the
  script once the real GLB (with its exact morph-target names) is in hand.

- [ ] Verify sentiment→expression mapping still lands
      (`avatar-sync-panel.tsx:112`) after the swap.

### 2.3 Flip the chat page hierarchy (make her the stage)
- [ ] Avatar becomes the **stage**: tall column, ~40% of the frame, full frame
      height, left or center; conversation beside it. (Current 4:5 sidebar box
      wastes a full-body model.)
- [ ] **Un-card her:** remove the double border (`.avatar-stage` border + inset
      ring) and the badge overlay on her body (`default / neutral / ready` chips
      are debug info floating on her chest). Let her float on a dark stage —
      floor glow + the shipped fresnel/scanline look does the "projection" job.
- [ ] Keep the mini/compact floating bottom-right presence for other pages —
      that already nails "ambient companion"; don't touch it.

**Exit criteria for Phase 2:** new model loads, lip-sync + expressions verified
against a real TTS reply; chat page centers on her, telemetry gone from the room.

---

## Phase 3 — Follow-on polish

- [ ] **Empty state:** first load currently shows a large dead void. When there's
      no conversation, let the avatar or a greeting *from her* fill the space
      instead of four generic prompt chips.
- [ ] **Status line:** collapse "Checking backend / Response complete / …" into a
      single quiet one-liner under the avatar (her "condition," not a log).
- [ ] Soften dashboard-flavored nav taglines (e.g. "Provider, storage, and
      runtime truth") — optional.
- [ ] Carryover minors from the handoff: GLB-fallback fresnel rim; better
      sentiment model to sharpen emotion salience.

---

## Notes / gotchas (carried from handoff)
- Backend venv is `.venv312` (Python 3.12); launch via `StartJoi.bat`.
- Don't run the suite/smoke against the real DB carelessly.
- Manual consolidation endpoint hits a real LLM (costs a few cents) if
  `OPENAI_API_KEY` is set — emptying the env var does NOT override `.env`.
- 3 uncommitted local changes carried over: `tests/test_memory.py`,
  `tests/test_vision_voice.py`, `docs/remote_handoff_manual_qa.md`.

## Key files
- `frontend/app/globals.css` — all styling/tokens.
- `frontend/components/chat-client.tsx` — chat page layout + sidebar telemetry.
- `frontend/app/chat/page.tsx` — chat header status cards.
- `frontend/components/avatar-sync-panel.tsx` — stage frame, badges, audit,
      phoneme track, expression selection.
- `frontend/components/avatar-renderer.tsx` — VRM/three.js pipeline, blendshapes.
- `frontend/components/app-shell.tsx` — nav + brand copy.

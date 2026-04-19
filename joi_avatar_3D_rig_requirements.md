# Joi Avatar 3D Rig Requirements

## Purpose

This document defines the minimum rig, facial controls, asset constraints, and export requirements for Joi's 3D avatar.

The goal is to prevent the team from choosing or building an asset that looks good in a still render but fails once it has to blink, speak, emote, and react in realtime.

---

## Rig Philosophy

Joi does not need a full gameplay character rig.

Joi does need:

- a premium bust silhouette
- stable head and neck motion
- expressive face controls
- speech-capable lip and jaw controls
- enough upper torso structure for breathing and posture shifts

The rig should be optimized for close-up conversation performance, not full-body locomotion.

---

## Minimum Shippable Scope

### Body scope

Minimum geometry and rig support:

- head
- neck
- clavicles
- shoulders
- upper chest
- upper torso / bust line

Optional for later:

- arms below upper arm
- full body
- hands as hero elements

---

## Required Skeletal Controls

### Core bones / transforms

Required:

- head
- neck
- upper chest or chest root
- left clavicle
- right clavicle
- left shoulder / upper arm root
- right shoulder / upper arm root

Recommended:

- spine / upper torso controller for breathing
- dedicated eye bones or eye aim controls
- jaw bone

### Motion expectations

The rig must support:

- subtle head drift
- nods and micro emphasis beats
- neck settling
- shoulder response
- chest breathing

If the torso cannot move cleanly, Joi will still feel disembodied even with a good face.

---

## Required Facial Control Set

### Minimum facial outputs

Required:

- blink left
- blink right
- eye look left
- eye look right
- eye look up
- eye look down
- jaw open
- mouth close
- mouth funnel
- mouth pucker
- mouth smile / corner pull
- mouth frown / corner depress
- brow inner raise
- brow down

Strongly recommended:

- cheek raise
- lip upper raise
- lip lower depress
- mouth stretch
- mouth shrug upper / lower
- sneer / asymmetry controls

### Expression blending

The face rig must support blended weights.

Hard expression swaps are not acceptable for the premium target.

---

## Speech Animation Requirements

### Minimum speech-capable controls

Required for a workable first pass:

- jaw open
- mouth close
- lip funnel
- lip pucker
- smile / corner width
- lower lip and upper lip shaping support

### Premium speech path compatibility

Preferred:

- ARKit-like blend shape compatibility
- or a clearly documented mapping layer from provider visemes to rig controls

This matters because later phases may use viseme IDs or blend-shape output from TTS systems.

---

## Eye System Requirements

### Mandatory behavior support

- independent blinking
- eye target / gaze aim
- small saccades
- return-to-user gaze

### Why this is mandatory

Without strong eye behavior, even a good face rig will still feel dead in a conversational assistant context.

---

## Hair And Secondary Motion Requirements

### Minimum requirement

- hair silhouette must hold up in close portrait framing

### Preferred

- limited secondary motion support for hair strands or grouped locks
- stable performance under subtle movement

### Constraint

Hair motion should be elegant and restrained.

Do not build a physics-heavy hairstyle that becomes the dominant moving element in the scene.

---

## Topology And Mesh Requirements

### Face topology

- must deform cleanly around eyes, lips, and jaw
- must hold expression changes without visible collapse
- should support close-up portrait rendering

### Silhouette

- hair, head, neck, and shoulders must read clearly against a dark chamber
- neckline and shoulder form should support the bust framing

### Optimization

- mesh density should favor the face and silhouette
- unnecessary geometry outside the bust should be removed if it does not serve the shot

---

## Material And Texture Requirements

### Required maps or equivalents

- base color / albedo
- normal
- roughness
- emissive if used for projection treatment

### Quality goals

- skin must hold up in close portrait framing
- hair must read under cool rim lighting
- materials must survive mild bloom and projection shimmer

### Avoid

- overly glossy skin
- noisy microdetail that turns ugly under post-processing
- textures that only look correct under flat white light

---

## Runtime Format Requirements

### Acceptable formats

- `glb`
- `vrm`

### Selection rule

Choose the format that gives the team:

- stable runtime loading
- maintainable rig access
- clean animation targeting
- viable blend-shape control in the browser

### Do not choose format based on trend

If a technically simpler `glb` pipeline produces a better controlled Joi than a messier `vrm` integration, use `glb`.

---

## Export Requirements

Every export must preserve:

- skeleton hierarchy
- facial blend shapes or equivalent facial controls
- material assignment
- scale and orientation conventions
- consistent neutral pose

Every export should document:

- source tool and version
- export settings
- texture sizes
- rig control summary
- known limitations

---

## Performance Constraints

The rig and asset should be designed for:

- desktop browser runtime
- realtime chat usage
- sustained scene residency

That means:

- reasonable texture budgets
- facial controls that animate cheaply enough for continuous use
- no unnecessary full-body complexity

The avatar is a persistent UI presence, not a one-off hero render.

---

## Animation Compatibility Checklist

The asset is acceptable only if it supports:

- neutral idle pose
- blink loop
- gaze targeting
- breathing motion
- subtle head turn
- expression blending
- speech animation from phoneme or viseme mapping

The asset is not acceptable if:

- facial animation depends on baked clips only
- the mouth controls are too limited for speech
- the eyes cannot aim cleanly
- shoulders or chest are too rigid to breathe

---

## Preferred Production Checklist

Before the team commits to an asset, verify:

1. Can it render well as a bust in a dark chamber?
2. Can the face blend smoothly between emotional states?
3. Can the rig support subtle breathing and shoulder life?
4. Can the eyes track and blink convincingly?
5. Can the mouth be driven by phoneme or viseme data?
6. Are the legal rights clear for shipping in a public web client?
7. Can the browser runtime load and animate it comfortably?

If the answer to any of the first five is no, the asset should not be the base Joi model.

---

## Immediate Asset Selection Rule

For Phase 1 and Phase 2, prioritize in this order:

1. close-up facial rig quality
2. silhouette quality in bust framing
3. eye and mouth control quality
4. browser runtime compatibility
5. secondary motion support
6. only then broader avatar feature completeness

For Joi, a perfect full-body avatar with a weak face is the wrong asset.

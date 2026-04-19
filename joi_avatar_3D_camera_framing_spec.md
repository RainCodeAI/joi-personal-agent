# Joi Avatar 3D Camera And Framing Spec

## Purpose

This document defines the default camera, composition, and viewport behavior for Joi's 3D avatar scene on the chat page.

The camera framing is not a cosmetic detail. It determines whether Joi reads as:

- a premium projected companion

or

- a 3D asset dropped into a dashboard

---

## Primary Camera Goal

Frame Joi as a cinematic projected bust with enough shoulder and upper chest presence to feel embodied, while keeping the face dominant.

---

## Default Composition

### Shot type

- close bust portrait
- visible upper chest, collarbone, shoulders, neck, and full head

### Eye-line target

- eyes should sit at roughly 42% to 46% from the top of the chamber

### Headroom

- maintain visible breathing room above the hair silhouette
- avoid cropping too tightly at the top

### Side margins

- shoulders should approach the frame edges without touching them
- silhouette needs dark negative space around it

### Vertical balance

- the bust should be visually centered within the projection chamber
- the face should feel slightly above the geometric midpoint

---

## Camera Orientation

### Default angle

- slight three-quarter softness is acceptable
- default should still read as mostly front-facing and emotionally direct

### Rotation bias

- yaw: minimal by default
- pitch: slightly flattering downward or neutral, never from below
- roll: effectively zero in idle

### Rule

The camera should flatter Joi the way a portrait lens would flatter a lead character.

It should never feel like a gameplay inspection camera.

---

## Lens Feel

### Target

Simulate a portrait-oriented lens feel:

- compressed enough to flatter the face
- not so narrow that the render feels stiff
- not so wide that the shoulders or chin distort

### Guidance

- avoid wide-angle perspective distortion
- prioritize elegance and intimacy over technical drama

---

## Panel Geometry Target

### Aspect ratio

Preferred avatar chamber ratios:

- desktop target: between `4:5` and `5:6`
- acceptable fallback: slightly taller than square
- avoid returning to `1:1` as the primary composition

### Chamber behavior

- taller chamber gives room for shoulders, headroom, and projection atmosphere
- width should support shoulder silhouette without making the face feel small

---

## Chat Layout Relationship

### Role in the page

- the avatar chamber is the emotional focal point of the right column
- it should feel visually heavier than a generic status card
- it should not dominate the entire page over the chat itself

### Layout principle

- conversation remains the functional primary area
- Joi remains the emotional primary area

That means:

- the chat panel owns width and task flow
- the avatar panel owns emotional attention

---

## Desktop Framing Rules

### Large desktop

- show full bust composition with atmospheric chamber depth
- preserve top and side breathing room
- do not zoom in so far that the shoulders disappear

### Standard desktop

- keep the same composition logic
- reduce chamber ornament before cropping the bust too tightly

### Small desktop / tablet

- preserve face readability first
- keep shoulders if possible
- if compression is required, reduce empty chamber depth before reducing embodiment

---

## Responsive Behavior

### Do

- scale chamber height first
- preserve eye-line and bust hierarchy
- preserve silhouette clarity

### Do not

- collapse back to a square portrait crop
- let the chamber become a thumbnail card
- recenter only the face while shoulders fall out of frame

---

## Motion Framing Rules

### Idle motion

- head drift must remain within the shot without feeling constrained
- breathing motion must not collide with chamber edges

### Speaking motion

- emphasis nods should stay inside the portrait composition
- gaze shifts should feel readable without requiring large camera moves

### Camera rule

The camera should be stable by default.

If the system needs constant camera movement to feel alive, the avatar motion system is underpowered.

---

## Lighting Relationship To Camera

### Primary read

- the face must remain readable in the default camera
- the hair and shoulders must support depth cues from the chosen angle

### Rim light behavior

- rim light should clarify silhouette from the camera position
- highlights must reinforce form, not wash it out

---

## Scene Layers Inside Frame

From front to back:

1. facial form and expression
2. hair silhouette and shoulder contour
3. subtle projection shimmer / scan treatment
4. chamber atmosphere and depth haze
5. outer frame / emitter structure

If the ordering feels reversed in practice, the scene will look fake.

---

## Camera Acceptance Checklist

The framing is correct if:

- Joi reads as a bust, not a head-only crop
- the eyes land slightly above center
- shoulders help sell presence
- the face dominates without flattening the form
- the chamber feels intentionally composed

The framing is wrong if:

- it looks like a profile image box
- the head is too low or too high in frame
- there is too much empty dead space above the head
- the shoulders disappear
- the camera feels wide-angle or "gamey"

---

## Default Implementation Guidance

For first implementation:

1. Build around a stable default camera only
2. Tune the scene until the static pose looks premium
3. Add idle motion
4. Add reactive gaze
5. Only then consider subtle camera variation

Any fancy camera behavior before that is likely compensating for a weaker asset or weaker motion language.

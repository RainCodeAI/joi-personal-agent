# Claude's Analysis: Making Joi's Avatar Smoother

## Current State (Post-Revert)

Joi is speaking and her mouth is moving again — good baseline. But the animation still feels **jumpy and a bit cartoonish**. Here's my breakdown of why, and how to fix it — this time **one step at a time** so we don't break what works.

---

## Why It Looks Jumpy

Three things create the "jumping" effect:

### 1. Hard Image Swaps
Each viseme is a full-face PNG (~1.2 MB). When the mouth changes, the **entire image** swaps out — even though only the mouth area is different. The eyes, hair, skin all "pop" slightly between frames because each PNG was generated independently, meaning subtle differences in shading, anti-aliasing, and pixel alignment across the full face.

### 2. Fixed-Speed Crossfade
The CSS transition is a flat `0.14s ease-in-out` for every viseme change. In real speech:
- Vowels should **linger** (mouth holds open for "ahhh")
- Consonants should **snap** (mouth flickers through "t", "d", "k")
- But right now everything transitions at the same speed

### 3. Synthetic Timeline Drift
The phoneme timeline is generated from text character-by-character with fixed durations (120ms vowels, 80ms consonants). Real speech has rhythm, emphasis, and pauses. The mouth moves at a robotically even pace while the audio flows naturally.

---

## Recommended Fixes (In Priority Order)

### Fix 1: Mouth-Only Overlay (BIGGEST WIN)

**Impact: Eliminates the "popping" entirely**

Right now every viseme PNG is the **full face**. If we split each asset into:
- **1 base face** (everything except the mouth region) — used as the fixed background
- **13 mouth-only PNGs** (just the mouth area, transparent everywhere else)

Then the expression layer stays rock-solid while only the small mouth region swaps. No more eye/hair/skin popping between frames.

**How to produce the mouth-only assets:**
1. Open each viseme PNG in any editor (Photoshop, GIMP, or even Canva)
2. Erase everything except the mouth/chin region
3. Export as PNG with transparency
4. The mouth images will be tiny (~50-100 KB instead of 1.2 MB), which also makes the page load *way* faster

**Code change needed:** Minimal — the dual-layer crossfade system already exists. We just change the mouth layer `src` from full-face PNGs to mouth-only PNGs. The expression layer continues showing the base face.

> [!TIP]
> This is by far the highest-impact change. The current full-face swap is the #1 reason it looks cartoonish. Everything else is polish.

---

### Fix 2: Variable Crossfade Speed (Phase 3, Done Right)

**Impact: Makes lips feel natural instead of mechanical**

The previous attempt at this (Phase 3) broke things because it used `setFadeSpeed()` to override CSS transitions inline, which interfered with the crossfade rendering. The safer approach:

**Use separate CSS classes instead of inline styles:**

```css
/* Slow crossfade for vowels — mouth holds open */
.mouth-layer.vowel-fade {{
    transition: opacity 0.20s ease-in-out;
}}
/* Fast crossfade for consonants — quick flicker */
.mouth-layer.consonant-fade {{
    transition: opacity 0.08s ease-in-out;
}}
/* Default */
.mouth-layer {{
    transition: opacity 0.14s ease-in-out;
}}
```

Then in the animation loop, toggle classes instead of overwriting `style.transition`:
```javascript
if (vowels.has(currentPh)) {
    mouthA.classList.add('vowel-fade');
    mouthA.classList.remove('consonant-fade');
} else {
    mouthA.classList.add('consonant-fade');
    mouthA.classList.remove('vowel-fade');
}
```

This is CSS-native and won't interfere with the opacity crossfade logic.

---

### Fix 3: Timeline-to-Audio Scaling (Phase 1, Done Safely)

**Impact: Mouth stops drifting out of sync with audio**

The previous Phase 1 attempt broke things because it was bundled with Phase 2 and 3. On its own, it's a safe change. The fix:

```python
# In say_and_sync(), AFTER generating phoneme_timeline:
try:
    with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
        audio_duration = wf.getnframes() / float(wf.getframerate())
    if phoneme_timeline and len(phoneme_timeline) > 1:
        raw_end = phoneme_timeline[-1][0]
        if raw_end > 0 and audio_duration > 0:
            scale = (audio_duration * 0.92) / raw_end
            phoneme_timeline = [
                (round(t * scale, 3), ph) for t, ph in phoneme_timeline
            ]
except Exception:
    pass
```

**Test this independently** before combining with other fixes.

---

### Fix 4: Smoother Transition Frames (Phase 2, Simplified)

**Impact: Removes the "teleporting mouth" effect between extreme shapes**

Instead of inserting `rest` frames (which can make the mouth flicker to neutral), use a **CSS blend duration** approach:

When jumping between extreme mouth shapes (e.g., wide "A" → closed "M"), extend the crossfade duration to 0.25s. This lets the browser blend between the two images smoothly rather than snapping.

```javascript
// In updateFrame(), when calculating next viseme:
const OPENNESS = { "rest": 1, "MB": 0, "A": 3, "O": 3, "E": 2, /* etc */ };
const jump = Math.abs((OPENNESS[currentPh] || 1) - (OPENNESS[lastPh] || 1));
if (jump >= 2) {
    // Big jump — use slower blend
    mouthA.classList.add('vowel-fade');  // 0.20s
} else {
    mouthA.classList.add('consonant-fade');  // 0.08s
}
```

This gets the Phase 2 benefit without inserting extra timeline entries.

---

### Fix 5: Idle Micro-Animations

**Impact: Makes Joi feel alive when not speaking**

Currently idle Joi just blinks (opacity dip). Add:
- **Subtle breathing**: Very slow vertical bob (2px, 4-second cycle via CSS animation)
- **Occasional micro-expression shifts**: Rare, tiny opacity shifts between Neutral and a soft smile
- **Parallax on mouse hover**: Slight image shift following the cursor (hologram effect!)

```css
@keyframes breathe {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-2px); }
}
.avatar-container {
    animation: breathe 4s ease-in-out infinite;
}
```

---

## Recommended Rollout Order

| Step | Fix | Risk | Effort |
|------|-----|------|--------|
| 1 | Mouth-only overlays | None (asset work) | Medium (image editing) |
| 2 | Variable crossfade via CSS classes | Low | Small (CSS + JS) |
| 3 | Timeline-to-audio scaling | Low | Small (Python only) |
| 4 | Smart transition blending | Low | Small (JS only) |
| 5 | Idle micro-animations | None | Small (CSS only) |

**Key rule going forward: Test each fix independently, commit, and verify before adding the next.**

---

## Long-Term: Canvas-Based Rendering

The ultimate smoothness upgrade would be switching from `<img>` crossfading to **HTML5 Canvas** rendering. Instead of swapping full images, you'd:

1. Load all mouth textures into an offscreen canvas
2. Use `globalAlpha` blending to smoothly interpolate between any two mouth shapes
3. Render the base face once, then composite the mouth region on top

This enables frame-perfect blending with zero CSS transition artifacts. But it's a bigger rewrite — save it for when the overlay approach hits its ceiling.

---

## Summary

The single biggest improvement is **Fix 1 (mouth-only overlays)**. It eliminates the full-face popping that makes it look cartoonish. Everything else is polish that adds up. The key lesson from the Phase 1-3 attempt: **always ship one change at a time and test it before stacking the next.**

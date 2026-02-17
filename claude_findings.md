# Joi Bug Findings & Next Steps

## Completed Fixes
- **Profile Save Crash** -- `autoincrement=True` added to all models
- **Empty/Gibberish Responses** -- Swapped DialoGPT for OpenAI Chat API (`gpt-4o-mini`)
- **Journal NameError** -- `route_request` replaced with `conversation_agent.generate_proactive_message()`
- **Blade Runner 2049 Moods** -- Playful, Devoted, Tender, Curious, Melancholic, Defiant
- **Avatar Wiring** -- All 20 PNGs mapped, OpenAI TTS (`nova` voice) integrated, dual-layer crossfade added

---

## Current Issue: Avatar Lip-Sync Feels Unnatural

### Root Cause Analysis

After reviewing the code, there are **three separate problems** causing the unnatural movement. Fixing any one helps, but fixing all three together is what will make it feel alive.

---

### Problem 1: Fake Phoneme Timeline (THE BIG ONE)

The `_text_to_phonemes()` method in `agent.py` (line 208) generates a phoneme timeline by scanning characters with fixed durations:
- Every vowel = 120ms
- Every consonant = 80ms
- Word gaps = 80ms

This timeline is completely **disconnected from the actual audio**. OpenAI's TTS speaks at a natural pace with pauses, emphasis, and rhythm -- but the mouth moves on a rigid, synthetic clock. The mouth finishes "speaking" at a different time than the audio does, and the rhythm never matches.

**Fix:** Use OpenAI's audio timestamps. When you request audio with `response_format="wav"`, you can also request word-level timestamps. Alternatively, we can **scale the phoneme timeline to match the actual audio duration** -- this is simpler and gets us 80% of the way there.

---

### Problem 2: Missing Transition Visemes

When the mouth jumps from a wide "ah" shape to a closed "M" shape, that's a huge visual leap. Real mouths pass through intermediate positions. The current 13 visemes are great, but there's no logic to insert transitional frames.

**Fix: Auto-insert rest frames.** Between any two visemes that are "far apart" (e.g., wide-open "A" to closed "MB"), briefly show the neutral/rest position as a transition. This creates the impression of the mouth closing and re-opening naturally instead of teleporting.

Here's the viseme "distance" concept:
- `A` (wide open) -> `MB` (closed) = far, needs a rest transition
- `A` (wide open) -> `O` (round open) = close, direct transition is fine
- `MB` (closed) -> `rest` (neutral) = close, fine

**Optional new assets that would help** (if you want to produce them):
1. **Half-open neutral** -- mouth slightly parted (between Neutral and any vowel)
2. **Slight smile** -- softer than Smile, for conversational warmth
3. These two alone would massively improve transitions

---

### Problem 3: No Duration Awareness in Visemes

Currently, every viseme fires and immediately starts crossfading to the next one. But in real speech:
- Vowels are **held** (the mouth stays open on "ahhh")
- Consonants are **quick** (the mouth flickers through "t", "d", "k")

The animation doesn't distinguish between these, so everything has the same visual weight.

**Fix:** Add a minimum hold time for vowels before allowing the next crossfade. Vowel visemes hold for at least 100ms before transitioning; consonant visemes can transition immediately.

---

## Proposed Implementation Plan

### Phase 1: Scale Timeline to Audio Duration (Biggest Win)

**File: `agent.py` -- `_text_to_phonemes()` and `say_and_sync()`**

After generating speech audio, calculate the actual audio duration from the WAV header. Then scale the entire phoneme timeline proportionally so the last phoneme ends when the audio ends. This alone fixes the drift problem.

```
audio_duration = len(wav_data) / (sample_rate * channels * sample_width)
timeline_duration = timeline[-1][0]
scale_factor = audio_duration / timeline_duration
scaled_timeline = [(t * scale_factor, ph) for t, ph in timeline]
```

### Phase 2: Auto-Insert Transition Rest Frames

**File: `agent.py` -- `_text_to_phonemes()`**

After generating the timeline, run a post-processing pass that inserts brief `rest` frames between visemes that are "far apart" on a distance map. This prevents the teleporting-mouth effect.

### Phase 3: Vowel Hold in JS Animation

**File: `avatar_js.py`**

In the animation loop, add a minimum hold timer for vowel visemes. When a vowel fires, don't allow the next crossfade for at least 100ms even if the timeline says the next phoneme is sooner. This makes vowels feel held/sustained.

### Optional: New Asset Requests

If you'd like to produce 2 more images to further smooth things out:

| Asset | Description | Purpose |
|-------|-------------|---------|
| `Joi_HalfOpen.png` | Mouth slightly parted, between Neutral and any vowel | Transition frame between closed and open positions |
| `Joi_SoftSmile.png` | Subtle smile, less than full Smile | Warmer default for conversational idle |

These are nice-to-have, not required. The code fixes above will make the biggest difference.

### Verification

1. Restart Joi, go to Avatar page
2. Type a longer sentence (10+ words) and hit "Say & Animate"
3. Watch that the mouth movement ends roughly when the audio ends (Phase 1 fix)
4. Watch for smooth transitions between wide-open and closed shapes (Phase 2 fix)
5. Watch that vowels feel "held" rather than flickered (Phase 3 fix)

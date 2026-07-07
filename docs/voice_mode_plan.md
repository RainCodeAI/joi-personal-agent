# Voice Mode Plan

## Objective

Make spoken interaction with Joi fast, interruptible, and reliable enough to feel like a natural companion mode rather than a recorder bolted onto chat.

Voice should support push-to-talk first, then conversation mode, then optional wake word only after privacy indicators and interruption behavior are mature.

## Current Fit

What exists:

- Browser and native hotkey push-to-talk.
- Media session state model.
- Transcription endpoint.
- TTS and avatar sync path.
- Basic conversation mode and interruption handling.
- Latency fields in media session state.

Main gaps:

- No true streaming STT path.
- No robust local VAD beyond current browser energy detection.
- TTS is generated as a complete audio payload before playback.
- Device selection and echo handling need hands-on validation.
- Wake word is not ready yet.

## Coding Tasks

### Phase 1 - Device QA Closeout

- Validate push-to-talk in browser and WebView2.
- Validate conversation mode with real mic and speakers.
- Confirm interruption deletes stale assistant replies.
- Confirm latency metrics are populated.
- Add fixes from manual device findings.

### Phase 2 - Stronger VAD

- Evaluate WebRTC VAD, Silero VAD, or another local VAD path.
- Replace or augment energy-only detection.
- Add thresholds for quiet room, speaker playback, and headset use.
- Add diagnostics for speech detection confidence.
- Preserve push-to-talk behavior.

### Phase 3 - Streaming STT

- Add a WebSocket audio stream endpoint.
- Send browser AudioWorklet chunks to the backend.
- Emit partial and final transcript events.
- Start thinking only after final transcript for v1.
- Later evaluate speculative response start from stable partials.

### Phase 4 - Streaming TTS And Barge-In

- Stream TTS audio chunks when provider supports it.
- Keep a local fallback TTS path.
- Start audio playback before the full response is complete.
- Ensure detected user speech cancels generation and playback.
- Tie all playback to assistant turn IDs.

### Phase 5 - Wake Word Evaluation

- Evaluate a local wake-word engine.
- Keep wake word off by default.
- Add tray/hardware listening indicator.
- Discard non-trigger audio.
- Add physical or one-click mute.

## Manual Tasks

- Test with laptop mic.
- Test with headset mic.
- Test with speakers playing Joi's voice.
- Test in a quiet room and with background noise.
- Measure end-of-speech to first audible response.
- Interrupt Joi mid-sentence and confirm stale responses do not persist.
- Confirm privacy indicators are visible during recording/listening.

## Privacy Guardrails

- Wake word must be local only.
- Non-trigger audio should not be retained.
- Listening state must be visible.
- Ambient mode must be opt-in.
- Quiet hours, mute, and DND must apply to voice.

## Definition Of Done

- Push-to-talk is stable across browser and native shell.
- Conversation mode reliably detects speech and silence.
- Barge-in works without stale persisted replies.
- Latency is measured and visible in diagnostics.
- Wake word remains deferred until the base voice loop is dependable.

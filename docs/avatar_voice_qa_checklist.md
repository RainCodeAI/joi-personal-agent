# Avatar and Voice QA Checklist

Use this checklist before hardware testing so physical nodes extend a known-good Joi baseline.

## Required Checks

- [ ] Full avatar framing: full mode shows stable upper/full-body chamber framing without face, hair, or shoulders being cropped.
- [ ] Mini avatar framing: compact mode reads as a bust or half-body presence, with the face fully visible and no clipped controls.
- [ ] VRM fallback: preferred VRM loads from `frontend/public/avatar/models/vroid-joi/joi-vroid-v1.vrm`.
- [ ] GLB fallback: GLB fallback loads from `frontend/public/avatar/models/ai-girllike-it/source/009-3.glb` if VRM loading fails.
- [ ] Idle motion: idle breathing, posture, gaze, and expression motion remain subtle and continuous without jitter.
- [ ] Speech and lip-sync: spoken response starts, avatar mouth motion tracks the phoneme timeline, and playback settles back to idle.
- [ ] Voice interrupt: `Stop speaking` interrupts queued or active playback and records the media session as interrupted.
- [ ] Narrow viewport behavior: chat, avatar, mini mode, voice controls, and status text fit without overlap at phone-width layouts.

## Pass Criteria

Hardware work can begin when every required check passes on the current branch and any failure has a clear issue or follow-up note.

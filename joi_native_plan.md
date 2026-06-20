# Joi Native App Plan

Goal: make Joi feel like a native computer presence first, then gradually add desktop control behind explicit permissions.

## Guiding Principles

- Native presence before broad automation.
- Local-first by default.
- Every powerful desktop action goes through an allowlist.
- Destructive or external actions require explicit approval.
- Screen, microphone, file, and app access must be opt-in and visible.
- The LLM proposes actions; a narrow local broker executes only approved actions.

## Phase 1 - Native Presence Foundation

Status: Done.

Purpose: make Joi feel like an app that lives on the computer, not just a web page.

Scope:

- Harden and modernize the existing desktop tray launcher.
- Start and stop the FastAPI backend and Next.js frontend reliably.
- Generate or load the local API token and pass it to both processes.
- Add tray actions:
  - Open Joi
  - Restart Joi
  - Stop Joi
  - Quit
- Add a global hotkey for opening Joi.
- Add launch-on-startup documentation or a simple setup script.
- Keep all services bound to localhost.

Success criteria:

- Joi starts from one launcher.
- The tray icon shows whether the stack is running.
- Opening Joi from tray or hotkey works consistently.
- Quitting the tray app cleans up child processes.

## Phase 2 - Desktop Shell

Status: In progress.

Purpose: give Joi a polished native window while preserving the current web UI.

Candidate approaches:

- Short term: Python tray plus browser/window launch.
- Long term preferred: Tauri wrapper around the Next.js frontend.
- Fallback: Electron if Tauri blocks important desktop integration.

Scope:

- Evaluate Tauri vs Electron vs Python-only shell.
- Wrap the existing Next.js UI in a native window.
- Preserve local API token injection.
- Add window controls:
  - Show/hide
  - Always-on-top toggle
  - Start minimized
  - Restore last window size and position

Success criteria:

- Joi opens as a real desktop app window.
- The user does not need to manually start backend/frontend terminals.
- The app can run quietly in the background.

## Phase 2 Immediate Tasks

- [x] Add a lightweight Python desktop shell around the existing Next.js UI.
- [x] Preserve localhost API/frontend binding and API token propagation.
- [x] Persist native window size and position.
- [x] Add always-on-top and start-minimized shell settings.
- [x] Wire the tray launcher and `Ctrl+Space` hotkey to the native shell.
- [ ] Evaluate Tauri once the native window contract is stable.
- [ ] Decide whether packaged production Next.js output is required before installer work.

## Phase 2 Implementation Notes

- `desktop/window_shell.py` is the active Phase 2 shell.
- The shell uses `pywebview` when available and falls back to the browser when it is missing.
- `desktop/tray_app.py` now opens the native shell by default after the API and frontend are healthy.
- Tray actions include native window open, always-on-top open, browser fallback open, start, stop, restart, and quit.
- Runtime window state is stored in `data/desktop_shell.json`, which is ignored by git.
- Tauri remains the preferred long-term packaging direction, but the Python shell gives Joi native-window behavior without changing the web UI or token flow.

## Phase 3 - Voice Loop

Status: Core loop validated; automated hotkey/cancel/interrupt hardening complete, device-level QA remains.

Purpose: let Joi be spoken to naturally without overbuilding wake-word complexity too early.

Scope:

- Add push-to-talk first.
- Use the existing voice/transcription pipeline where possible.
- Show clear mic state in the UI and tray.
- Add interrupt/cancel behavior while Joi is speaking.
- Keep wake word as a later optional enhancement.

Success criteria:

- Pressing a hotkey records a short request.
- Joi transcribes, responds, and optionally speaks back.
- The user can stop recording or interrupt playback.

## Phase 3 Immediate Tasks

- [x] Reuse the existing browser `MediaRecorder` capture path instead of adding ambient microphone access.
- [x] Bridge native `Ctrl+Shift+Space` push-to-talk from the desktop shell into the web UI.
- [x] Preserve the existing `/api/v2/media/transcribe` transcription contract.
- [x] Keep explicit stop/interruption behavior through the current media session state.
- [x] Add a persisted `Voice sends` mode so clean voice prompts can submit automatically.
- [x] Add explicit recording cancellation and Escape-to-interrupt behavior.
- [x] Add a packaged-window QA pass once `pywebview` is installed in the active runtime.
- [x] Decide whether voice requests should auto-send after transcription or keep appending to the draft.
- [x] Manually validate click-to-record browser voice capture, transcription, auto-send, and assistant response.
- [x] Harden focused-web `Ctrl+Shift+Space` push-to-talk against modifier-first release and focus-loss keyup gaps.
- [x] Harden `Esc` cancellation while microphone permission/session setup is still pending.
- [x] Add automated native-shell hotkey dispatch coverage and frontend compile/type verification.
- [ ] Device-level validate focused-web `Ctrl+Shift+Space` push-to-talk with a real microphone.
- [ ] Device-level validate `Esc` cancel while recording and `Esc` interrupt during real spoken playback.

## Phase 3 Implementation Notes

- `frontend/components/voice-composer.tsx` remains the authoritative recorder.
- Focused web UI push-to-talk still uses hold `Ctrl+Shift+Space`.
- `desktop/window_shell.py` now registers the same global hotkey while the native shell is open and dispatches browser events into the web UI.
- The native hotkey does not start background listening by itself; it only triggers the visible web recorder in the active Joi window.
- `Voice sends` defaults on and is stored in browser local storage. Clean voice transcripts submit immediately; transcripts append for review when a draft or attachment is already present.
- `Esc` cancels an active recording without sending audio to transcription. When Joi is speaking, `Esc` interrupts playback through the existing media-session update path.
- Focused-web push-to-talk now stops on the Space keyup even if Ctrl/Shift were released first, and stops safely if the window loses focus while the key is held.
- Recording cancellation invalidates capture setup before and after microphone permission resolves, preventing a canceled permission request from starting a late recorder or transcription.
- Playback interruption is guarded while its local/API teardown is in flight, preventing repeated Escape keydown events from incrementing interruption state more than once per request.
- Conversation mode now keeps browser capture armed between turns. Detected speech stops active playback, aborts the in-flight browser chat request, and filters stale assistant events by client turn ID before submitting the new transcript.
- Media-session persistence now records the active assistant turn ID alongside voice mode, speech detection, interruption, and latency telemetry.
- Interrupted assistant replies are discarded from persisted chat history and cannot emit completion/avatar events or create pending approvals after barge-in.
- Voice telemetry now records model, TTS-generation, first-audio, and estimated end-to-end latency per turn, resetting counters before each response.
- Energy VAD requires consecutive speech frames and raises its speech threshold during assistant playback to reduce false barge-in from speaker feedback.
- Automated verification on 2026-06-19: 47 targeted Python tests passed across desktop shell, media-session persistence, and API contracts; frontend TypeScript checking passed.
- Phase B closeout verification on 2026-06-20: Python compilation, focused interruption/latency API tests, and frontend TypeScript checking passed.
- The frontend currently has no component/unit-test runner for synthetic `MediaRecorder`, keyboard, or audio playback events. Real microphone permission timing, focused-window key delivery, and audible playback interruption therefore remain device-level checks.
- Manual QA on 2026-05-27 confirmed click-to-record voice capture, browser `webm/opus` upload, transcription, voice auto-send, text chat, and provider-backed assistant responses.
- Runtime fixes from QA:
  - Frozen launches re-enter the packaged executable for API and native-window child modes instead of trying to execute bundled source files or `python -m`.
  - Packaged window state is stored under `%LOCALAPPDATA%\Joi` instead of PyInstaller's temporary extraction directory.
  - The PyInstaller build now requires and includes the standalone Next.js server, static assets, Node runtime, and pywebview backends.
  - Native-window creation/runtime failures fall back to the browser unless explicitly disabled.
  - Source launch scripts fail early with an actionable dependency message instead of silently falling back to a browser-only launch.
  - QA on 2026-06-18 confirmed pywebview 6.2.1 can create and close a native WebView2 window, shell state tests pass, and the production frontend compiles and typechecks.
  - Rebuilding the standalone frontend artifact from the OneDrive workspace remains environment-blocked by repeated Windows `UNKNOWN copyfile` errors inside `node_modules`; package builds now fail early when that artifact is absent instead of producing a broken launcher.
  - Data URL parsing accepts browser media parameters like `audio/webm;codecs=opus`.
  - Browser audio conversion uses bundled `imageio-ffmpeg` when system `ffmpeg` is unavailable.
  - Browser/file STT remains enabled even when server-side PyAudio microphone support is missing.
  - Vector memory retrieval skips cleanly when embeddings/index are unavailable so chat can continue.
  - The local QA runtime needs declared provider SDKs installed when cloud routes are configured.
- Wake word remains out of scope until the privacy model is stronger.

## Phase 4 - Safe Desktop Actions

Status: In progress.

Purpose: add useful native powers with low risk.

Initial action broker allowlist:

- `open_app`
- `open_url`
- `show_notification`
- `read_clipboard`
- `write_clipboard`
- `find_file`
- `open_file`
- `screenshot_once`

Scope:

- Build a local desktop action broker.
- Define typed request/response schemas.
- Add per-action permission checks.
- Add audit logging for every action.
- Surface actions in the approval/event UI.

Success criteria:

- Joi can open apps, links, files, and notifications through a controlled broker.
- Clipboard and screenshot access are opt-in.
- Every action is logged.

## Phase 4 Immediate Tasks

- [x] Add a typed local desktop action broker.
- [x] Start with low-risk allowlisted actions only: `open_url` and `show_notification`.
- [x] Require explicit confirmation before any desktop action executes.
- [x] Block non-http URL schemes for `open_url`.
- [x] Write JSONL audit records for every completed or blocked action.
- [x] Publish desktop action events through the existing realtime event bus.
- [x] Add approval UI integration for proposed desktop actions.
- [ ] Add opt-in clipboard and screenshot actions after the broker contract is proven.

## Phase 4 Implementation Notes

- `app/desktop_actions.py` owns the Phase 4 broker.
- `POST /api/v2/desktop/actions` is local-only and typed through `DesktopActionRequest`.
- The first broker allowlist contains only `open_url` and `show_notification`.
- `open_url` accepts absolute `http` and `https` URLs only; `file:`, `javascript:`, shell commands, and arbitrary app launches are blocked.
- Audit records are stored in `data/desktop_action_audit.jsonl`, which is ignored by git.
- The chat sidebar now exposes a safe desktop action review panel. Users stage the exact payload first, then explicitly run or cancel it.

## Next Session - Recommended Tasks

1. Finish the remaining Phase 3 device-level QA checks:
   - Hold focused-web `Ctrl+Shift+Space`, speak, release, and confirm it follows the same voice auto-send path.
   - Start recording, press `Esc`, and confirm it cancels without submitting audio.
   - Confirm spoken reply playback works, then press `Esc` during playback and confirm interruption.
2. Run a quick browser pass for the Phase 4 Safe actions panel:
   - Stage and run `show_notification`.
   - Stage and run `open_url` with an `https` URL.
   - Confirm blocked behavior for a non-http URL.
   - Confirm `desktop.action.completed` / `desktop.action.blocked` events appear in the feed.
3. Harden the local runtime/dev launcher:
   - Ensure the active Python runtime installs all declared voice/provider dependencies.
   - Make API/frontend startup avoid ad hoc elevated launch steps.
   - Re-check token-protected launch through `StartJoiNative.bat`.
4. Decide the next safe broker expansion:
   - Prefer `read_clipboard` / `write_clipboard` only after adding visible opt-in state and tests.
   - Defer `screenshot_once` until the screen-awareness privacy controls are designed.
   - Keep `open_app`, `open_file`, and filesystem writes out until the approval review surface is stronger.

## Phase 5 - Screen Awareness

Purpose: let Joi understand current context without constant surveillance.

Scope:

- Start with manual screenshot analysis: "Joi, look at this."
- Add active-window metadata only if explicitly enabled.
- Add privacy controls:
  - Never capture
  - Ask each time
  - Allow while app is active
- Avoid continuous screen monitoring until the permission model is proven.

Success criteria:

- Joi can analyze a user-requested screenshot.
- The user can see and change perception settings.
- No background screen capture happens without opt-in.

## Phase 6 - Medium-Risk Computer Skills

Purpose: help with real work while still keeping control narrow.

Candidate skills:

- Create files in approved folders.
- Move or rename files in approved folders.
- Draft emails.
- Draft calendar events.
- Summarize selected text or clipboard content.
- Search approved folders.

Scope:

- Extend broker schemas.
- Add folder allowlists.
- Require approval for writes.
- Never send email or create calendar events without confirmation.

Success criteria:

- Joi can prepare useful work artifacts.
- The user reviews before anything leaves the machine or changes important files.

## Phase 7 - High-Risk Actions With Approval

Purpose: support powerful actions without giving the model raw control.

High-risk actions:

- Send email.
- Create/update/delete calendar events.
- Delete files.
- Run shell commands.
- Install software.
- Change system settings.

Rules:

- Always require explicit approval.
- Show the exact action, target, and arguments.
- Prefer dry-run previews.
- Commands must be allowlisted or manually approved.
- No arbitrary shell execution from model text.

Success criteria:

- Joi can propose powerful actions.
- The user remains the final authority.
- The audit trail explains what happened and why.

## Phase 8 - Startup, Packaging, and Updates

Purpose: make Joi installable and maintainable as a real native app.

Scope:

- Package the desktop shell.
- Include backend/frontend startup.
- Store config in a predictable user data directory.
- Add backup/export for memories and settings.
- Add update strategy.
- Document recovery steps.

Success criteria:

- Joi can be installed, launched, updated, and removed cleanly.
- User data is not mixed with application binaries.
- Backups are straightforward.

## Phase 9 - Optional Wake Word and Ambient Mode

Purpose: add "always available" behavior only after privacy and reliability are solid.

Scope:

- Evaluate local wake-word engines.
- Keep wake word disabled by default.
- Add visual/audio indicators when listening.
- Add quiet hours and do-not-disturb integration.

Success criteria:

- Wake word works locally and reliably enough to be useful.
- The user can fully disable ambient listening.

## Phase 1 Immediate Tasks

- [x] Review the existing `desktop/tray_app.py`.
- [x] Ensure token generation and propagation are robust.
- [x] Add process health checks.
- [x] Improve tray menu state.
- [x] Add clean shutdown behavior.
- [x] Test local launch from a single command.

## Phase 1 Implementation Notes

- `desktop/tray_app.py` is the active Phase 1 launcher.
- `StartJoiNative.bat` starts the tray launcher from one command.
- The tray launcher now generates or loads a local API token and passes it to both backend and frontend child processes.
- The launcher waits for API and frontend health before opening Joi.
- The tray menu reports running, partial, or stopped state and exposes start, stop, restart, open, and quit actions.
- Shutdown now terminates the launched process trees instead of only the direct parent processes.

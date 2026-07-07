# Runtime Reliability Plan

## Objective

Make Joi dependable enough to leave running as an always-on desktop companion.

The app should start cleanly, recover from common failures, avoid duplicate instances, expose health clearly, and behave predictably outside the OneDrive workspace.

## Current Fit

What exists:

- FastAPI backend.
- Next.js frontend.
- Native tray/window shell.
- Startup scripts.
- Diagnostics and health endpoints.
- Child-process watchdog foundations.
- Launch-on-login scripts.
- Manual QA checklist.

Main gaps:

- Non-OneDrive packaging and soak testing still need completion.
- Full-day runtime behavior needs validation.
- Crash recovery and restart limits need hands-on verification.
- Startup shortcut behavior needs manual confirmation.
- Runtime state persistence needs periodic audit.

## Coding Tasks

### Phase 1 - Non-OneDrive Workspace Validation

- Move active development to the `C:\dev` copy.
- Reinstall Python and Node dependencies if needed.
- Run backend tests with local temp paths.
- Run frontend typecheck and build.
- Confirm no code path relies on OneDrive-specific paths.

### Phase 2 - Launch And Single Instance

- Validate `StartJoi.bat`, `StartJoiNative.bat`, and related scripts.
- Confirm one instance owns the API/frontend/tray.
- Confirm second launch focuses the existing window.
- Confirm quit stops child processes.
- Add tests or script checks where practical.

### Phase 3 - Watchdog And Recovery

- Deliberately kill the API child process and confirm bounded restart.
- Deliberately kill the frontend child process and confirm bounded restart.
- Confirm failure states appear in tray/diagnostics.
- Confirm restart attempts do not loop forever.
- Persist enough state to recover gracefully.

### Phase 4 - Packaging

- Build packaged app outside OneDrive.
- Redirect build output to stable local paths if needed.
- Validate packaged API, frontend, diagnostics, settings, voice, screen capture, and camera permissions.
- Document packaging commands and failure workarounds.

### Phase 5 - Soak Test

- Run Joi for a full day.
- Record uptime, restart count, memory use, CPU use, and errors.
- Include one intentional API crash and one intentional frontend crash.
- Confirm no duplicate child processes are left behind.

## Manual Tasks

- Switch the repo/session to the `C:\dev` copy when home.
- Start Joi from the normal launcher.
- Test launch-on-login install and remove.
- Test tray show/hide/restart/quit.
- Test native window persistence.
- Test voice, camera, screen, and connectors in packaged mode.
- Keep notes on every crash or degraded diagnostic state.

## Guardrails

- Do not build/package out of OneDrive if it causes locks or sync crashes.
- Avoid background processes that survive after quit.
- Avoid silent failures; surface degraded state in diagnostics/tray.
- Keep local API bound to localhost unless explicitly changing deployment model.

## Definition Of Done

- Joi starts reliably from the normal launcher.
- Duplicate launches focus the existing app.
- API/frontend crashes are recovered or reported cleanly.
- Packaged app runs outside OneDrive.
- Full-day soak test passes with documented behavior.

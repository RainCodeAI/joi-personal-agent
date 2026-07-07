# Desktop Control Plan

## Objective

Expand Joi's ability to interact with the local computer while preserving a strict approval and audit boundary.

Desktop control should start with narrow, typed actions and grow only after previews, local confirmation, and verification are reliable.

## Current Fit

What exists:

- Desktop action broker.
- Current allowlist includes `open_url` and `show_notification`.
- Local-only request checks for desktop actions.
- Audit records for attempted actions.
- Native tray and window shell foundations.
- Manual screen capture path.

Main gaps:

- No general typed desktop action registry.
- No selected-region capture or active-window metadata contract.
- No safe file/folder operations through the desktop broker.
- No automation actions beyond URL/notification.
- No remote-safe policy distinction beyond local-only checks.

## Coding Tasks

### Phase 1 - Action Registry

- Define typed desktop action specs.
- Add risk levels: safe, sensitive, destructive.
- Require local approval for sensitive and destructive actions.
- Add action previews.
- Add audit tests for every action path.

### Phase 2 - Screen And Window Actions

- Add or harden:
  - `screenshot_once`
  - `capture_window`
  - `get_active_window_metadata`
  - `show_window`
  - `hide_window`
  - `focus_window`
- Keep raw screenshots transient.
- Add visible capture indicators.

### Phase 3 - File And App Actions

- Add safe actions:
  - open file picker
  - reveal file in Explorer
  - open approved folder
  - open app or URL from allowlist
- Avoid arbitrary path operations until the tool platform is stronger.
- Add path allowlists for any local file operations.

### Phase 4 - Automation Evaluation

- Evaluate whether to add browser automation, keyboard, or mouse actions.
- Prefer high-level actions over low-level clicks.
- Require explicit local approval for anything that changes state.
- Never allow model-generated arbitrary GUI automation without review.

### Phase 5 - Remote Policy

- Keep Telegram/remote desktop actions blocked in v1.
- Later allow only harmless actions such as `show_notification` if useful.
- Keep all local computer control decisions audited with surface and identity.

## Manual Tasks

- Test notification and URL opening.
- Test blocked URL schemes.
- Test screen capture indicators.
- Test show/hide/focus through native shell.
- Test actions while the window is hidden.
- Confirm audit records are written for success, blocked, and error cases.

## Security Guardrails

- No arbitrary shell commands.
- No arbitrary mouse/keyboard control.
- No destructive file operations without explicit local approval.
- No remote desktop control by default.
- All desktop actions need typed schemas and audit records.

## Definition Of Done

- Desktop actions have typed specs, previews, and audits.
- Screen/window actions work with visible consent indicators.
- Sensitive actions require local approval.
- Remote surfaces cannot control the desktop by default.
- Tests cover blocked and successful actions.

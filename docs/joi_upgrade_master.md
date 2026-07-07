# Joi — Master Upgrade Roadmap (reconciled 2026-07-06)

This is the single front door for Joi's upgrade planning. It reconciles the 10 capability plans, the higher-level roadmaps, and the specs in `docs/` against the actual codebase. Every status below is grounded in code or git history as of `a19d5b3` (HEAD, main). Where a plan doc and the code disagree, the code wins — see [Reconciliation notes](#reconciliation-notes).

## Where Joi is now

Joi is much further along than most of the planning docs admit. The backend (`app/`) is a full FastAPI v2 API with sessions/chat, memory search + **nightly consolidation with emotion-tagged salience** (`app/memory/consolidation.py`, `app/memory/store.py`, commits `a0e3ec8`, `d160f25`), a user-model layer with LLM dry-run synthesis and durable corrections (`app/user_model/`), an initiative service + scheduler with quiet-hours/DND/caps/spacing gating and diagnostics (`app/initiative/`), a context-event service with sanitized payloads, dedupe, commentary candidates and feedback (`app/context_events/service.py`), a desktop action broker allowlisted to `open_url` + `show_notification` with local-only checks (`app/desktop_actions.py`), an approvals queue (`app/orchestrator/security/approval.py`, exposed at `/api/v2/approvals`), Gmail/Calendar connectors (`app/tools/email_gmail.py`, `calendar_gcal.py`), an SSE realtime event layer (`/api/v2/events/stream`), and an MQTT hardware bridge + firmware contract (`app/hardware/`).

The frontend (`frontend/`) has a 2.5D hologram portrait avatar with expression layers and amplitude-gated 2D viseme lip-sync (`frontend/components/avatar/avatar-portrait.tsx`, commits `5101140`, `d4b881c`, `a19d5b3`), and — contrary to the voice plan — a **working app-wide "Hey Joi" wake-word ambient listening mode** mounted in the app shell (`frontend/components/ambient-listener-provider.tsx`, `frontend/hooks/use-ambient-listener.ts`, `frontend/lib/wake-word.ts`, commits `9f3978e`, `29bb82e`, `139141c`). The backend token is proxied server-side so it never reaches the browser (`frontend/app/api/backend/[...path]`, commit `ab2c6f3`). A native tray shell with a bounded-restart watchdog exists (`desktop/tray_app.py`).

The two biggest genuinely-open areas are: (1) **tool execution is still keyword-matched** — `ExecutorAgent` dispatches on literal phrases like `"check email"` (`app/orchestrator/agents/executor.py`), and `app/tools/types.py` has only a minimal `ToolSpec` (name/description/parameters — no risk level, approval flag, or registry); `app/tools/registry.py` does not exist. (2) **No remote surface exists at all** — zero Telegram code in the repo (`app/integrations/` absent). Voice works but is batch-mode end to end: no streaming STT (no WebSocket endpoints in `app/api/`), TTS is generated as a complete payload before a `tts.ready` event fires (`app/api/v2.py` ~line 1821).

## Capability status matrix

| Capability | Status | Evidence | Key remaining gap | Source doc |
|---|---|---|---|---|
| Avatar (2.5D portrait + expressions + 2D lip-sync) | Done | `frontend/components/avatar/avatar-portrait.tsx`; commits `5101140`, `d4b881c`, `a19d5b3` | lifeState-tinted stage (deferred in july5 plan); unified state vocabulary across surfaces | embodiment_plan, july5_plan |
| Wake word "Hey Joi" (app-wide ambient listening) | Done | `frontend/hooks/use-ambient-listener.ts`, `ambient-listener-provider.tsx` in `app-shell.tsx`; commits `9f3978e`, `29bb82e`, `139141c` | It is VAD + Whisper-transcribe + text match, not a dedicated low-power wake engine; battery/CPU cost unmeasured | voice_mode_plan (contradicted — see notes) |
| Voice: push-to-talk, transcription, TTS, interruption | Partial | `/api/v2/media/transcribe`, `app/tools/whisper_local.py`, `voice_elevenlabs.py`, `voice.py`; media session store `app/api/media_session.py`; commits `28d713c`, `091d871`, `7146030`, `daba53e` | No streaming STT (no WebSocket in `app/api/`), TTS is full-payload before playback, VAD is energy-only | voice_mode_plan |
| Memory consolidation ("sleep") + emotion-tagged recall | Done | `app/memory/consolidation.py`, `app/memory/store.py` (`_emotional_salience`, `emotion:` tags); commits `a0e3ec8`, `d160f25`; tests `tests/test_consolidation.py`, `test_emotion_memory.py` | Retrieval-quality eval fixtures; forget/hide UI flows | memory_user_model_plan |
| User model + synthesis + corrections | Partial | `app/user_model/{synthesis,llm_synthesis,store}.py`; `/api/v2/user-model/*` routes; commits `91fa766`–`f32bf35` | LLM synthesis is dry-run only (writes disabled per `session_synthesis_spec.md` and `llm_synthesis.py` docstrings); review UI depth | memory_user_model_plan, session_synthesis_spec, user_model_contract |
| Initiative service + scheduler + policy gating | Done (core) | `app/initiative/{service,policy,scheduler? via app/scheduler}.py`; candidates: greeting, return-after-absence, late-night, silence, memory follow-up; `can_emit` gates quiet hours/DND/focus/caps/spacing; `/api/v2/initiative/diagnostics`; `tests/test_initiative.py` | Phase 10 quality gate (relevance/novelty scoring) is **design-only** — no scoring code in `app/initiative/` | initiative_policy_plan, initiative_quality_gate_spec |
| Context event service + commentary gate + feedback | Done (core) | `app/context_events/service.py` (sanitize, dedupe, TTL, commentary candidates, useful/wrong/too_much/never feedback); `/api/v2/context/events*`; commit `76bac52`; `tests/test_context_events.py` | Calendar/active-window/hardware sources not normalized in; no context-snapshot endpoint | context_awareness_plan |
| Camera perception (MediaPipe, local assets) | Done (core) | commits `2b235b1`, `7b5117d`, `43e7876`, `2dff0a4`, `12be79e` (tray camera suspend); `app/api/perception_policy.py` | Runs in browser surface; richer signals (objects/gesture) out of scope for now | context_awareness_plan, always_on_companion_upgrade_plan |
| Desktop action broker | Partial | `app/desktop_actions.py` — allowlist exactly `{open_url, show_notification}`, local-only check, audit; `/api/v2/desktop/actions`; commit `85bb641` (tests) | No typed action registry, no screen/window/file actions, no risk levels | desktop_control_plan |
| Tool execution platform | Planned (prototype only) | `app/orchestrator/agents/executor.py` — keyword matching (`"check email" in lower`); `app/tools/types.py` minimal `ToolSpec`; **no `app/tools/registry.py`** | Entire typed registry / proposal contract / risk levels / verification | tool_platform_plan |
| Gmail / Calendar connectors + approvals | Done (core) | `app/tools/email_gmail.py`, `calendar_gcal.py`; approvals: `app/orchestrator/security/approval.py`, `/api/v2/approvals/{id}/approve|deny`, local-approval check `_require_local_approval_request` in `app/api/v2.py`; `tests/test_tools_email.py`, `test_calendar_tools.py` | Draft-first workflows, scope splitting, post-execution verification | tool_platform_plan |
| Realtime event layer (SSE) | Done | `/api/v2/events` + `/events/stream` in `app/api/v2.py`; `app/api/realtime.py`; envelope per `realtime_event_layer.md` | WebSocket transport (only if streaming voice needs it) | realtime_event_layer |
| Runtime reliability (tray, watchdog, single instance) | Partial | `desktop/tray_app.py` (watchdog thread, `_restart_allowed` bounded-restart history); Start scripts; repo already lives at `C:\dev\joi` (plan's Phase 1 done); `tests/test_desktop_shell.py`, `test_runtime_persistence.py` | Packaged-build validation and full-day soak test are manual work not evidenced in repo | runtime_reliability_plan |
| Hardware bridge (MQTT) | Partial | `app/hardware/{bridge,mqtt_bridge,schemas}.py`; `/api/v2/hardware/contract`; contract doc `hardware_firmware_contract.md` | No firmware/node in repo; presence telemetry → context events not wired | ambient_presence_plan, embodiment_plan |
| Unified state vocabulary / life state | Partial | `app/avatar/life_state.py` (`LifeStateEngine`, `/api/v2/avatar/life-state`); `joi.state.changed` SSE event | Not the single canonical vocabulary across tray/avatar/hardware/media session yet | embodiment_plan, joi_master_presence_roadmap |
| Telegram / remote access | Planned (nothing built) | `grep -r telegram app/` → no hits; no `app/integrations/` | Everything; but it only needs to be an API client of `/api/v2/chat` | telegram_bot_plan, remote_access_plan |
| Security hardening pass | Done (recent) | commits `c89102c`, `54f0299`, `fc637bb`, `ab2c6f3` (token proxy, prompt guard, vault, SSE) | Ongoing | (not in any plan doc) |

## Dependency-ordered roadmap

The proposed Foundation→Reach ordering mostly survives contact with the code, with two refinements: (1) memory/context/initiative are further along than "middle tier" implies — what they need is the *quality gate*, which depends on nothing in Foundation; (2) Telegram v1 is genuinely self-contained (it is just a localhost API client) and can be pulled forward as an early win, exactly as remote_access_plan suggests.

### Tier 0 — Foundation (unblocks everything that acts)
- **Tool platform** (`tool_platform_plan.md`): the single highest-leverage gap. Replace keyword `ExecutorAgent` with `app/tools/registry.py` + typed `ToolSpec` (risk level, approval requirement), `ToolProposal`/`ToolPreview`/`ToolExecutionResult` models, and LLM-generated proposals validated against schemas. The approvals queue and connectors it needs **already exist** — this is a refactor plus a planner, not a greenfield build.
- **Runtime reliability** (`runtime_reliability_plan.md`): watchdog and bounded restarts exist in `desktop/tray_app.py`; remaining work is mostly manual validation (packaged build, soak test, launch-on-login). Do the soak test before adding more always-on features.
- **Unified state vocabulary** (`embodiment_plan.md` Phase 1): `LifeStateEngine` + `joi.state.changed` exist; consolidate media-session, tray, avatar, and hardware states onto the canonical list. Cheap, and both initiative delivery and hardware nodes depend on it.

### Tier 1 — Quality and depth (each independently shippable)
- **Initiative quality gate** (`initiative_quality_gate_spec.md`): the spec is written, the insertion point (`candidate builder → quality gate → can_emit`) is real in `app/initiative/service.py`, and zero scoring code exists. This is the difference between "Joi speaks on timers" and "Joi notices things."
- **User-model write enablement** (`session_synthesis_spec.md`): LLM synthesis is dry-run with audit records (`f32bf35`, `6b8b125`). Graduate to write-enabled once dry-run output is reviewed — gate behind the existing correction store.
- **Context source normalization** (`context_awareness_plan.md` Phases 2–3): fold calendar and hardware presence into context events; add the context-snapshot endpoint.
- **Voice hardening** (`voice_mode_plan.md` Phases 2–4): streaming STT (needs a WebSocket endpoint — the first one in the codebase) and chunked TTS. Skip Phase 5 (wake-word evaluation) — it shipped.

### Tier 2 — Reach
- **Telegram v1** (`telegram_bot_plan.md` / `remote_access_plan.md` Phase 1): *pull-forward candidate.* Long-polling bridge as a localhost client of `/api/v2/chat`, allowlisted user IDs, read-only approvals reporting. Depends on nothing in Tier 0/1 for a conservative v1; benefits later from the tool platform for remote approvals.
- **Desktop control expansion** (`desktop_control_plan.md`): explicitly blocked on the Tier 0 tool/action registry — do not add actions to the current string-allowlist broker.
- **Hardware presence nodes** (`ambient_presence_plan.md`): bridge and contract exist; needs firmware + the unified state vocabulary.

## Reconciliation notes

**(a) Doc claims that are stale / contradicted by code:**
- `voice_mode_plan.md` says *"Wake word is not ready yet"* and schedules it as Phase 5 evaluation. **Wrong**: "Hey Joi" wake-word ambient listening is built, promoted to the app shell (every page), with wake chime/flash and mic-error retry UI (commits `9f3978e`, `29bb82e`, `139141c`; `frontend/hooks/use-ambient-listener.ts`). Caveat: it is a VAD+Whisper+text-match pipeline, not a dedicated wake engine, so the plan's Phase 5 concerns (indicator, mute, audio discard) still deserve a check — but the feature exists.
- `memory_user_model_plan.md` Phase 5 ("Harden nightly consolidation") reads as future work; nightly consolidation shipped (`a0e3ec8`, `app/memory/consolidation.py`, `/api/v2/memory/consolidate` manual trigger — which is exactly the "consolidate now" action the plan asks for). Emotion-weighted recall also shipped (`d160f25`).
- `always_on_companion_upgrade_plan.md` says desktop/screen awareness is "not implemented" and there is "no camera indicator in the native tray." Since then: screen-context tooling exists (`app/tools/screen_context.py`, `tests/test_screen_context.py`, Phase C commit `0b5ea2d`) and tray camera suspend controls landed (`12be79e`). The doc's overall lane framing predates the entire Phase A–E push (`a3ab183`…`d2e537c`).
- `july5_plan.md` marks Phase 2 (avatar model swap / layout flip) as pending, but the hologram-portrait direction shipped a different way (`5101140`, `d4b881c`) — the doc's Phase 2 is partially superseded.
- `embodiment_plan.md` "Current Fit" is roughly accurate but under-credits the life-state engine and `joi.state.changed` event, which already exist (`app/avatar/life_state.py`, `/api/v2/avatar/life-state`).

**(b) Overlaps / duplication:**
- `telegram_bot_plan.md` and `remote_access_plan.md` Phase 1 describe the same deliverable (remote_access even says "implement the plan in telegram_bot_plan.md"). Treat telegram_bot_plan as the implementation detail; remote_access_plan as the umbrella (identity abstraction, proactive delivery, PWA).
- `embodiment_plan.md` Phase 5 duplicates `ambient_presence_plan.md`; `joi_master_presence_roadmap.md` restates both plus the avatar plan. The master roadmap's shared event vocabulary overlaps `realtime_event_layer.md`'s event names — these should converge on one list.
- `initiative_policy_plan.md` Phase 2 (candidate quality scoring) duplicates `initiative_quality_gate_spec.md` — the spec is the more developed version.
- `always_on_companion_upgrade_plan.md` overlaps nearly every capability plan; it is a useful narrative but should be read as historical context, not status.

**(c) Things the docs plan that already exist:**
- Approvals queue with local-only enforcement (`_require_local_approval_request`), audit records, and persistence — tool_platform_plan lists these correctly as existing, but desktop_control_plan's Phase 1 "require local approval" is partly done.
- Initiative diagnostics endpoint, suppression reason codes, and retryable-vs-permanent suppression distinction (`ContextEventService.is_retryable_suppression`) — initiative_policy_plan Phase 1 items that are already coded.
- Context feedback actions (`useful/wrong/too_much/never_comment`) — planned in context_awareness_plan Phase 4, already implemented in `app/context_events/{service,feedback}.py`.
- Manual "consolidate now" (`POST /api/v2/memory/consolidate`) — memory plan Phase 5 item, done.
- Server-side token proxy — no doc planned it; it shipped in `ab2c6f3` (`frontend/app/api/backend/[...path]`).

**Unverified** (not asserted as Done anywhere above): packaged-build health, launch-on-login behavior, full-day soak results, real-device voice QA beyond what commits `daba53e`/`091d871` claim — these are manual-validation items with no repo artifact to check.

## Gaps the docs don't cover

- **Cost / model-routing plan.** The project is budget-conscious, yet no doc addresses which model handles chat vs. synthesis vs. consolidation vs. initiative scoring, or per-day token budgets. Config has the seams (`model_chat`, `model_ollama`, `gguf_model_path`, `router_timeout` in `app/config.py`, plus commit `fc637bb` "model split") but no policy. Initiative + consolidation + synthesis are all background LLM consumers — an always-on Joi can quietly burn money.
- **Data lifecycle / backup.** SQLite + Chroma + JSON runtime state accumulate indefinitely; `scripts/backup_db.sh` exists but no retention or migration plan (only `groom_memory` in `app/scheduler/jobs.py`).
- **Evaluation harness for the companion behaviors.** Synthesis has a validation harness (`5d4986c`); memory retrieval, initiative quality, and wake-word false-positive rate have none.
- **Wake-word privacy/power accounting.** Since wake word shipped ahead of plan, nothing documents its mic-always-on implications, CPU cost of continuous VAD, or the audio-discard guarantee.
- **Doc lifecycle itself.** Nothing marks docs as superseded; this file should carry that role (see index below).

## Recommended next 3–5 concrete steps

1. **Build the typed tool registry** (`app/tools/registry.py` + upgraded `ToolSpec` with risk level/approval requirement, `ToolProposal` models) and route `ExecutorAgent`'s existing email/calendar handlers through it before adding the LLM planner. Highest leverage; everything acting (desktop expansion, remote approvals) is blocked on it. Keep the current keyword paths as deterministic fallbacks, per the plan.
2. **Implement the initiative quality gate** from `initiative_quality_gate_spec.md` — the insertion point in `app/initiative/service.py` (before `can_emit`) is ready, and it directly improves the always-on experience with zero new surface area.
3. **Ship Telegram v1** per `telegram_bot_plan.md` — standalone long-polling process in `app/integrations/`, allowlisted IDs, localhost-only API, read-only approvals reporting. Self-contained, high daily-life value, and it exercises the API contract remotely without any new attack surface.
4. **Run the reliability soak** (runtime_reliability_plan Phases 3–5): kill-and-recover tests against the existing `tray_app.py` watchdog, then a full-day run with notes. This is validation, not construction — cheap and it de-risks everything above.
5. **Write the missing cost/model-routing policy** (one page): which provider/model per background job (consolidation, synthesis, initiative scoring, commentary), local-model fallbacks via the existing Ollama/GGUF seams, and a daily budget check in diagnostics.

## Source docs index

Capability plans (`docs/`):
- `telegram_bot_plan.md` — Telegram bridge implementation detail (nothing built yet).
- `remote_access_plan.md` — remote-surface umbrella; Phase 1 = telegram_bot_plan.
- `tool_platform_plan.md` — typed tool registry replacing keyword execution (accurate; still the biggest gap).
- `desktop_control_plan.md` — desktop action expansion (blocked on tool platform).
- `runtime_reliability_plan.md` — packaging/watchdog/soak (watchdog exists; validation pending).
- `initiative_policy_plan.md` — initiative audit/scoring/channels (core done; scoring not).
- `memory_user_model_plan.md` — memory taxonomy/UI/retrieval (consolidation done; UI/eval pending).
- `context_awareness_plan.md` — context event normalization (service done; sources uneven).
- `voice_mode_plan.md` — voice hardening (**stale on wake word**; streaming still open).
- `embodiment_plan.md` — unified state vocabulary + avatar/tray/hardware (partial).

Higher-level (read as narrative/history, statuses superseded by this doc):
- `joi_master_presence_roadmap.md` — app + avatar + hardware merge.
- `always_on_companion_upgrade_plan.md` — lane-by-lane snapshot, predates Phase A–E work.
- `ambient_presence_plan.md` — ESP32/Pi hardware node build.
- `july5_plan.md` — UI vibe pass (Phase 1 done; Phase 2 partially superseded by the hologram portrait).

Specs (still authoritative for their contracts):
- `session_synthesis_spec.md` — synthesis write contract (dry-run stance still true in code).
- `user_model_contract.md` — user model item shape/sections.
- `initiative_quality_gate_spec.md` — Phase 10 scoring design (unimplemented).
- `realtime_event_layer.md` — SSE envelope + event names (implemented).
- `hardware_firmware_contract.md` — MQTT topics/states (bridge implemented; no firmware).

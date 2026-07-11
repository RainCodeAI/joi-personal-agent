# Phase 10 Initiative Quality Gate Spec

Status: rollout stages 1–2 implemented (2026-07-11)
Last updated: 2026-07-11

## Implementation Status (2026-07-11)

Stages 1–2 of the staged rollout are built:

- `app/initiative/quality.py` — `InitiativeQualityGate` scores an *evidence-bound*
  candidate on relevance/timing/recency/novelty/safety (weights and 0.75 threshold
  from this spec), with a hard safety floor (0.70) and hard-suppression rules
  (missing/generic/unattributable evidence, repeat topic within 7 days). Scoring
  is deterministic — no LLM — per the non-goals.
- `app/initiative/emission_memory.py` — `InitiativeEmissionMemory` persists one
  record per emitted evidence-bound initiative, keyed by `topic_key` and scoped
  by `session_id`, for repeat suppression and the feedback loop (`user_response`).
- Feedback loop is wired end to end: the chat path calls
  `InitiativeService.register_user_reply(session_id)` on every user message, which
  marks the most recent in-window initiative `engaged` and ages stale unanswered
  ones out to `ignored`. (`negative` — hide/delete/disable — is still future, but
  its scoring effect is already implemented.)
- Feedback is consumed back into scoring: over a 30-day window, a run of `ignored`
  emissions of a type with no engagement multiplies the score by a dampening
  factor (pushing borderline candidates under threshold); a single `engaged`
  clears it; any `negative` hard-suppresses the type. Surfaced as
  `feedback_factor` on each `QualityScore`.
- The gate is wired into `InitiativeService` as a pre-policy step: it runs before
  the existing policy gate and only for candidates that carry `evidence`. Timer-
  driven candidates (daily greeting, absence return, etc.) carry no evidence and
  bypass it entirely, so legacy behavior is unchanged. Controlled by
  `INITIATIVE_QUALITY_GATE_ENABLED` (default on).
- `memory_followup` is the first evidence-bound consumer: its builder now attaches
  a `memory` source excerpt + `observed_at` + `topic_key`, so it is scored and
  repeat-suppressed by the gate.
- Diagnostics: `InitiativeService.diagnostics()` includes a `quality_gate` block
  (threshold, safety floor, weights, recent decisions).

Stage 3 started with `calendar_heads_up` (2026-07-11) — the first *new* evidence-
bound candidate type, added diagnostics-only:

- `InitiativeService.build_calendar_heads_up_candidate` builds an evidence-bound
  candidate for the soonest calendar event in a lead window (default 15–90 min),
  with `source_type="calendar"`, the event title as excerpt, and a per-event
  `topic_key`. Events are supplied by callers/tests or read from the read-only
  calendar tool when authenticated.
- It is deliberately **not** in the default `INITIATIVE_ALLOWED_TYPES`, so the
  policy gate suppresses live emission (`initiative type disabled`) while the
  quality gate still scores it. Inspect via
  `POST /api/v2/initiative/calendar-heads-up` (emit=false), which returns the
  decision and the quality breakdown. Enabling live emission is a later flip:
  add `calendar_heads_up` to `INITIATIVE_ALLOWED_TYPES` and wire a scheduler tick.

Not yet implemented (later stages): the other context-triggered families
(`open_loop_followup`, `project_checkin`, `mood_pattern_notice`,
`win_acknowledgement`), a live scheduler tick for `calendar_heads_up`, and the
user-model-confidence / hidden-deleted-correction hard rules — those depend on
Phase 9 synthesis being trustworthy (Rollout Gates below). The scorer and
emission memory are ready to receive them.

## Original Design


## Purpose

Phase 10 turns initiative from timer-driven checks into context-driven attention. Joi should only speak unprompted when the candidate references something real, arrives at a plausible moment, and has not become repetitive.

This is not an implementation plan for enabling proactive user-model writes. Phase 9 synthesis remains dry-run/audit-first until output quality and correction safety are trustworthy.

## Current Baseline

The current initiative stack already has:

- candidate builders in `app/initiative/service.py`
- central policy gating through `InitiativeService.can_emit`
- emission and suppression records in `InitiativeStore`
- scheduler ticks for daily greeting, absence return, late-night check-in, prolonged silence, and memory follow-up
- diagnostics through `/api/v2/initiative/diagnostics`

The Phase 10 quality gate should sit between candidate construction and the existing policy gate:

```text
candidate builder -> quality gate -> existing policy gate -> emit/suppress
```

The existing policy gate remains authoritative for DND, focus, quiet hours, daily limit, spacing, media state, expiry, and disabled initiative types.

## Candidate Types

Phase 10 introduces context-triggered candidate families:

| Type | Source | Example | Minimum evidence |
| --- | --- | --- | --- |
| `open_loop_followup` | synthesis records, recent chat, user model open loops | "You said you still had to follow up with Dana. Did that happen?" | exact evidence excerpt plus no later closure |
| `project_checkin` | active project items, recent memory | "Haven't heard about the FastAPI backend in a bit. Still the main thread?" | active project, no recent mention, no hidden/deleted correction |
| `mood_pattern_notice` | mood logs, repeated mood signals | "Something's been lower than usual lately. Want to talk, or leave it alone?" | repeated low signal over multiple sessions, no diagnosis |
| `win_acknowledgement` | recent wins | "That MQTT bridge win sounded like it mattered." | positive outcome from prior session, next-day or later timing |

All context-triggered candidates must carry structured evidence:

```json
{
  "type": "open_loop_followup",
  "session_id": "default",
  "message": "Draft text...",
  "reason": "open loop from synthesis record",
  "evidence": {
    "source_type": "synthesis_record",
    "source_id": "record-id",
    "excerpt": "I still haven't written the review checklist.",
    "observed_at": "2026-04-30T..."
  }
}
```

## Quality Score

Before the existing policy gate sees a candidate, Phase 10 computes a `QualityScore`.

```json
{
  "candidate_id": "uuid",
  "initiative_type": "open_loop_followup",
  "total": 0.82,
  "relevance": 0.9,
  "timing": 0.8,
  "recency": 0.75,
  "novelty": 0.8,
  "safety": 0.9,
  "threshold": 0.75,
  "decision": "pass"
}
```

### Dimensions

- **Relevance**: candidate references a concrete user fact, project, open loop, win, or mood pattern with evidence.
- **Timing**: current moment is plausible based on activity, quiet hours, calendar/presence later, and session state.
- **Recency**: source evidence is neither too fresh to need follow-up nor stale enough to feel random.
- **Novelty**: similar initiative has not been emitted recently.
- **Safety**: candidate avoids diagnoses, pressure, unsupported interpretations, hidden/deleted items, and sensitive extrapolation.

Initial weights:

| Dimension | Weight |
| --- | ---: |
| relevance | 0.30 |
| timing | 0.20 |
| recency | 0.15 |
| novelty | 0.20 |
| safety | 0.15 |

Default threshold: `0.75`.

Any safety score below `0.70` suppresses the candidate regardless of total score.

## Hard Suppression Rules

The quality gate suppresses candidates before policy gating when:

- evidence is missing, generic, or not attributable
- source item is hidden/deleted by user correction
- candidate repeats a similar message emitted in the last 7 days
- candidate depends on a user-model item below confidence `0.75`
- candidate makes a diagnosis, personality judgment, relationship interpretation, or prediction
- candidate asks for emotional labor immediately after user disengagement
- candidate is based only on small talk or assistant text

## Emission Memory

Add a durable initiative memory record before enabling Phase 10 triggers:

```json
{
  "id": "uuid",
  "type": "project_checkin",
  "topic_key": "active_projects:fastapi-backend",
  "source_ids": ["record-id"],
  "message": "Haven't heard about the FastAPI backend in a bit.",
  "quality_score": 0.83,
  "emitted_at": "2026-05-01T...",
  "user_response": "engaged|ignored|negative|unknown"
}
```

`topic_key` is required for repeat suppression. Similarity can start with deterministic keys (`section_key:normalized_label`) before semantic similarity is added.

## Feedback Loop

Track user response after initiative:

- **engaged**: user replies with substantive text within a short window
- **ignored**: no reply before next normal interaction or timeout
- **negative**: user hides/deletes the referenced item, disables a type, or says the initiative was unwelcome
- **unknown**: ambiguous or interrupted

Use feedback to adjust future scores by type and topic:

- repeated ignored `project_checkin` lowers novelty/timing for that topic
- negative feedback suppresses that topic/type combination until user re-enables it
- engaged feedback allows the type to keep its default weight, not exceed safety thresholds

## Diagnostics

Diagnostics must show both passed and suppressed candidates:

```json
{
  "candidate": {...},
  "quality_score": {...},
  "policy_decision": {
    "allowed": false,
    "suppressed_reason": "daily limit reached"
  },
  "final_decision": "suppressed"
}
```

The UI should expose:

- candidate type
- source evidence
- quality dimension scores
- hard suppression reason, if any
- existing policy suppression reason, if any
- recent similar emissions
- feedback state

## Rollout Gates

Phase 10 implementation should not start until:

1. Phase 9 synthesis diagnostics have been reviewed against real sessions.
2. Synthesis records are reliable enough to inspect source evidence and skipped status.
3. Hidden/deleted user-model corrections are consistently respected by synthesis and prompts.
4. A read-only diagnostics surface can show candidate quality decisions before any automatic emission.

Implementation rollout should be staged:

1. Add quality scorer and diagnostics-only candidate evaluation.
2. Add emission memory and repeat suppression.
3. Add one low-risk candidate type, likely `win_acknowledgement`, with `emit=false` diagnostics first.
4. Only then allow controlled emission through the existing policy gate.

## Non-Goals

- No automatic user-model writes.
- No proactive initiative from unvalidated synthesis.
- No medical, psychological, or relationship inference.
- No broad increase in daily initiative limits until repeat suppression and feedback tracking exist.
- No LLM-generated initiative text without evidence-bound templates or strict validation.

# Phase 10 Initiative Quality Gate Spec

Status: design only
Last updated: 2026-04-30

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

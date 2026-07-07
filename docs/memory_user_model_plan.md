# Memory And User Model Plan

## Objective

Make Joi's memory feel coherent, useful, and respectful.

Joi should remember durable facts, preferences, active projects, important people, emotional patterns, recurring worries, and explicit corrections. She should also know what not to infer, mention, or retain.

## Current Fit

What exists:

- Memory store with chat history and memories.
- User model sections and correction store.
- Explicit share detection.
- Memory search and recent memory APIs.
- Memory consolidation plan and tests.
- Profile, mood, habits, goals, contacts, and related data models.

Main gaps:

- User model synthesis is still conservative and partly contract-oriented.
- Memory confidence and lifecycle need more UI support.
- Forget/hide/confirm flows need to be easy and trusted.
- Project/open-loop memory could be more structured.
- Memory retrieval quality needs recurring evaluation.

## Coding Tasks

### Phase 1 - Memory Taxonomy

- Define memory types clearly:
  - episodic
  - semantic
  - preference
  - relationship
  - project
  - correction
  - do-not-mention
- Add migration or mapping if existing records need normalization.
- Add tests for memory type filtering.

### Phase 2 - User Model Hardening

- Expand user model synthesis from chat and profile data.
- Track confidence, evidence count, first seen, last seen, lifecycle, and user confirmation.
- Respect corrections during future synthesis.
- Add anti-duplication checks.
- Add dry-run and write-enabled modes.

### Phase 3 - Review And Correction UI

- Improve the user model panel for confirm, edit, hide, delete, and add.
- Show evidence summaries without exposing too much raw transcript.
- Add "never bring this up" support.
- Add memory deletion and retention controls.

### Phase 4 - Retrieval Quality

- Add a memory retrieval evaluation fixture set.
- Test project continuity, personal preference recall, and emotional context recall.
- Prevent over-retrieval of stale or irrelevant memories.
- Add recency plus importance weighting.

### Phase 5 - Consolidation

- Harden nightly consolidation.
- Produce durable summaries of active projects, open loops, recent emotional state, and important events.
- Keep consolidation auditable.
- Add manual "consolidate now" UI action.

## Manual Tasks

- Review the user model panel and correct wrong assumptions.
- Add a few explicit facts and confirm they appear correctly.
- Ask Joi about active projects after a restart.
- Ask Joi to forget or hide something and verify it stops surfacing.
- Test memory search with names, projects, and recurring concerns.

## Privacy Guardrails

- Never treat inferred emotional state as fact.
- Let the user correct, hide, or delete memory.
- Do not retain raw sensitive files or media unless explicitly enabled.
- Keep evidence summaries compact.
- Avoid bringing up sensitive memories unless relevant and welcome.

## Definition Of Done

- Joi maintains a useful, editable user model.
- Corrections affect future synthesis and responses.
- Memory retrieval improves continuity without feeling forced.
- Forget/hide/delete paths are tested.
- Consolidation can run safely and explain what changed.

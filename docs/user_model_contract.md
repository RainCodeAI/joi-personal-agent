# Joi User Model Contract

Status: Phase 9 contract with durable correction storage
Last updated: 2026-04-27

## Purpose

The user model is Joi's persistent, readable theory of the user. It is not a raw memory dump and it is not a private surveillance store. It is a structured layer that turns repeated, confirmed, or high-confidence signals into context Joi can use with restraint.

The first implementation must be contract-first:

- every inferred item carries evidence and confidence
- user corrections are first-class
- unconfirmed inferences must stay visibly provisional
- initiative may read from this model only after the initiative gate remains stable

## Relationship to Existing Profile

`/api/v2/profile` is the explicit profile and CRM-like surface: user-entered profile fields, moods, habits, goals, contacts, activities, sleep, and transactions.

`/api/v2/user-model` is the inferred companion context surface. It can include explicit profile data, but every item must say where it came from and whether it was confirmed by the user.

The model must not silently convert a guess into a fact.

## Sections

Initial section keys:

- `active_projects`: projects or workstreams that currently matter
- `recurring_worries`: concerns that appear across sessions
- `stated_goals`: goals the user explicitly stated or confirmed
- `important_people`: people the user mentions or marks as important
- `mood_trend`: recent emotional baseline and notable shifts
- `communication_preferences`: how the user prefers Joi to respond
- `recent_wins`: positive outcomes worth remembering
- `open_loops`: unresolved decisions, promises, or follow-ups
- `character_notes`: Joi's current read on the user's tone and state, written cautiously

## Item Shape

Each item must include:

- `id`: stable local identifier
- `label`: short display label
- `value`: readable sentence or short paragraph
- `category`: section-specific subtype
- `confidence`: `0.0` to `1.0`
- `evidence_count`: number of supporting observations
- `first_seen`: ISO timestamp or `null`
- `last_seen`: ISO timestamp or `null`
- `lifecycle`: `fresh`, `active`, `archive`, or `pinned`
- `user_confirmed`: whether the user explicitly confirmed it
- `hidden`: whether the user hid it from normal use
- `source_summary`: short explanation of where it came from
- `evidence`: minimal source references, not raw transcripts by default

## Evidence Shape

Each evidence record must include:

- `source_type`: one of `chat`, `memory`, `profile`, `mood`, `habit`, `goal`, `contact`, `calendar`, `notes`, `hardware`, `correction`, or `system`
- `source_id`: optional local id
- `summary`: short summary of the signal
- `observed_at`: ISO timestamp or `null`

Evidence should be enough for the user to understand why Joi believes something without exposing large raw logs in the response.

## Correction Contract

Future correction actions:

- `confirm`: mark an item as true
- `edit`: replace the value with the user's wording
- `hide`: keep the item stored but do not use it in prompts or initiative
- `delete`: remove the item
- `add`: add an explicit user-supplied item

Correction writes must be durable before the endpoint reports success. Until durable storage exists, correction requests should fail clearly rather than pretending to save.

## Inference Rules

Joi may infer:

- recurring projects, topics, and worries
- stated goals and decisions
- open loops from unresolved conversation threads
- communication preferences from explicit feedback or repeated corrections
- cautious character notes about current tone

Joi must not infer:

- medical diagnosis
- legal conclusions
- protected or sensitive identity attributes unless explicitly supplied by the user
- private-message content
- browser activity
- raw file contents unless explicitly shared
- emotion claims from weak signals like webcam or ultrasonic presence alone

## Initiative Use

Initiative can use user-model items only when:

- `initiative_enabled` is true
- the central initiative gate allows emission
- the item is not hidden
- confidence is high enough for the trigger type
- a similar initiative has not been emitted recently
- the message references the item gently and allows the user to dismiss it

Default minimum confidence for surfaced initiative should be `0.75`.

## API

### `GET /api/v2/user-model?user_id=default`

Returns the current user model in the contract shape. The Phase 9 foundation may return a read-only projection of explicit profile data while inferred storage is not implemented.

### `POST /api/v2/user-model/correct?user_id=default`

Accepts the correction request shape and persists the correction to `data/user_model_corrections.json`.

Supported actions:

- `confirm`: requires `item_id`; marks the item confirmed and pinned
- `edit`: requires `item_id` plus `label` or `value`; edits and confirms the item
- `hide`: requires `item_id`; marks the item hidden so it should not feed prompts or initiative
- `delete`: requires `item_id`; removes the item from the response projection
- `add`: requires `label` or `value`; adds a user-supplied pinned item

## Current Foundation

The initial API implementation is intentionally inference-off:

- it projects existing explicit profile, goals, contacts, moods, and preferences into the future user-model response shape
- every projected item is marked with source metadata
- corrections persist in a small JSON store and are merged into the response
- inference and session synthesis are not enabled yet

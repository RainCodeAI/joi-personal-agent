# Session Synthesis Spec

Status: Phase 9 design — stub implemented, writes disabled
Last updated: 2026-04-27

## Purpose

Session synthesis is the process of extracting structured user-model facts from conversation history and writing them as inferred items into the user model. It closes the gap between "Joi remembers what you said" and "Joi knows who you are."

Synthesis is not real-time and not user-facing. It runs after a session ends, quietly, in the background. The user sees its output through the user model surface, where they can confirm, correct, or hide anything it produced.

This spec defines what can be extracted, how confidence is assigned, how corrections take precedence, when synthesis runs, and what the write contract is.

---

## What Synthesis Is Not

- **Not surveillance.** Synthesis reads messages the user already sent. It does not read files, browser history, ambient sensors, or third-party data.
- **Not always-on inference.** Synthesis runs once per session, after it ends, not continuously.
- **Not certain.** Every item synthesis produces is provisional until the user confirms it. Unconfirmed items are marked visibly as inferred.
- **Not blocking.** Synthesis never delays a chat response. It is always async and out-of-band.
- **Not a replacement for explicit profile data.** Profile fields, goals, contacts, and habits entered by the user carry higher trust than anything synthesis infers.

---

## Inputs

| Input | Source | Notes |
|---|---|---|
| `session_id` | caller | the session to synthesise |
| `messages` | `memory_store.get_chat_history(session_id)` | ordered list of `ChatMessage` records |
| `existing_items` | `_user_model_response(user_id).sections` | current user model state to deduplicate against |
| `corrections` | `UserModelCorrectionStore.list_for_user(user_id)` | user corrections that block or override synthesis output |
| `user_id` | caller | default `"default"` |

Only user-role messages are analysed for content extraction. Assistant-role messages are read only to detect explicit acknowledgement patterns (e.g. the user confirming something Joi said).

---

## Extraction Methods

Two methods are defined. The stub implements method 1. Method 2 is the full implementation target.

### Method 1 — Pattern matching (stub, current)

Simple regex and keyword patterns applied to individual messages. Fast, deterministic, no LLM cost, testable. Lower recall — misses paraphrased or implicit signals. Used in the stub endpoint for design verification.

### Method 2 — LLM extraction (future)

A single structured extraction call made to the configured chat provider after the session ends. The prompt asks the model to return a JSON list of inferred facts with section keys, labels, values, and confidence. Higher recall, handles paraphrase, but costs tokens and requires async scheduling. Implemented in a follow-up pass once the stub output shape is validated.

---

## Extractable Facts Per Section

Synthesis may populate the following sections. It must never populate sections not listed here.

### `stated_goals`
Trigger phrases (user message): "my goal is", "i want to", "i'm trying to", "i'd like to", "i hope to", "one of my goals", "i'm aiming to"

Example input: "My goal is to ship the Joi hardware node by the end of the month."
Example output: label="Ship hardware node", value="User stated a goal to ship the Joi hardware node by end of month."

### `active_projects`
Trigger phrases: "i'm working on", "i'm building", "working on a", "the project", "this project", "i've been building"

Example: "I've been working on a FastAPI backend for weeks." → label="FastAPI backend", value="User is actively working on a FastAPI backend."

### `recurring_worries`
Trigger phrases: "i'm worried about", "i'm stressed", "it's stressing me", "i keep thinking about", "it's bothering me", "i'm anxious about", "keeps me up"

Example: "I keep thinking about whether the deadline is realistic." → label="Deadline concern", value="User expressed recurring worry about deadline realism."

### `open_loops`
Trigger phrases: "i still haven't", "i need to follow up", "i forgot to", "remind me", "i haven't done", "i should get around to"

Example: "I still haven't replied to that email." → label="Unreplied email", value="User noted an unresolved task: has not replied to an email."

### `important_people`
Pattern: capitalized proper names that appear in personal context ("my", "our", "with [Name]", "[Name] and I"). Requires at least two mentions across the session or explicit personal framing ("my friend", "my colleague", "my partner").

Must not trigger on: brand names, technology names, place names.

### `communication_preferences`
Trigger phrases: "i prefer when you", "i like when you", "please don't", "can you just", "i'd rather you", "stop saying", "less", "more concise"

Example: "Can you just be more direct?" → label="Directness preference", value="User prefers direct, concise responses."

### `recent_wins`
Trigger phrases: "i finally", "i finished", "i got the", "it worked", "i managed to", "i achieved", "we shipped", "i completed"

Example: "I finally got the MQTT bridge working." → label="MQTT bridge", value="User completed the MQTT bridge implementation."

### `mood_trend`
High-signal mood words in user messages, not inferred from sentence structure alone. Requires explicit emotional vocabulary.

Positive signals: "i'm excited", "feeling good", "really happy about", "pumped", "energised"
Negative signals: "exhausted", "burned out", "i'm frustrated", "feeling low", "drained", "struggling"

Neutral/ambiguous signals are dropped — mood inference requires explicit self-reporting.

---

## Confidence Assignment

| Signal strength | Description | Confidence |
|---|---|---|
| Explicit marker + clear subject | Trigger phrase present, subject parseable | 0.80 |
| Clear subject, no marker | 3+ mentions of same topic/name across session | 0.65 |
| Single mention with context | One occurrence, framing is personal | 0.55 |
| Weak or ambiguous | Trigger present but subject unclear | Drop |

The minimum confidence to emit a candidate is **0.55**. Items below this threshold are silently dropped.

Items with confidence below **0.75** are not eligible for initiative surfacing (this matches the global `min_confidence_to_surface` policy default).

---

## Deduplication

Before emitting a candidate, synthesis checks:

1. **Existing item label match**: if the existing user model already contains an item in the same section with a label that is a case-insensitive substring match of the candidate label (or vice versa), the candidate is skipped.
2. **Correction block**: if any correction with action `hide` or `delete` exists for the same item_id, the candidate is blocked. Synthesis must not re-add items the user has removed.
3. **Same-session duplicate**: if the same extraction pattern fires on multiple messages in the same session, collapse into one candidate with the highest-confidence instance and an evidence count reflecting the match count.

---

## Correction Precedence

User corrections are always authoritative. The precedence order is:

1. **User-added items** (`add` action): treated as confirmed, confidence 1.0, never overwritten by synthesis.
2. **User-confirmed items** (`confirm` or `edit`): synthesis may not overwrite them. If synthesis would produce the same item_id, it is skipped.
3. **User-hidden items** (`hide`): synthesis output for the same item_id is suppressed. The item remains hidden even if the session produces new evidence.
4. **User-deleted items** (`delete`): synthesis output for the same item_id is blocked. Synthesis may produce a new item for the same concept only if the item_id would differ and the new evidence is strong enough.

---

## Write Semantics

Synthesis has two modes:

### Dry-run (default, always active while `inference_enabled=False`)

- Runs the full extraction pipeline
- Returns the candidate list without writing anything to the user model or correction store
- Useful for: design verification, diagnostics, previewing what synthesis would produce

### Write mode (only when `inference_enabled=True`)

- Runs the full extraction pipeline
- Deduplicates against existing items
- Applies correction blocks
- Writes surviving candidates as inferred items to a `SynthesisRecord` store (to be defined)
- Returns the written items and the skipped count

The `inference_enabled` policy flag is `False` by default. Write mode must not be reachable while it is `False`.

---

## Timing and Triggers

When write mode is enabled, synthesis should run:

- When a session transitions to an idle or closed state (no new messages for N minutes)
- At most once per session (track synthesised session IDs to prevent re-runs)
- Never during an active exchange — synthesis must not compete with live response generation
- Via the initiative scheduler or a standalone background task, not inline in the chat handler

The initial trigger mechanism is an explicit `POST /api/v2/user-model/synthesize?session_id=X` call. Automatic post-session scheduling is a follow-up task.

---

## Output Shape

### `SynthesisCandidate`

```json
{
  "candidate_id": "stated_goals:abc123",
  "section_key": "stated_goals",
  "label": "Ship hardware node",
  "value": "User stated a goal to ship the Joi hardware node by end of month.",
  "confidence": 0.80,
  "inference_method": "pattern",
  "trigger_phrase": "my goal is",
  "source_excerpt": "My goal is to ship the Joi hardware node by the end of the month.",
  "source_message_role": "user",
  "source_message_index": 3,
  "blocked_by_correction": false,
  "duplicate_of_existing": false
}
```

### `SynthesisResponse`

```json
{
  "api_version": "v2",
  "session_id": "abc",
  "user_id": "default",
  "dry_run": true,
  "writes_enabled": false,
  "candidates": [...],
  "written_count": 0,
  "skipped_count": 2,
  "message_count": 14,
  "analysed_at": "2026-04-27T..."
}
```

---

## API Stub

### `POST /api/v2/user-model/synthesize`

Query parameters:
- `session_id` (required): the session to analyse
- `user_id` (default `"default"`): the user to synthesise for

Always returns candidates from the pattern-matching extractor. Dry-run review includes candidates skipped as duplicates or blocked by correction so tuning can inspect what the extractor found and why it will not be written. While `inference_enabled=False`, `dry_run` is always `true` and `written_count` is always `0` regardless of request body.

When write mode is eventually enabled, a `dry_run=false` query parameter will activate writes. This parameter is accepted but ignored while writes are disabled.

---

## What This Spec Does Not Cover

The following are deliberate out-of-scope items for this pass:

- **LLM extraction prompt**: designed separately once the output shape is validated against pattern results
- **Automatic post-session scheduling**: depends on session lifecycle events not yet defined
- **Multi-session aggregation**: recurrence counting across sessions is a follow-up after single-session extraction is stable
- **`character_notes` synthesis**: this section requires careful LLM judgment; it is excluded from pattern extraction
- **`mood_trend` aggregation**: single-session mood signal is low-value; multi-session aggregation is needed first

---

## Next Steps After This Spec

1. Run the stub endpoint against real sessions and review candidate output quality
2. Adjust confidence thresholds and trigger phrases based on actual output
3. Design the LLM extraction prompt against the validated output shape
4. Add `SynthesisRecord` durable store for written items
5. Wire automatic post-session trigger through the initiative scheduler
6. Enable write mode behind `inference_enabled=True` after LLM extraction is validated

## Validation Harness

Use `scripts/validate_synthesis.py` to run the extractor against curated realistic multi-turn sessions. The script exits non-zero when curated expected sections do not match actual extracted sections.

```powershell
.venv-test\Scripts\python.exe scripts\validate_synthesis.py
.venv-test\Scripts\python.exe scripts\validate_synthesis.py --real-db
.venv-test\Scripts\python.exe scripts\validate_synthesis.py --json --real-db
```

The curated cases cover active projects, goals, worries, important people, open loops, recent wins, mood signals, communication preferences, and small-talk negative controls. `--real-db` also samples saved sessions from `data/agent.db`.

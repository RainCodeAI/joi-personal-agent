# Session Synthesis LLM Prompt

Status: Phase 9 prompt contract, dry-run only
Last updated: 2026-04-28

## Purpose

This prompt is for a future dry-run LLM extraction pass that complements the deterministic regex extractor. It must find nuanced or indirect user-model candidates while staying conservative, evidence-bound, and correction-safe.

The LLM must not write to storage. It returns candidate JSON only. The local validator decides what survives.

## Allowed Sections

The LLM may emit candidates only for:

- `active_projects`
- `recurring_worries`
- `stated_goals`
- `important_people`
- `mood_trend`
- `communication_preferences`
- `recent_wins`
- `open_loops`

It must not emit `character_notes`, diagnoses, personality judgments, medical claims, relationship interpretations, or predictions.

## System Prompt

```text
You extract cautious user-model candidates from a single chat session.

Return JSON only. Do not explain.

You may infer only facts directly supported by user messages in the provided session. Do not infer from assistant messages except to understand conversational context. Do not guess. Do not diagnose. Do not label the user's personality. Do not create a candidate when the evidence is weak, generic, playful, or only small talk.

Allowed section_key values:
- active_projects
- recurring_worries
- stated_goals
- important_people
- mood_trend
- communication_preferences
- recent_wins
- open_loops

Every candidate must include:
- section_key
- label
- value
- confidence, from 0.0 to 1.0
- source_excerpt, copied from a user message
- source_message_index, the zero-based index of that user message in the provided messages array
- source_message_role, always "user"

Confidence rules:
- 0.90-1.00: explicit user instruction or direct statement with durable meaning
- 0.80-0.89: clear direct evidence with a specific subject
- 0.75-0.79: likely durable context, but less explicit
- below 0.75: do not emit

Use the shortest label that preserves meaning. Values should be one plain sentence. Source excerpts must be exact substrings from user messages. If no durable candidates are present, return {"candidates":[]}.
```

## Developer Prompt

```text
Analyze this session for durable user-model candidates.

Messages are provided as an array. Use each message's array index as source_message_index. Only user messages may be used as source evidence.

Return exactly this JSON shape:
{
  "candidates": [
    {
      "section_key": "active_projects",
      "label": "Short label",
      "value": "One sentence grounded in the user message.",
      "confidence": 0.82,
      "source_excerpt": "Exact substring from a user message.",
      "source_message_index": 3,
      "source_message_role": "user"
    }
  ]
}

Extraction guidance:
- active_projects: ongoing work or projects the user is actively building, writing, planning, debugging, or maintaining.
- recurring_worries: explicit concern, stress, anxiety, or repeated mental load. Do not diagnose.
- stated_goals: explicit aims, goals, intentions, or desired outcomes.
- important_people: named people with personal or work relevance. Do not emit generic roles without a name.
- mood_trend: explicit self-reported emotional state only.
- communication_preferences: how the user wants Joi to respond or behave.
- recent_wins: completed work, breakthroughs, shipped items, or positive outcomes.
- open_loops: unresolved tasks, follow-ups, reminders, or decisions.

Drop anything that is temporary, vague, generic, or unsupported by an exact user-message excerpt.
```

## Local Validation Rules

`app/user_model/llm_synthesis.py` validates all LLM output before it can be shown in dry-run synthesis:

- malformed JSON is dropped
- unsupported sections are dropped
- confidence outside `0.0..1.0` is dropped
- confidence below `0.75` is dropped
- missing label, value, source excerpt, or source index is dropped
- assistant-role evidence is dropped
- source excerpts that are not grounded in user messages are dropped
- existing-model duplicates are dropped
- user-hidden or user-deleted candidate IDs are dropped

## Example No-Op

Input user messages:

```json
[
  {"role":"user","content":"Hi Joi."},
  {"role":"user","content":"Just hanging around today."}
]
```

Expected output:

```json
{"candidates":[]}
```

## Example Candidate

Input user message:

```json
{"role":"user","content":"I'm building a prompt preview panel so I can see exactly what Joi receives."}
```

Expected output:

```json
{
  "candidates": [
    {
      "section_key": "active_projects",
      "label": "Prompt preview panel",
      "value": "User is building a prompt preview panel to inspect Joi's prompt context.",
      "confidence": 0.86,
      "source_excerpt": "I'm building a prompt preview panel so I can see exactly what Joi receives.",
      "source_message_index": 0,
      "source_message_role": "user"
    }
  ]
}
```

# Tool Platform Plan

## Objective

Replace prototype keyword-based tool execution with a typed, reviewable task platform.

Joi should be able to read context, draft actions, request approval, execute safely, and verify results. This is the foundation for email, calendar, files, notes, browser, desktop actions, and future connectors.

## Current Fit

What exists:

- `ExecutorAgent` can detect simple email/calendar intents.
- Gmail and Calendar connectors exist.
- Approval queue exists and persists.
- Tool call results are returned through `/api/v2/chat`.
- Audit records exist for tool and desktop action paths.
- Central typed registry for email, calendar, memory, files, desktop, and web tools.
- Canonical read/draft/write/destructive operations, risk levels, schemas, and approval flags.
- Typed proposal, preview, execution-result, and verification-result contracts.
- Registry-driven Gmail and Calendar dispatch for existing read/write capabilities.
- Exact local and redacted remote previews bound to immutable proposal fingerprints.
- Fifteen-minute, one-use approvals requiring both approval ID and proposal ID.
- Persisted approval migration with tamper, expiry, mismatch, and replay rejection.
- Deterministic provider idempotency for Gmail sends and Calendar event creation.
- Gmail/Calendar provider read-back verification; failed verification is an error.
- Constrained LLM proposal planning with strict registry/schema validation,
  `needs_input`, and deterministic keyword fallback on invalid/provider output.

Main gaps:

- Several registered tools do not yet have dispatcher handlers.
- Keyword extraction remains as the safe fallback when model planning fails.

## Coding Tasks

### Phase 1 - Tool Registry

Status: complete as of 2026-07-10. The keyword executor retains its existing
behavior and references the registry as the deterministic fallback foundation.

- Add `app/tools/registry.py`.
- Define a `ToolSpec` model with name, description, category, input schema, output schema, risk level, and approval requirement.
- Register existing Gmail, Calendar, memory, file, and desktop action tools.
- Add tests that all registered tools have stable schemas.

### Phase 2 - Tool Proposal Contract

Status: complete for the existing Gmail and Calendar write paths. Exact previews,
proposal IDs, argument fingerprints, expiry, and one-use consumption are enforced.

- Define Pydantic models for `ToolProposal`, `ToolPreview`, `ToolExecutionResult`, and `ToolVerificationResult`.
- Separate operations into:
  - `read`
  - `draft`
  - `write`
  - `destructive`
- Require exact previews for write/destructive actions.
- Require approval IDs for write/destructive execution.

### Phase 3 - Model Tool Planning

Status: complete for the registry proposal layer as of 2026-07-10. Likely tool
requests use strict JSON planning; unknown tools/fields, invalid types, malformed
output, and provider failures cannot execute and fall back to keyword rules.

- Replace keyword intent checks with typed tool proposal generation.
- Use the selected LLM to produce structured tool proposals.
- Validate proposals against tool schemas before displaying or executing.
- Return `needs_input` when required fields are missing.
- Keep deterministic fallback rules for common read-only commands.

### Phase 4 - Execution And Verification

Status: complete for Gmail and Calendar. Approved writes use proposal IDs as
stable provider idempotency keys and are read back after execution.

- Add idempotency keys for write actions.
- Execute approved tool proposals through one execution path.
- Verify results after execution when the provider supports it.
- Record result, verification, and audit metadata.
- Surface failed verification as an error, not as success.

### Phase 5 - Connector Hardening

- Split read and write scopes where provider APIs allow.
- Add draft-first Gmail and Calendar workflows.
- Add connector health and reconnect checks.
- Add revoke/disconnect verification.
- Add tests for unauthenticated and insufficient-scope behavior.

## Manual Tasks

- Reconnect Gmail and Calendar after scope changes.
- Test read-only email/calendar behavior.
- Test draft email, approve locally, and verify actual send.
- Test calendar event draft, approve locally, and verify event appears.
- Try incomplete requests and confirm Joi asks for missing fields.
- Try dangerous or vague requests and confirm Joi refuses or asks for clarification.

## Security Guardrails

- Never invent recipients, event times, file paths, or destructive intent.
- Never report success before provider confirmation.
- Do not execute write/destructive tools without explicit approval.
- Do not allow arbitrary shell commands as model-generated tools.
- Keep secrets in the vault or environment, never in prompt context.

## Definition Of Done

- Tools are registered with typed schemas.
- Write actions are previewed before approval.
- Approved actions execute through one audited path.
- Results are verified where practical.
- Tests cover invalid proposals, missing inputs, approval flow, and failed execution.

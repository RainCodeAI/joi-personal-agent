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

Main gaps:

- Tool selection is keyword-based.
- Arguments are extracted with simple patterns.
- No central typed tool registry.
- Read, draft, write, and destructive operations are not clearly separated.
- No idempotency or post-execution verification contract.

## Coding Tasks

### Phase 1 - Tool Registry

- Add `app/tools/registry.py`.
- Define a `ToolSpec` model with name, description, category, input schema, output schema, risk level, and approval requirement.
- Register existing Gmail, Calendar, memory, file, and desktop action tools.
- Add tests that all registered tools have stable schemas.

### Phase 2 - Tool Proposal Contract

- Define Pydantic models for `ToolProposal`, `ToolPreview`, `ToolExecutionResult`, and `ToolVerificationResult`.
- Separate operations into:
  - `read`
  - `draft`
  - `write`
  - `destructive`
- Require exact previews for write/destructive actions.
- Require approval IDs for write/destructive execution.

### Phase 3 - Model Tool Planning

- Replace keyword intent checks with typed tool proposal generation.
- Use the selected LLM to produce structured tool proposals.
- Validate proposals against tool schemas before displaying or executing.
- Return `needs_input` when required fields are missing.
- Keep deterministic fallback rules for common read-only commands.

### Phase 4 - Execution And Verification

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

# Initiative Policy Plan

## Objective

Let Joi occasionally speak first in a way that feels intentional, restrained, and useful.

Initiative is the difference between a passive chatbot and an ambient companion, but it is also the easiest area to make annoying. The policy must prioritize quiet, relevance, and user control.

## Current Fit

What exists:

- Initiative service and scheduler.
- Daily greeting, return-after-absence, late-night, prolonged silence, memory follow-up, and context commentary candidates.
- Quiet hours, DND, focus mode, daily caps, spacing, and media-state suppression.
- Context feedback actions.
- Realtime events and optional native notification path.

Main gaps:

- Context relevance scoring needs more tuning.
- Calendar, remote, hardware, and richer screen/camera context are not fully integrated.
- Proactive delivery while hidden or remote needs clearer policy.
- User preference learning from feedback is still early.

## Coding Tasks

### Phase 1 - Policy Audit

- Document every initiative type and its eligibility rules.
- Add tests for quiet hours, DND, focus mode, daily caps, spacing, and busy mic/playback.
- Ensure all suppressions include reason codes.
- Ensure retryable and permanent suppressions are distinct.

### Phase 2 - Candidate Quality Scoring

- Add scoring fields:
  - relevance
  - novelty
  - confidence
  - emotional appropriateness
  - interruption cost
  - user preference fit
- Require thresholds before candidate delivery.
- Store score breakdowns for diagnostics.

### Phase 3 - Delivery Channels

- Define delivery channels:
  - in-app chat
  - spoken line
  - native notification
  - Telegram/remote later
  - hardware state cue
- Add policy per channel.
- Avoid sending sensitive context to remote surfaces by default.

### Phase 4 - Feedback Learning

- Use `useful`, `wrong`, `too_much`, and `never_comment` feedback to tune categories.
- Add cooldowns by category and event kind.
- Add diagnostics for feedback effects.
- Add settings to reset feedback preferences.

### Phase 5 - Initiative Design Pass

- Rewrite templates and prompts so proactive messages are brief and restrained.
- Avoid therapy-speak and generic productivity nudges.
- Prefer small observations with obvious value.
- Ask one clear question only when useful.

## Manual Tasks

- Enable each initiative type one at a time.
- Test return after absence.
- Test late-night check-in.
- Test daily greeting.
- Test silence threshold.
- Test commentary feedback actions.
- Verify Joi stays quiet during DND, focus, mic recording, playback, and quiet hours.

## Guardrails

- Rare is better than frequent.
- No guilt-tripping the user for being away.
- No appearance commentary by default.
- No inferred emotional claims stated as fact.
- No remote proactive delivery of sensitive context without explicit opt-in.

## Definition Of Done

- Every initiative has clear eligibility and suppression reasons.
- Feedback changes future behavior.
- Delivery channels respect sensitivity and user state.
- Manual testing confirms Joi feels restrained rather than noisy.

# Joi v2 Realtime Event Layer

## Transport
- Initial transport: Server-Sent Events
- Stream endpoint: `GET /api/v2/events/stream`
- Bootstrap endpoint: `GET /api/v2/events`

SSE is the first transport because it fits the current FastAPI backend well and keeps the client contract simple during the Streamlit-to-Next.js migration. The event envelope is transport-stable so a future WebSocket layer can reuse the same payloads.

## Event Envelope

Every event uses this shape:

```json
{
  "api_version": "v2",
  "event_id": "uuid",
  "event": "message.completed",
  "source": "chat",
  "session_id": "session-123",
  "timestamp": "2026-04-17T12:00:00.000000",
  "payload": {}
}
```

## Current Event Names

- `session.created`
- `message.received`
- `response.started`
- `message.created`
- `message.completed`
- `approval.requested`
- `approval.resolved`
- `tool.completed`
- `avatar.state`
- `joi.state.changed`
- `tts.ready`
- `settings.updated`
- `heartbeat`

## Intended Client Behavior

- Open one SSE connection per active session when the chat view mounts.
- Use `GET /api/v2/events?session_id=...` for short backfill or reconnect bootstrap.
- Treat `message.completed` as the current assistant-final event.
- Treat `response.started` as typing/processing state.
- Treat `joi.state.changed` as the stable ambient-hardware command signal for LEDs and future node behavior.
- Treat `approval.requested` and `approval.resolved` as the approval UI driver.
- Treat `avatar.state` and `tts.ready` as separate signals so motion and playback can evolve independently.

## Near-Term Follow-Up

- Add true partial-text streaming from the provider path and emit `message.delta`.
- Emit tool lifecycle steps before/after execution rather than only completion.
- Move the event bus off process memory if Joi needs multi-worker deployment.

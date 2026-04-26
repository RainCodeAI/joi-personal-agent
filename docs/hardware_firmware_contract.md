# Joi Hardware Firmware Contract

Contract version: `ambient-v1`

The PC runtime owns Joi state. Firmware should subscribe to commands, render the requested LED state, and publish node telemetry/status. Firmware must not invent personality states.

## Topics

Default topic prefix: `joi`

Default node id: `desk`

Firmware subscribes to:

```text
joi/nodes/{node_id}/cmd/state
joi/nodes/{node_id}/cmd/config
```

Firmware publishes to:

```text
joi/nodes/{node_id}/telemetry/heartbeat
joi/nodes/{node_id}/status/health
joi/nodes/{node_id}/telemetry/presence
joi/nodes/{node_id}/telemetry/distance
joi/nodes/{node_id}/status/availability
```

The PC bridge publishes lifecycle status to:

```text
joi/bridge/status
```

## Allowed Runtime States

Allowed `state` values:

- `sleeping`
- `idle`
- `listening`
- `thinking`
- `speaking`
- `user_returned`
- `user_away`
- `error`

Allowed `led_state` values:

- `off`
- `calm_pulse`
- `attentive_pulse`
- `thinking_glow`
- `speaking_pulse`
- `gentle_wake`
- `amber_warning`

## PC-to-Node State Command

Topic:

```text
joi/nodes/{node_id}/cmd/state
```

Payload fields:

- `contract_version`: string, required, currently `ambient-v1`
- `state`: allowed runtime state, required
- `led_state`: allowed LED state, required
- `intensity`: number from `0.0` to `1.0`, required
- `transition_ms`: non-negative integer, required
- `mood`: string, required
- `source_event`: string, required
- `session_id`: string or null, required
- `reason`: string or null, required
- `updated_at`: ISO-8601 UTC string, required

Example:

```json
{
  "contract_version": "ambient-v1",
  "state": "thinking",
  "led_state": "thinking_glow",
  "intensity": 0.45,
  "transition_ms": 700,
  "mood": "neutral",
  "source_event": "response.started",
  "session_id": "session-chat",
  "reason": "assistant response in progress",
  "updated_at": "2026-04-24T22:30:00Z"
}
```

## Node-to-PC Heartbeat

Topic:

```text
joi/nodes/{node_id}/telemetry/heartbeat
```

Payload fields:

- `contract_version`: string, required, currently `ambient-v1`
- `node_id`: string, required
- `status`: string, required, allowed values `online`, `degraded`
- `uptime_ms`: non-negative integer, required
- `sequence`: non-negative integer incremented by firmware, required
- `published_at`: ISO-8601 UTC string, required
- `firmware_version`: string, optional
- `ip`: string, optional
- `rssi_dbm`: integer, optional

Example:

```json
{
  "contract_version": "ambient-v1",
  "node_id": "desk",
  "status": "online",
  "uptime_ms": 120000,
  "sequence": 42,
  "published_at": "2026-04-24T22:30:00Z",
  "firmware_version": "joi-presence-node-v1.0.0",
  "ip": "192.168.1.42",
  "rssi_dbm": -58
}
```

## Node-to-PC Health

Topic:

```text
joi/nodes/{node_id}/status/health
```

Payload fields:

- `contract_version`: string, required, currently `ambient-v1`
- `node_id`: string, required
- `status`: string, required, allowed values `ok`, `degraded`, `error`
- `uptime_ms`: non-negative integer, required
- `free_heap`: non-negative integer bytes, required
- `wifi_rssi_dbm`: integer, required
- `last_command_sequence`: non-negative integer or null, required
- `published_at`: ISO-8601 UTC string, required
- `firmware_version`: string, optional
- `last_error`: string or null, optional

Example:

```json
{
  "contract_version": "ambient-v1",
  "node_id": "desk",
  "status": "ok",
  "uptime_ms": 120000,
  "free_heap": 184320,
  "wifi_rssi_dbm": -58,
  "last_command_sequence": 42,
  "published_at": "2026-04-24T22:30:00Z",
  "firmware_version": "joi-presence-node-v1.0.0",
  "last_error": null
}
```

## Optional Presence Telemetry

Topic:

```text
joi/nodes/{node_id}/telemetry/presence
```

Payload fields:

- `contract_version`: string, required, currently `ambient-v1`
- `node_id`: string, required
- `present`: boolean, required
- `confidence`: number from `0.0` to `1.0`, required
- `event`: string, required, allowed values `user_returned`, `user_away`, `presence_changed`, `presence_sample`
- `published_at`: ISO-8601 UTC string, required
- `distance_cm`: non-negative number or null, optional
- `sample_count`: non-negative integer, optional

Example:

```json
{
  "contract_version": "ambient-v1",
  "node_id": "desk",
  "present": true,
  "confidence": 0.82,
  "event": "user_returned",
  "published_at": "2026-04-24T22:30:00Z",
  "distance_cm": 74,
  "sample_count": 5
}
```

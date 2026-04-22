# Joi Ambient Presence Plan

## Objective

Build Joi as one AI presence expressed through software and small physical nodes.

The PC remains the brain. ESP32 nodes act as lightweight physical presence nodes. Raspberry Pi boards remain available for later artifact and expansion work.

This is not a generic smart-home roadmap. The hardware should feel like subtle body language for Joi, not a dashboard of independent gadgets.

## Current Hardware Inventory

### Raspberry Pi

- 2 Raspberry Pi 3 boards
- multiple Raspberry Pi Zero / Zero-class boards
- PiSugar battery
- Pi cases and cooling cases
- Waveshare 2.13 inch e-paper HAT

### Microcontroller

- ESP32 starter kit
- ESP32 dev board
- breadboard
- jumper wires
- assorted LEDs and likely resistors
- HC-SR04 ultrasonic sensor
- small servo
- likely DHT temperature/humidity sensor
- joystick module
- keypad
- relay module

### Arduino

- Elegoo Uno R3
- prototyping shield
- assorted modules and wires
- 28BYJ-48 stepper motor and driver
- 16x2 LCD display
- 4-digit 7-segment display

## Strategy Decision

Use ESP32 as the first physical presence node.

Reasons:

- fast boot
- low power
- Wi-Fi capable
- good for LEDs, sensors, and servo control
- simpler than maintaining a full Pi OS node for first-pass ambient behavior

Keep Raspberry Pi 3 for later:

- e-paper desk artifact
- richer display node
- secondary room node
- local audio or experimental embodiment

Use Arduino only for isolated actuator experiments if useful.

## V1 Build Target

### Name

`Joi Presence Node v1`

### Hardware

- ESP32 dev board
- breadboard
- jumper wires
- one LED or small LED group
- resistor for LED, likely 220 ohm to 330 ohm
- HC-SR04 ultrasonic sensor
- optional later: small servo

### Electrical Notes

Many HC-SR04 modules output 5V on `ECHO`. ESP32 GPIO is 3.3V. Use a voltage divider or level shifter for the echo pin unless the exact sensor board is confirmed 3.3V-safe.

If servo motion is added, use external power if the ESP32 becomes unstable. Servo ground and ESP32 ground must be common.

## V1 Responsibilities

The node should:

- connect to Wi-Fi
- connect to local MQTT broker
- subscribe to Joi state commands
- render subtle LED behavior
- detect simple near/far desk presence
- publish meaningful presence changes
- publish availability and health

The node should not:

- make personality decisions
- speak independently
- spam raw distance data by default
- flash aggressively
- behave like generic RGB smart-home hardware

## Communication

### Protocol

Use MQTT.

Initial broker location:

- local Mosquitto broker on PC

Future broker options:

- PC-hosted broker remains primary
- Pi-hosted broker only if the ambient network needs to survive PC restarts

## MQTT Topic Structure

Use node-scoped topics from the start.

```text
joi/nodes/desk-01/cmd/state
joi/nodes/desk-01/cmd/config
joi/nodes/desk-01/telemetry/presence
joi/nodes/desk-01/telemetry/distance
joi/nodes/desk-01/status/availability
joi/nodes/desk-01/status/health
```

Optional app-level event topics:

```text
joi/events/user_returned
joi/events/user_away
joi/events/node_online
joi/events/node_offline
```

Prefer the node-scoped topics for firmware. Let the PC bridge convert node telemetry into app-level events.

## State Vocabulary

Initial state commands:

- `sleeping`
- `idle`
- `listening`
- `thinking`
- `speaking`
- `user_returned`
- `user_away`
- `error`

Example command payload:

```json
{
  "state": "idle",
  "intensity": 0.35,
  "mood": "neutral",
  "transition_ms": 1200
}
```

Example presence payload:

```json
{
  "present": true,
  "distance_cm": 74,
  "confidence": 0.82,
  "event": "user_returned"
}
```

## LED Behavior

Lighting should be subtle and ambient.

State mapping:

- `sleeping`: dim or off
- `idle`: slow calm pulse
- `listening`: slightly quicker pulse
- `thinking`: restrained flicker or slow transition
- `speaking`: brighter active pulse
- `user_returned`: brief gentle wake response
- `error`: low amber warning, not aggressive flashing

Avoid:

- rainbow effects
- rapid blinking
- attention-grabbing loops
- constant changes unrelated to Joi state

## Ultrasonic Presence Behavior

Use the HC-SR04 only for simple desk presence.

Detect:

- user near desk
- user away from desk
- user returned

Implementation rules:

- smooth multiple readings
- ignore impossible spikes
- require stable threshold crossing before changing state
- publish only state changes by default
- optionally publish raw distance at a slow debug interval

Suggested starting thresholds:

- near: under 120 cm for 3 stable samples
- away: over 170 cm or no stable reading for 10 to 20 seconds
- returned: transition from away to near

These should be tunable in config.

## Servo Behavior

Servo is not required for v1 bring-up.

Add only after LED and presence are stable.

Intended motion:

- neutral resting position when idle
- slight shift when listening
- small emphasis while speaking
- brief wake movement on return

Avoid:

- constant scanning
- large gestures
- novelty robot motion
- motor noise during quiet idle

## Firmware Architecture

Recommended folder:

```text
firmware/joi-presence-node/
  platformio.ini
  src/
    main.cpp
    config.example.h
    wifi_manager.cpp
    wifi_manager.h
    mqtt_client.cpp
    mqtt_client.h
    node_state.cpp
    node_state.h
    led_behavior.cpp
    led_behavior.h
    presence_sensor.cpp
    presence_sensor.h
    servo_behavior.cpp
    servo_behavior.h
```

Do not commit real Wi-Fi credentials. Commit `config.example.h`; keep local `config.h` ignored.

### Modules

`wifi_manager`

- connect to Wi-Fi
- reconnect if dropped
- expose connection state

`mqtt_client`

- connect to broker
- subscribe to command topics
- publish telemetry and status
- handle reconnects

`node_state`

- store current Joi state
- parse state payloads
- provide shared state to LED/servo modules

`led_behavior`

- non-blocking animation loop
- map Joi state to LED output
- handle smooth transitions

`presence_sensor`

- read ultrasonic distance
- smooth readings
- detect near/away/returned
- publish only meaningful events

`servo_behavior`

- optional
- non-blocking movement profiles
- state-to-position mapping

## PC-Side Integration

Add a small hardware bridge in Python/FastAPI rather than direct React-to-MQTT control.

Suggested package:

```text
app/hardware/
  __init__.py
  mqtt_bridge.py
  node_registry.py
  schemas.py
  events.py
```

Responsibilities:

- publish Joi state to MQTT
- subscribe to node telemetry
- normalize node messages into Joi events
- expose node health to diagnostics
- keep hardware feature behind a config flag

Config candidates:

- `ENABLE_HARDWARE_NODES`
- `MQTT_BROKER_HOST`
- `MQTT_BROKER_PORT`
- `MQTT_CLIENT_ID`

## Event Flow

```text
Joi state changes
  -> FastAPI/runtime state event
  -> hardware MQTT bridge
  -> joi/nodes/desk-01/cmd/state
  -> ESP32 LED/servo behavior

ESP32 detects returned user
  -> joi/nodes/desk-01/telemetry/presence
  -> hardware MQTT bridge
  -> Joi realtime event bus
  -> avatar gaze/posture and initiative logic
```

## Build Sprints

### Sprint 1 - ESP32 Bring-Up

Goal:

- flash firmware successfully
- connect to Wi-Fi
- print serial logs

Deliverables:

- firmware skeleton
- local `config.h`
- serial boot log

### Sprint 2 - MQTT And LED

Goal:

- ESP32 connects to Mosquitto
- subscribes to state command topic
- LED responds to state payloads

Deliverables:

- MQTT connectivity
- LED state machine
- availability heartbeat

### Sprint 3 - Ultrasonic Presence

Goal:

- detect near/away/returned without noisy spam

Deliverables:

- distance reader
- smoothing/debounce logic
- presence telemetry payloads

### Sprint 4 - Joi App Integration

Goal:

- Joi runtime sends state to node and receives presence events

Deliverables:

- Python MQTT bridge
- node registry
- realtime event conversion
- diagnostics entry for node health

### Sprint 5 - Servo Embodiment

Goal:

- add subtle motion only if it improves presence

Deliverables:

- servo wiring
- restrained motion mappings
- no blocking delay loops

## Future Expansion

### Second ESP32 Node

Use after `desk-01` is stable.

Possible roles:

- room corner ambient light
- doorway presence detector
- bedside subtle status node

### Pi 3 E-Paper Artifact

Use:

- Raspberry Pi 3
- Waveshare 2.13 inch e-paper HAT

Possible behavior:

- calm Joi phrase
- low-frequency ambient status
- daily prompt
- do-not-disturb or quiet-hours indicator

### Battery-Backed Node

Use PiSugar only after the basic node architecture is proven.

## First Implementation Checklist

- Choose ESP32 board and verify USB upload.
- Install PlatformIO or prepare Arduino IDE workflow.
- Install/run Mosquitto on PC.
- Build firmware skeleton with Wi-Fi and MQTT.
- Wire one LED with resistor.
- Test state command from PC to LED.
- Wire ultrasonic sensor with safe echo-level handling.
- Add presence smoothing.
- Add Python MQTT bridge behind a feature flag.

## Design Guardrails

- Subtle over flashy.
- Rare over constant.
- State-driven over random.
- Centralized intelligence over smart peripherals.
- Privacy and consent before richer sensing.
- One reliable node before multi-node expansion.

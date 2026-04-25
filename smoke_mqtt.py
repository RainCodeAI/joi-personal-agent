"""
Smoke test for MqttBridge.

Connects a subscriber before starting the bridge, fires a synthetic
joi.state.changed event through the real RealtimeEventBus, then asserts:

  1. Bridge connects and publishes joi/bridge/status = online (retained birth msg).
  2. The state command arrives on joi/nodes/desk/cmd/state.
  3. HardwareBridgeStore diagnostics reflect connected state and last_publish_at.
  4. Bridge shuts down cleanly and connection_state returns to disconnected.
"""

import asyncio
import json
import sys

import aiomqtt

from app.api.realtime import RealtimeEventBus
from app.hardware.bridge import HardwareBridgeStore
from app.hardware.mqtt_bridge import MqttBridge
from app.config import settings

BROKER = "127.0.0.1"
PORT = 1883
TIMEOUT = 8.0

settings.enable_hardware_nodes = True
settings.mqtt_broker_host = BROKER
settings.mqtt_broker_port = PORT
settings.mqtt_node_id = "desk"
settings.mqtt_client_id = "joi-smoke-test"
settings.mqtt_topic_prefix = "joi"


async def run_smoke_test() -> bool:
    store = HardwareBridgeStore()
    bus = RealtimeEventBus()
    bridge = MqttBridge(store, bus)

    received_birth: dict | None = None
    received_command: dict | None = None

    async def subscriber() -> None:
        nonlocal received_birth, received_command
        async with aiomqtt.Client(hostname=BROKER, port=PORT, identifier="joi-smoke-sub") as sub:
            await sub.subscribe("joi/bridge/status")
            await sub.subscribe("joi/nodes/desk/cmd/state")
            async for msg in sub.messages:
                topic = str(msg.topic)
                payload = json.loads(msg.payload)
                if topic == "joi/bridge/status":
                    received_birth = payload
                elif topic == "joi/nodes/desk/cmd/state":
                    received_command = payload
                if received_birth and received_command:
                    return

    sub_task = asyncio.create_task(subscriber())

    await bridge.start()
    # Give bridge a moment to connect and publish birth message
    await asyncio.sleep(0.5)

    # Fire a synthetic state change through the real event bus
    await bus.publish(
        "joi.state.changed",
        {
            "state": "thinking",
            "led_state": "thinking_glow",
            "hardware_command": {
                "contract_version": "ambient-v1",
                "state": "thinking",
                "led_state": "thinking_glow",
                "intensity": 0.45,
                "transition_ms": 700,
                "mood": "neutral",
                "source_event": "smoke.test",
                "session_id": None,
                "reason": "smoke test publish",
                "updated_at": "2026-04-23T00:00:00Z",
            },
        },
        source="smoke-test",
    )

    try:
        await asyncio.wait_for(sub_task, timeout=TIMEOUT)
    except asyncio.TimeoutError:
        sub_task.cancel()

    await bridge.stop()

    # --- Assertions ---
    passed = True

    def check(name: str, condition: bool, detail: str = "") -> None:
        nonlocal passed
        mark = "PASS" if condition else "FAIL"
        print(f"  [{mark}] {name}" + (f": {detail}" if detail else ""))
        if not condition:
            passed = False

    snapshot = store.get_bridge_snapshot()

    print("\nSmoke test results:")
    check("Bridge birth message received", received_birth is not None)
    check(
        "Birth status = online",
        received_birth is not None and received_birth.get("status") == "online",
        str(received_birth),
    )
    check("State command received on joi/nodes/desk/cmd/state", received_command is not None)
    check(
        "Command state = thinking",
        received_command is not None and received_command.get("state") == "thinking",
        str(received_command),
    )
    check(
        "Diagnostics last_publish_at set",
        snapshot.get("last_publish_at") is not None,
        str(snapshot.get("last_publish_at")),
    )
    check(
        "Bridge shut down cleanly (disconnected)",
        snapshot.get("connection_state") == "disconnected",
        snapshot.get("connection_state"),
    )

    print()
    return passed


if __name__ == "__main__":
    # SelectorEventLoop required on Windows for aiomqtt's add_reader/add_writer.
    # Use loop_factory (Python 3.12+) to avoid the deprecated set_event_loop_policy.
    factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    ok = asyncio.run(run_smoke_test(), loop_factory=factory)
    sys.exit(0 if ok else 1)

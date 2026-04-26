"""
Smoke test for MqttBridge.

Connects a subscriber before starting the bridge, fires a synthetic
joi.state.changed event through the real RealtimeEventBus, restarts the
bridge, then asserts:

  1. Bridge starts live and publishes joi/bridge/status = online.
  2. Bridge stops live and returns diagnostics to disconnected.
  3. Reconnect replays the current command.
  4. A non-default mqtt_node_id publishes to the expected node topic.
"""

import asyncio
import json
import sys
import uuid

import aiomqtt

from app.api.realtime import RealtimeEventBus
from app.hardware.bridge import HardwareBridgeStore
from app.hardware.mqtt_bridge import MqttBridge
from app.config import settings

BROKER = "127.0.0.1"
PORT = 1883
TIMEOUT = 8.0
NODE_ID = f"smoke-{uuid.uuid4().hex[:8]}"
CLIENT_ID = f"joi-smoke-test-{NODE_ID}"
SUBSCRIBER_ID = f"joi-smoke-sub-{NODE_ID}"
TOPIC_PREFIX = "joi"
BRIDGE_STATUS_TOPIC = f"{TOPIC_PREFIX}/bridge/status"
STATE_TOPIC = f"{TOPIC_PREFIX}/nodes/{NODE_ID}/cmd/state"

settings.enable_hardware_nodes = True
settings.mqtt_broker_host = BROKER
settings.mqtt_broker_port = PORT
settings.mqtt_node_id = NODE_ID
settings.mqtt_client_id = CLIENT_ID
settings.mqtt_topic_prefix = TOPIC_PREFIX


async def run_smoke_test() -> bool:
    store = HardwareBridgeStore()
    bus = RealtimeEventBus()
    bridge = MqttBridge(store, bus)

    received_birth: dict | None = None
    received_commands: list[dict] = []
    received_command_topics: list[str] = []
    stop_snapshot: dict | None = None
    reconnect_snapshot: dict | None = None
    subscriber_ready = asyncio.Event()

    async def subscriber() -> None:
        nonlocal received_birth
        async with aiomqtt.Client(hostname=BROKER, port=PORT, identifier=SUBSCRIBER_ID) as sub:
            await sub.subscribe(BRIDGE_STATUS_TOPIC)
            await sub.subscribe(STATE_TOPIC)
            subscriber_ready.set()
            async for msg in sub.messages:
                topic = str(msg.topic)
                payload = json.loads(msg.payload)
                if topic == BRIDGE_STATUS_TOPIC:
                    received_birth = payload
                elif topic == STATE_TOPIC:
                    received_command_topics.append(topic)
                    received_commands.append(payload)
                if received_birth and len(received_commands) >= 3:
                    return

    sub_task = asyncio.create_task(subscriber())
    await asyncio.wait_for(subscriber_ready.wait(), timeout=TIMEOUT)

    command, _changed = store.set_runtime_state(
        "thinking",
        source_event="smoke.test.seed",
        reason="smoke test reconnect replay seed",
    )

    await bridge.start()
    # Give bridge a moment to connect and publish birth message
    await asyncio.sleep(0.5)

    # Fire a synthetic state change through the real event bus
    await bus.publish(
        "joi.state.changed",
        {
            "state": "thinking",
            "led_state": "thinking_glow",
            "hardware_command": command,
        },
        source="smoke-test",
    )
    await asyncio.sleep(0.5)

    await bridge.stop()
    stop_snapshot = store.get_bridge_snapshot()

    await bridge.start()
    await asyncio.sleep(0.5)
    reconnect_snapshot = store.get_bridge_snapshot()

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
    check("Configured non-default mqtt_node_id", NODE_ID != "desk", NODE_ID)
    check("Bridge birth message received", received_birth is not None)
    check(
        "Birth status = online",
        received_birth is not None and received_birth.get("status") == "online",
        str(received_birth),
    )
    check(
        f"State command received on {STATE_TOPIC}",
        STATE_TOPIC in received_command_topics,
        str(received_command_topics),
    )
    check(
        "Command state = thinking",
        any(command.get("state") == "thinking" for command in received_commands),
        str(received_commands),
    )
    check(
        "Reconnect replayed current command",
        len([command for command in received_commands if command.get("state") == "thinking"]) >= 2,
        str(received_commands),
    )
    check(
        "Diagnostics last_publish_at set",
        snapshot.get("last_publish_at") is not None,
        str(snapshot.get("last_publish_at")),
    )
    check(
        "Bridge started live",
        reconnect_snapshot is not None and reconnect_snapshot.get("connection_state") == "connected",
        None if reconnect_snapshot is None else reconnect_snapshot.get("connection_state"),
    )
    check(
        "Bridge stopped live",
        stop_snapshot is not None and stop_snapshot.get("connection_state") == "disconnected",
        None if stop_snapshot is None else stop_snapshot.get("connection_state"),
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
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    ok = asyncio.run(run_smoke_test())
    sys.exit(0 if ok else 1)

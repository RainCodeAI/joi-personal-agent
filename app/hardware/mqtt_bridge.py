"""MQTT bridge: connects to the broker and publishes Joi state commands to hardware nodes."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Optional

from app.config import settings

if TYPE_CHECKING:
    from app.api.realtime import RealtimeEventBus
    from app.hardware.bridge import HardwareBridgeStore

try:
    import aiomqtt
    _AIOMQTT_AVAILABLE = True
except ImportError:
    _AIOMQTT_AVAILABLE = False

logger = logging.getLogger(__name__)

_RECONNECT_DELAY = 15


class MqttBridge:
    """
    Manages MQTT connection lifecycle and forwards joi.state.changed events to hardware nodes.

    - Disabled by default; activates only when settings.enable_hardware_nodes is True.
    - All MQTT errors are non-fatal: caught, logged, and retried after _RECONNECT_DELAY seconds.
    - HardwareBridgeStore diagnostics are updated on every connection state change.
    - V1 publishes to one configured node (settings.mqtt_node_id).
    - Bridge lifecycle messages use joi/bridge/status; node topics are reserved for ESP nodes.
    """

    def __init__(
        self,
        bridge_store: "HardwareBridgeStore",
        event_bus: "RealtimeEventBus",
    ) -> None:
        self._store = bridge_store
        self._event_bus = event_bus
        self._task: Optional[asyncio.Task[None]] = None
        self._running = False
        self._config_signature: tuple[Any, ...] | None = None

    def _settings_signature(self) -> tuple[Any, ...]:
        return (
            bool(settings.enable_hardware_nodes),
            settings.mqtt_broker_host,
            settings.mqtt_broker_port,
            settings.mqtt_client_id,
            settings.mqtt_topic_prefix,
            settings.mqtt_node_id,
        )

    async def start(self) -> None:
        """Start the bridge background task. No-op if the feature flag is off."""
        if not settings.enable_hardware_nodes:
            logger.debug("MQTT bridge disabled (enable_hardware_nodes=False)")
            self._store.set_connection_state("disabled")
            return
        if not _AIOMQTT_AVAILABLE:
            logger.error("aiomqtt is not installed; MQTT bridge cannot start")
            self._store.set_connection_state("error", "aiomqtt not installed")
            return
        if self._task is not None and not self._task.done():
            logger.debug("MQTT bridge already running")
            self._config_signature = self._settings_signature()
            return
        self._running = True
        self._config_signature = self._settings_signature()
        self._task = asyncio.create_task(self._run(), name="mqtt-bridge")
        logger.info(
            "MQTT bridge starting: %s:%d node=%s",
            settings.mqtt_broker_host,
            settings.mqtt_broker_port,
            settings.mqtt_node_id,
        )

    async def stop(self, *, disabled: bool = False) -> None:
        """Shut down the bridge and wait for clean disconnect."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        self._config_signature = None
        if disabled:
            self._store.set_connection_state("disabled")
        logger.info("MQTT bridge stopped")

    async def apply_runtime_settings(self) -> None:
        """Apply live runtime-setting changes without requiring a process restart."""
        desired_signature = self._settings_signature()
        bridge_enabled = bool(settings.enable_hardware_nodes)
        bridge_running = self._task is not None and not self._task.done()

        if not bridge_enabled:
            if bridge_running:
                await self.stop(disabled=True)
            else:
                self._store.set_connection_state("disabled")
            return

        if not _AIOMQTT_AVAILABLE:
            self._store.set_connection_state("error", "aiomqtt not installed")
            return

        if bridge_running and self._config_signature == desired_signature:
            return

        if bridge_running:
            logger.info("MQTT bridge settings changed; restarting bridge")
            await self.stop()

        await self.start()

    # ------------------------------------------------------------------
    # Internal

    async def _run(self) -> None:
        """Outer reconnect loop. Re-enters _connect_and_serve on any failure."""
        while self._running:
            try:
                await self._connect_and_serve()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("MQTT bridge error (retry in %ds): %s", _RECONNECT_DELAY, exc)
                self._store.set_connection_state("error", str(exc))
                if self._running:
                    await asyncio.sleep(_RECONNECT_DELAY)

    async def _connect_and_serve(self) -> None:
        prefix = settings.mqtt_topic_prefix
        node_id = settings.mqtt_node_id

        bridge_status_topic = f"{prefix}/bridge/status"
        state_topic = f"{prefix}/nodes/{node_id}/cmd/state"
        heartbeat_topic = f"{prefix}/nodes/{node_id}/telemetry/heartbeat"

        subscriber_id, queue = await self._event_bus.subscribe()
        try:
            async with aiomqtt.Client(
                hostname=settings.mqtt_broker_host,
                port=settings.mqtt_broker_port,
                identifier=settings.mqtt_client_id,
                will=aiomqtt.Will(
                    topic=bridge_status_topic,
                    payload=json.dumps({
                        "status": "offline",
                        "client_id": settings.mqtt_client_id,
                    }),
                    retain=True,
                ),
            ) as client:
                self._store.set_connection_state("connected")
                logger.info("MQTT bridge connected to %s:%d", settings.mqtt_broker_host, settings.mqtt_broker_port)

                await client.publish(
                    bridge_status_topic,
                    payload=json.dumps({
                        "status": "online",
                        "client_id": settings.mqtt_client_id,
                    }),
                    retain=True,
                )
                await client.subscribe(heartbeat_topic)
                await self._publish_command(
                    client,
                    state_topic,
                    self._store.get_current_command(),
                )

                receive_task = asyncio.create_task(
                    self._receive_loop(client), name="mqtt-receive"
                )
                try:
                    await self._publish_loop(client, queue, state_topic)
                finally:
                    receive_task.cancel()
                    try:
                        await receive_task
                    except (asyncio.CancelledError, Exception):
                        pass
        finally:
            await self._event_bus.unsubscribe(subscriber_id)
            self._store.set_connection_state("disconnected")

    async def _publish_loop(
        self,
        client: "aiomqtt.Client",
        queue: asyncio.Queue[Any],
        state_topic: str,
    ) -> None:
        """Drain the internal event bus and forward joi.state.changed to the node."""
        while self._running:
            try:
                envelope = await asyncio.wait_for(queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                continue

            if envelope.get("event") != "joi.state.changed":
                continue

            command = envelope.get("payload", {}).get("hardware_command")
            if not command:
                continue

            await self._publish_command(client, state_topic, command)

    async def _publish_command(
        self,
        client: "aiomqtt.Client",
        state_topic: str,
        command: dict[str, Any],
    ) -> None:
        await client.publish(state_topic, payload=json.dumps(command), retain=True)
        self._store.record_publish()
        logger.debug("MQTT published state=%s to %s", command.get("state"), state_topic)

    async def _receive_loop(self, client: "aiomqtt.Client") -> None:
        """Record heartbeat timestamps from the node."""
        async for _message in client.messages:
            try:
                self._store.record_heartbeat()
                logger.debug("MQTT heartbeat received from node")
            except Exception as exc:
                logger.warning("MQTT receive handling error: %s", exc)

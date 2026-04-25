from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Any

from app.config import settings
from app.hardware.schemas import (
    HardwareBridgeContractResponse,
    HardwareBridgeDiagnosticsResource,
    HardwareCommandResource,
    HardwareStateDefinitionResource,
    HardwareStateName,
)


CONTRACT_VERSION = "ambient-v1"

STATE_PROFILES: dict[HardwareStateName, dict[str, Any]] = {
    "sleeping": {
        "led_state": "off",
        "intensity": 0.05,
        "transition_ms": 1800,
        "note": "Dim or off ambient output for long idle or explicit sleep states.",
    },
    "idle": {
        "led_state": "calm_pulse",
        "intensity": 0.35,
        "transition_ms": 1200,
        "note": "Default calm presence when Joi is available but not actively engaged.",
    },
    "listening": {
        "led_state": "attentive_pulse",
        "intensity": 0.5,
        "transition_ms": 250,
        "note": "Mic capture or active listening state while the user is speaking.",
    },
    "thinking": {
        "led_state": "thinking_glow",
        "intensity": 0.45,
        "transition_ms": 700,
        "note": "Response generation or speech processing without aggressive flashing.",
    },
    "speaking": {
        "led_state": "speaking_pulse",
        "intensity": 0.65,
        "transition_ms": 180,
        "note": "Active spoken output while Joi is queued or playing speech.",
    },
    "user_returned": {
        "led_state": "gentle_wake",
        "intensity": 0.6,
        "transition_ms": 900,
        "note": "Short wake response when the user returns to the desk.",
    },
    "user_away": {
        "led_state": "off",
        "intensity": 0.1,
        "transition_ms": 1500,
        "note": "Fade down when the user is away instead of sustaining active presence.",
    },
    "error": {
        "led_state": "amber_warning",
        "intensity": 0.4,
        "transition_ms": 300,
        "note": "Low-key warning state for runtime or bridge errors.",
    },
}

DIAGNOSTICS_FIELDS = [
    "enabled",
    "available",
    "connection_state",
    "node_count",
    "last_heartbeat_at",
    "last_publish_at",
    "last_bridge_error",
]


def _utcnow() -> str:
    return datetime.utcnow().isoformat() + "Z"


class HardwareBridgeStore:
    """PC-side hardware contract and diagnostics state. Updated by MqttBridge at runtime."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._node_count = 0
        self._last_heartbeat_at: str | None = None
        self._last_publish_at: str | None = None
        self._last_bridge_error: str | None = None
        self._connection_state = "disabled"
        self._current_command = self._build_command(
            "idle",
            source_event="system.boot",
            reason="ambient bridge initialized in disabled mode",
        )

    def get_bridge_snapshot(self) -> dict[str, Any]:
        with self._lock:
            enabled = bool(settings.enable_hardware_nodes)
            connection_state = self._connection_state if enabled else "disabled"
            available = enabled and connection_state == "connected"
            snapshot = HardwareBridgeDiagnosticsResource(
                enabled=enabled,
                available=available,
                transport="mqtt",
                feature_flag="on" if enabled else "off",
                broker_host=settings.mqtt_broker_host,
                broker_port=settings.mqtt_broker_port,
                client_id=settings.mqtt_client_id,
                topic_prefix=settings.mqtt_topic_prefix,
                connection_state=connection_state,
                node_count=self._node_count,
                last_heartbeat_at=self._last_heartbeat_at,
                last_publish_at=self._last_publish_at,
                last_bridge_error=self._last_bridge_error,
                contract_version=CONTRACT_VERSION,
                current_command=self._current_command,
            )
            return snapshot.model_dump(mode="json")

    def get_contract(self) -> dict[str, Any]:
        contract = HardwareBridgeContractResponse(
            contract_version=CONTRACT_VERSION,
            disabled_by_default=True,
            state_topic_template=f"{settings.mqtt_topic_prefix}/nodes/{{node_id}}/cmd/state",
            config_topic_template=f"{settings.mqtt_topic_prefix}/nodes/{{node_id}}/cmd/config",
            telemetry_topics=[
                f"{settings.mqtt_topic_prefix}/nodes/{{node_id}}/telemetry/presence",
                f"{settings.mqtt_topic_prefix}/nodes/{{node_id}}/telemetry/distance",
                f"{settings.mqtt_topic_prefix}/nodes/{{node_id}}/status/availability",
                f"{settings.mqtt_topic_prefix}/nodes/{{node_id}}/status/health",
            ],
            diagnostics_fields=DIAGNOSTICS_FIELDS,
            states=[
                HardwareStateDefinitionResource(state=state, **profile)
                for state, profile in STATE_PROFILES.items()
            ],
            bridge=HardwareBridgeDiagnosticsResource(**self.get_bridge_snapshot()),
        )
        return contract.model_dump(mode="json")

    def get_current_command(self) -> dict[str, Any]:
        with self._lock:
            return self._current_command.model_dump(mode="json")

    def set_connection_state(
        self,
        state: str,
        error: str | None = None,
    ) -> None:
        with self._lock:
            self._connection_state = state
            if error is not None:
                self._last_bridge_error = error
            if state in ("disconnected", "disabled", "error"):
                self._node_count = 0

    def record_publish(self) -> None:
        with self._lock:
            self._last_publish_at = _utcnow()

    def record_heartbeat(self) -> None:
        with self._lock:
            self._last_heartbeat_at = _utcnow()
            self._node_count = 1

    def set_runtime_state(
        self,
        state: HardwareStateName,
        *,
        source_event: str,
        session_id: str | None = None,
        reason: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        with self._lock:
            previous = self._current_command
            next_command = self._build_command(
                state,
                source_event=source_event,
                session_id=session_id,
                reason=reason,
            )
            changed = (
                previous.state != next_command.state
                or previous.led_state != next_command.led_state
                or previous.session_id != next_command.session_id
            )
            if changed:
                self._current_command = next_command
            return self._current_command.model_dump(mode="json"), changed

    def sync_from_media_session(
        self,
        session_id: str,
        media_state: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        speaking_state = str(media_state.get("speaking_state") or "idle")
        mic_state = str(media_state.get("mic_state") or "idle")
        last_error = media_state.get("last_error")

        if speaking_state == "error" or mic_state == "error":
            next_state: HardwareStateName = "error"
            reason = str(last_error or "media session entered error state")
        elif speaking_state in {"queued", "playing"}:
            next_state = "speaking"
            reason = f"speaking_state={speaking_state}"
        elif mic_state in {"requesting", "recording"}:
            next_state = "listening"
            reason = f"mic_state={mic_state}"
        elif mic_state == "processing":
            next_state = "thinking"
            reason = "speech transcription in progress"
        else:
            next_state = "idle"
            reason = "media session settled"

        return self.set_runtime_state(
            next_state,
            source_event="media.session.updated",
            session_id=session_id,
            reason=reason,
        )

    def _build_command(
        self,
        state: HardwareStateName,
        *,
        source_event: str,
        session_id: str | None = None,
        reason: str | None = None,
    ) -> HardwareCommandResource:
        profile = STATE_PROFILES[state]
        return HardwareCommandResource(
            contract_version=CONTRACT_VERSION,
            state=state,
            led_state=profile["led_state"],
            intensity=profile["intensity"],
            transition_ms=profile["transition_ms"],
            mood="neutral",
            source_event=source_event,
            session_id=session_id,
            reason=reason,
            updated_at=_utcnow(),
        )

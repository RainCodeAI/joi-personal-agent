from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


HardwareStateName = Literal[
    "sleeping",
    "idle",
    "listening",
    "thinking",
    "speaking",
    "user_returned",
    "user_away",
    "error",
]

LedOutputStateName = Literal[
    "off",
    "calm_pulse",
    "attentive_pulse",
    "thinking_glow",
    "speaking_pulse",
    "gentle_wake",
    "amber_warning",
]

BridgeConnectionState = Literal["disabled", "disconnected", "connected", "error"]


class HardwareCommandResource(BaseModel):
    contract_version: str = "ambient-v1"
    state: HardwareStateName = "idle"
    led_state: LedOutputStateName = "calm_pulse"
    intensity: float = Field(default=0.35, ge=0.0, le=1.0)
    transition_ms: int = Field(default=1200, ge=0)
    mood: str = "neutral"
    source_event: str = "system.boot"
    session_id: Optional[str] = None
    reason: Optional[str] = None
    updated_at: str


class HardwareStateDefinitionResource(BaseModel):
    state: HardwareStateName
    led_state: LedOutputStateName
    intensity: float = Field(ge=0.0, le=1.0)
    transition_ms: int = Field(ge=0)
    note: str


class HardwareBridgeDiagnosticsResource(BaseModel):
    enabled: bool = False
    available: bool = False
    transport: str = "mqtt"
    feature_flag: str = "off"
    broker_host: str = "127.0.0.1"
    broker_port: int = 1883
    client_id: str = "joi-pc-runtime"
    topic_prefix: str = "joi"
    connection_state: BridgeConnectionState = "disabled"
    node_count: int = 0
    last_heartbeat_at: Optional[str] = None
    last_publish_at: Optional[str] = None
    last_bridge_error: Optional[str] = None
    contract_version: str = "ambient-v1"
    current_command: HardwareCommandResource


class HardwareBridgeContractResponse(BaseModel):
    api_version: Literal["v2"] = "v2"
    contract_version: str = "ambient-v1"
    disabled_by_default: bool = True
    state_topic_template: str
    config_topic_template: str
    telemetry_topics: list[str] = Field(default_factory=list)
    diagnostics_fields: list[str] = Field(default_factory=list)
    states: list[HardwareStateDefinitionResource] = Field(default_factory=list)
    bridge: HardwareBridgeDiagnosticsResource


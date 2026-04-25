from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class V2ResponseBase(BaseModel):
    api_version: Literal["v2"] = "v2"


class SessionCreateRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: str = "default"
    title: Optional[str] = None


class SessionResource(BaseModel):
    id: str
    user_id: str = "default"
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SessionListResponse(V2ResponseBase):
    sessions: List[SessionResource] = Field(default_factory=list)


class SessionCreateResponse(V2ResponseBase):
    session: SessionResource


class MessageResource(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    timestamp: datetime


class MessageListResponse(V2ResponseBase):
    session: SessionResource
    messages: List[MessageResource] = Field(default_factory=list)


class ToolCallResource(BaseModel):
    tool_name: str
    args: Dict[str, Any] = Field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    status: str = "success"


class ApprovalResource(BaseModel):
    id: str
    session_id: Optional[str] = None
    tool_name: str
    args: Dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: str
    resolved_at: Optional[str] = None


class ApprovalListResponse(V2ResponseBase):
    approvals: List[ApprovalResource] = Field(default_factory=list)


class ApprovalDecisionResponse(V2ResponseBase):
    approval: ApprovalResource
    tool_result: Optional[ToolCallResource] = None


class EmotionResource(BaseModel):
    craving_score: float = 0.0
    is_dramatic_return: bool = False


class ProviderResource(BaseModel):
    selected: str = ""
    route: List[str] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)


class AvatarCueResource(BaseModel):
    expression: str = "neutral"
    voice_hint: str = "default"
    should_speak: bool = True


class ChatAttachmentRequest(BaseModel):
    id: Optional[str] = None
    kind: Literal["image", "text", "file"] = "file"
    name: str
    media_type: str
    data_url: str
    size_bytes: Optional[int] = None


class ChatAttachmentResource(BaseModel):
    id: str
    kind: Literal["image", "text", "file"] = "file"
    name: str
    media_type: str
    size_bytes: int = 0
    preview_text: Optional[str] = None


class V2ChatRequest(BaseModel):
    session_id: str
    text: str
    attachments: List[ChatAttachmentRequest] = Field(default_factory=list)


class V2ChatResponse(V2ResponseBase):
    session: SessionResource
    user_message: MessageResource
    assistant_message: MessageResource
    attachments: List[ChatAttachmentResource] = Field(default_factory=list)
    tool_calls: List[ToolCallResource] = Field(default_factory=list)
    pending_approvals: List[ApprovalResource] = Field(default_factory=list)
    emotion: EmotionResource = Field(default_factory=EmotionResource)
    provider: ProviderResource = Field(default_factory=ProviderResource)
    avatar: AvatarCueResource = Field(default_factory=AvatarCueResource)


class AvatarSyncRequest(BaseModel):
    session_id: str
    text: str


class AvatarSyncResponse(V2ResponseBase):
    session_id: str
    audio_url: str
    phoneme_timeline: List[List[Any]] | List[tuple] = Field(default_factory=list)
    sentiment: str = "neutral"
    delivery_style: str = "normal"


class MediaSessionResource(BaseModel):
    session_id: str
    mic_state: Literal["idle", "requesting", "recording", "processing", "error"] = "idle"
    speaking_state: Literal["idle", "queued", "playing", "interrupted", "error"] = "idle"
    capture_source: str = "browser"
    last_transcript: str = ""
    recognition_latency_ms: Optional[int] = None
    playback_latency_ms: Optional[int] = None
    interruption_count: int = 0
    last_error: Optional[str] = None
    updated_at: str


class MediaSessionPatchRequest(BaseModel):
    session_id: str
    mic_state: Optional[Literal["idle", "requesting", "recording", "processing", "error"]] = None
    speaking_state: Optional[Literal["idle", "queued", "playing", "interrupted", "error"]] = None
    capture_source: Optional[str] = None
    last_transcript: Optional[str] = None
    recognition_latency_ms: Optional[int] = None
    playback_latency_ms: Optional[int] = None
    last_error: Optional[str] = None
    interrupted: bool = False


class MediaSessionResponse(V2ResponseBase):
    media_session: MediaSessionResource


class MediaTranscribeRequest(BaseModel):
    session_id: str
    media_type: str
    data_url: str
    duration_ms: Optional[int] = None


class MediaTranscribeResponse(V2ResponseBase):
    media_session: MediaSessionResource
    transcript: str = ""
    media_type: str
    duration_ms: Optional[int] = None
    latency_ms: int = 0


class RealtimeEventEnvelope(V2ResponseBase):
    event_id: str
    event: str
    source: str
    session_id: Optional[str] = None
    timestamp: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class RealtimeEventsResponse(V2ResponseBase):
    events: List[RealtimeEventEnvelope] = Field(default_factory=list)


class SettingsResource(BaseModel):
    airgap: bool
    autonomy_level: str
    enable_proactive_messaging: bool
    enable_hardware_nodes: bool
    mqtt_broker_host: str
    mqtt_broker_port: int
    mqtt_client_id: str
    mqtt_topic_prefix: str
    mqtt_node_id: str
    model_chat: str
    model_embed: str
    router_timeout: int
    gguf_n_ctx: int
    gguf_n_gpu_layers: int


class SettingsResponse(V2ResponseBase):
    settings: SettingsResource


class SettingsPatchRequest(BaseModel):
    airgap: Optional[bool] = None
    autonomy_level: Optional[str] = None
    enable_proactive_messaging: Optional[bool] = None
    enable_hardware_nodes: Optional[bool] = None
    mqtt_broker_host: Optional[str] = None
    mqtt_broker_port: Optional[int] = None
    mqtt_client_id: Optional[str] = None
    mqtt_topic_prefix: Optional[str] = None
    mqtt_node_id: Optional[str] = None
    model_chat: Optional[str] = None
    model_embed: Optional[str] = None
    router_timeout: Optional[int] = None
    gguf_n_ctx: Optional[int] = None
    gguf_n_gpu_layers: Optional[int] = None


class MemoryResource(BaseModel):
    id: int
    type: str
    text: str
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    memory_type: str


class MemorySearchItemResource(BaseModel):
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    distance: float
    source: str = "vector"
    matched_entity: Optional[str] = None


class MemoryRecentResponse(V2ResponseBase):
    memories: List[MemoryResource] = Field(default_factory=list)


class MemorySearchResponseV2(V2ResponseBase):
    query: str
    items: List[MemorySearchItemResource] = Field(default_factory=list)


class UserProfileResource(BaseModel):
    user_id: str = "default"
    name: Optional[str] = None
    email: Optional[str] = None
    birthday: Optional[str] = None
    hobbies: Optional[str] = None
    relationships: Optional[str] = None
    notes: Optional[str] = None
    therapeutic_mode: bool = False
    personality: Optional[str] = None
    humor_level: int = 5


class ProfilePatchRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    birthday: Optional[str] = None
    hobbies: Optional[str] = None
    relationships: Optional[str] = None
    notes: Optional[str] = None
    therapeutic_mode: Optional[bool] = None
    personality: Optional[str] = None
    humor_level: Optional[int] = None


class MoodEntryResource(BaseModel):
    id: int
    user_id: str
    date: datetime
    mood: int


class MoodEntryCreateRequest(BaseModel):
    user_id: str = "default"
    mood: int
    date: Optional[datetime] = None


class HabitResource(BaseModel):
    id: int
    user_id: str
    name: str
    streak: int = 0
    last_done: Optional[datetime] = None


class HabitCreateRequest(BaseModel):
    user_id: str = "default"
    name: str


class GoalResource(BaseModel):
    id: int
    user_id: str
    name: str
    description: Optional[str] = None
    linked_habit_id: Optional[int] = None
    linked_decision_id: Optional[int] = None
    status: str = "active"


class GoalCreateRequest(BaseModel):
    user_id: str = "default"
    name: str
    description: Optional[str] = None
    linked_habit_id: Optional[int] = None
    linked_decision_id: Optional[int] = None


class DecisionResource(BaseModel):
    id: int
    user_id: str
    question: str
    pros: Optional[str] = None
    cons: Optional[str] = None
    outcome: Optional[str] = None


class CbtExerciseResource(BaseModel):
    id: int
    user_id: str
    name: str
    description: str
    completed_count: int = 0


class CbtExerciseCreateRequest(BaseModel):
    user_id: str = "default"
    name: str
    description: str


class ActivityLogResource(BaseModel):
    id: int
    user_id: str
    app: str
    duration: int
    timestamp: datetime


class ActivityLogCreateRequest(BaseModel):
    user_id: str = "default"
    app: str
    duration: int


class ContactResource(BaseModel):
    id: int
    user_id: str
    name: str
    last_contact: date
    strength: int = 5
    entity_id: Optional[str] = None


class ContactCreateRequest(BaseModel):
    user_id: str = "default"
    name: str
    last_contact: Optional[date] = None
    strength: int = 5
    entity_id: Optional[str] = None


class SleepLogResource(BaseModel):
    id: int
    user_id: str
    date: date
    hours_slept: float
    quality: int


class SleepLogCreateRequest(BaseModel):
    user_id: str = "default"
    date: Optional[date] = None
    hours_slept: float
    quality: int = 5


class TransactionResource(BaseModel):
    id: int
    user_id: str
    date: date
    amount: float
    category: str


class TransactionCreateRequest(BaseModel):
    user_id: str = "default"
    date: Optional[date] = None
    amount: float
    category: str


class ProfileResponse(V2ResponseBase):
    profile: UserProfileResource
    moods: List[MoodEntryResource] = Field(default_factory=list)
    habits: List[HabitResource] = Field(default_factory=list)
    goals: List[GoalResource] = Field(default_factory=list)
    decisions: List[DecisionResource] = Field(default_factory=list)
    exercises: List[CbtExerciseResource] = Field(default_factory=list)
    activities: List[ActivityLogResource] = Field(default_factory=list)
    sleeps: List[SleepLogResource] = Field(default_factory=list)
    transactions: List[TransactionResource] = Field(default_factory=list)
    contacts: List[ContactResource] = Field(default_factory=list)


class MoodEntryCreateResponse(V2ResponseBase):
    mood: MoodEntryResource


class HabitCreateResponse(V2ResponseBase):
    habit: HabitResource


class GoalCreateResponse(V2ResponseBase):
    goal: GoalResource


class CbtExerciseCreateResponse(V2ResponseBase):
    exercise: CbtExerciseResource


class ActivityLogCreateResponse(V2ResponseBase):
    activity: ActivityLogResource


class SleepLogCreateResponse(V2ResponseBase):
    sleep: SleepLogResource


class TransactionCreateResponse(V2ResponseBase):
    transaction: TransactionResource


class ContactCreateResponse(V2ResponseBase):
    contact: ContactResource


class PlannerBlockResource(BaseModel):
    time: str
    activity: str


class PlannerSnapshotResource(BaseModel):
    user_id: str = "default"
    latest_mood: int = 5
    mood_trend: Dict[str, Any] = Field(default_factory=dict)
    health_correlation: Dict[str, Any] = Field(default_factory=dict)
    overdue_contacts: List[Dict[str, Any]] = Field(default_factory=list)
    active_goals: List[str] = Field(default_factory=list)
    habits: List[str] = Field(default_factory=list)


class PlannerContextResponse(V2ResponseBase):
    snapshot: PlannerSnapshotResource


class PlannerGenerateRequest(BaseModel):
    user_id: str = "default"
    key_tasks: List[str] = Field(default_factory=list)
    focus_areas: List[str] = Field(default_factory=list)
    energy_level: int = 5


class PlannerGenerateResponse(V2ResponseBase):
    provider: str
    model: str = ""
    blocks: List[PlannerBlockResource] = Field(default_factory=list)
    snapshot: PlannerSnapshotResource


class PerceptionPolicyResource(BaseModel):
    camera_enabled: bool = True
    retain_expressions: bool = False
    retain_snapshots: bool = False
    retention_days: int = 0
    last_updated: Optional[str] = None


class PerceptionPolicyResponse(V2ResponseBase):
    policy: PerceptionPolicyResource


class PerceptionPolicyPatchRequest(BaseModel):
    camera_enabled: Optional[bool] = None
    retain_expressions: Optional[bool] = None
    retain_snapshots: Optional[bool] = None
    retention_days: Optional[int] = None


class VisionAnalyzeRequest(BaseModel):
    session_id: str
    data_url: str
    context_hint: Optional[str] = None


class VisionAnalyzeResponse(V2ResponseBase):
    session_id: str
    description: str
    tags: List[str] = Field(default_factory=list)
    captured_at: str

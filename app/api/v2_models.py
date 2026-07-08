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


class DesktopActionRequest(BaseModel):
    session_id: Optional[str] = None
    action: Literal["open_url", "show_notification"]
    args: Dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False
    source: Literal["web", "native", "api"] = "web"


class DesktopActionResultResource(BaseModel):
    action_id: str
    action: str
    status: Literal["success", "blocked", "error"]
    summary: str
    result: Dict[str, Any] = Field(default_factory=dict)
    audit_record: Dict[str, Any] = Field(default_factory=dict)


class DesktopActionResponse(V2ResponseBase):
    desktop_action: DesktopActionResultResource


class ApprovalResource(BaseModel):
    id: str
    session_id: Optional[str] = None
    tool_name: str
    args: Dict[str, Any] = Field(default_factory=dict)
    local_only: bool = True
    status: str
    created_at: str
    resolved_at: Optional[str] = None


class ApprovalDecisionRequest(BaseModel):
    confirmed: bool
    client_surface: Literal["web"] = "web"


class ApprovalListResponse(V2ResponseBase):
    approvals: List[ApprovalResource] = Field(default_factory=list)


class ApprovalDecisionResponse(V2ResponseBase):
    approval: ApprovalResource
    tool_result: Optional[ToolCallResource] = None


class ConnectorResource(BaseModel):
    id: Literal["gmail", "calendar"]
    label: str
    connected: bool
    capabilities: List[str] = Field(default_factory=list)
    scopes: List[str] = Field(default_factory=list)


class ConnectorListResponse(V2ResponseBase):
    connectors: List[ConnectorResource] = Field(default_factory=list)


class ConnectorDisconnectRequest(BaseModel):
    confirmed: bool


class ConnectorDisconnectResponse(V2ResponseBase):
    connector: ConnectorResource


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
    source: Literal["user_upload", "screen_capture", "camera_snapshot"] = "user_upload"
    capture_metadata: Dict[str, str] = Field(default_factory=dict)


class ChatAttachmentResource(BaseModel):
    id: str
    kind: Literal["image", "text", "file"] = "file"
    name: str
    media_type: str
    size_bytes: int = 0
    preview_text: Optional[str] = None
    source: Literal["user_upload", "screen_capture", "camera_snapshot"] = "user_upload"
    capture_metadata: Dict[str, str] = Field(default_factory=dict)
    ocr_status: Optional[Literal["complete", "unavailable", "not_requested"]] = None


class PerceptionContextRequest(BaseModel):
    """Live camera-perception state the client sends with a chat turn, so Joi can
    reference real presence. Only sent when the camera is actively sensing."""
    camera_active: bool = False
    user_present: Optional[bool] = None
    expression: Optional[str] = None
    leaned_in: Optional[bool] = None


class V2ChatRequest(BaseModel):
    session_id: str
    text: str
    attachments: List[ChatAttachmentRequest] = Field(default_factory=list)
    client_turn_id: Optional[str] = None
    perception: Optional[PerceptionContextRequest] = None


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
    assistant_turn_id: Optional[str] = None
    voice_mode: Literal["push_to_talk", "conversation", "ambient"] = "push_to_talk"
    turn_state: Literal[
        "idle",
        "listening",
        "speech_detected",
        "transcribing",
        "thinking",
        "speaking",
        "interrupted",
        "error",
    ] = "idle"
    mic_state: Literal["idle", "requesting", "recording", "processing", "error"] = "idle"
    speaking_state: Literal["idle", "queued", "playing", "interrupted", "error"] = "idle"
    capture_source: str = "browser"
    last_transcript: str = ""
    recognition_latency_ms: Optional[int] = None
    end_of_speech_to_transcript_ms: Optional[int] = None
    speech_duration_ms: Optional[int] = None
    speech_detected: bool = False
    model_latency_ms: Optional[int] = None
    tts_generation_latency_ms: Optional[int] = None
    first_audio_latency_ms: Optional[int] = None
    end_to_end_latency_ms: Optional[int] = None
    playback_latency_ms: Optional[int] = None
    interruption_count: int = 0
    last_error: Optional[str] = None
    updated_at: str


class MediaSessionPatchRequest(BaseModel):
    session_id: str
    assistant_turn_id: Optional[str] = None
    voice_mode: Optional[Literal["push_to_talk", "conversation", "ambient"]] = None
    turn_state: Optional[
        Literal[
            "idle",
            "listening",
            "speech_detected",
            "transcribing",
            "thinking",
            "speaking",
            "interrupted",
            "error",
        ]
    ] = None
    mic_state: Optional[Literal["idle", "requesting", "recording", "processing", "error"]] = None
    speaking_state: Optional[Literal["idle", "queued", "playing", "interrupted", "error"]] = None
    capture_source: Optional[str] = None
    last_transcript: Optional[str] = None
    recognition_latency_ms: Optional[int] = None
    end_of_speech_to_transcript_ms: Optional[int] = None
    speech_duration_ms: Optional[int] = None
    speech_detected: Optional[bool] = None
    model_latency_ms: Optional[int] = None
    tts_generation_latency_ms: Optional[int] = None
    first_audio_latency_ms: Optional[int] = None
    end_to_end_latency_ms: Optional[int] = None
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
    voice_mode: Literal["push_to_talk", "conversation", "ambient"] = "push_to_talk"
    speech_detected: bool = False
    # A silent wake-word probe: transcribe only, without mutating media-session
    # state or broadcasting events, so ambient overhearing doesn't drive the
    # avatar/hardware or pollute the event stream.
    wake_probe: bool = False


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
    initiative_enabled: bool
    initiative_daily_limit: int
    initiative_timezone: str
    initiative_daily_greeting_start: str
    initiative_daily_greeting_end: str
    initiative_quiet_hours_start: str
    initiative_quiet_hours_end: str
    initiative_focus_mode: bool
    initiative_do_not_disturb: bool
    initiative_late_night_start: str
    initiative_late_night_end: str
    initiative_silence_threshold_minutes: int
    initiative_allowed_types: str
    context_commentary_enabled: bool
    context_min_confidence: float
    context_dedup_minutes: int
    context_allowed_categories: str
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
    initiative_enabled: Optional[bool] = None
    initiative_daily_limit: Optional[int] = None
    initiative_timezone: Optional[str] = None
    initiative_daily_greeting_start: Optional[str] = None
    initiative_daily_greeting_end: Optional[str] = None
    initiative_quiet_hours_start: Optional[str] = None
    initiative_quiet_hours_end: Optional[str] = None
    initiative_focus_mode: Optional[bool] = None
    initiative_do_not_disturb: Optional[bool] = None
    initiative_late_night_start: Optional[str] = None
    initiative_late_night_end: Optional[str] = None
    initiative_silence_threshold_minutes: Optional[int] = None
    initiative_allowed_types: Optional[str] = None
    context_commentary_enabled: Optional[bool] = None
    context_min_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    context_dedup_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    context_allowed_categories: Optional[str] = None
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


UserModelSectionKey = Literal[
    "active_projects",
    "recurring_worries",
    "stated_goals",
    "important_people",
    "mood_trend",
    "communication_preferences",
    "recent_wins",
    "open_loops",
    "character_notes",
]

UserModelEvidenceSource = Literal[
    "chat",
    "memory",
    "profile",
    "mood",
    "habit",
    "goal",
    "contact",
    "calendar",
    "notes",
    "hardware",
    "correction",
    "system",
]

UserModelLifecycle = Literal["fresh", "active", "archive", "pinned"]


class UserModelEvidenceResource(BaseModel):
    source_type: UserModelEvidenceSource
    source_id: Optional[str] = None
    summary: str
    observed_at: Optional[str] = None


class UserModelItemResource(BaseModel):
    id: str
    label: str
    value: str
    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_count: int = Field(default=0, ge=0)
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    lifecycle: UserModelLifecycle = "active"
    user_confirmed: bool = False
    hidden: bool = False
    source_summary: str
    evidence: List[UserModelEvidenceResource] = Field(default_factory=list)


class UserModelSectionResource(BaseModel):
    key: UserModelSectionKey
    title: str
    description: str
    items: List[UserModelItemResource] = Field(default_factory=list)


class UserModelPolicyResource(BaseModel):
    inference_enabled: bool = False
    correction_supported: bool = False
    initiative_surface_enabled: bool = False
    min_confidence_to_surface: float = Field(default=0.75, ge=0.0, le=1.0)
    stores_raw_files: bool = False
    stores_raw_presence_streams: bool = False


class UserModelResponse(V2ResponseBase):
    user_id: str = "default"
    status: Literal["contract_only", "active"] = "contract_only"
    generated_at: str
    policy: UserModelPolicyResource = Field(default_factory=UserModelPolicyResource)
    readable_summary: str = ""
    sections: List[UserModelSectionResource] = Field(default_factory=list)


class UserModelCorrectionRequest(BaseModel):
    section_key: UserModelSectionKey
    action: Literal["confirm", "edit", "hide", "delete", "add"]
    item_id: Optional[str] = None
    label: Optional[str] = None
    value: Optional[str] = None
    note: Optional[str] = None


class UserModelCorrectionResource(BaseModel):
    id: str
    user_id: str
    section_key: UserModelSectionKey
    action: Literal["confirm", "edit", "hide", "delete", "add"]
    item_id: Optional[str] = None
    label: Optional[str] = None
    value: Optional[str] = None
    note: Optional[str] = None
    created_at: str


class UserModelCorrectionResponse(V2ResponseBase):
    user_id: str = "default"
    correction: UserModelCorrectionResource
    user_model: UserModelResponse


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
    screen_access: Literal["disabled", "manual_only"] = "disabled"
    retain_expressions: bool = False
    retain_snapshots: bool = False
    retention_days: int = 0
    last_updated: Optional[str] = None


class PerceptionPolicyResponse(V2ResponseBase):
    policy: PerceptionPolicyResource


class PerceptionPolicyPatchRequest(BaseModel):
    camera_enabled: Optional[bool] = None
    screen_access: Optional[Literal["disabled", "manual_only"]] = None
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


class SynthesisCandidateResource(BaseModel):
    candidate_id: str
    section_key: UserModelSectionKey
    label: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    inference_method: str = "pattern"
    trigger_phrase: str = ""
    source_excerpt: str = ""
    source_message_role: str = "user"
    source_message_index: int = 0
    blocked_by_correction: bool = False
    duplicate_of_existing: bool = False


class SynthesisRecordResource(BaseModel):
    id: str
    run_id: str
    user_id: str = "default"
    session_id: str
    candidate_id: str
    section_key: UserModelSectionKey
    label: str
    method: Literal["pattern", "llm"]
    evidence_excerpt: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    status: Literal["dry_run", "skipped", "written"]
    skipped: bool = False
    skipped_reason: str = ""
    written: bool = False
    dry_run: bool = True
    source_message_role: str = "user"
    source_message_index: int = 0
    created_at: str


class SynthesisResponse(V2ResponseBase):
    session_id: str
    user_id: str = "default"
    method: Literal["pattern", "llm"] = "pattern"
    dry_run: bool = True
    writes_enabled: bool = False
    candidates: List[SynthesisCandidateResource] = Field(default_factory=list)
    audit_records: List[SynthesisRecordResource] = Field(default_factory=list)
    provider: ProviderResource = Field(default_factory=ProviderResource)
    written_count: int = 0
    skipped_count: int = 0
    message_count: int = 0
    analysed_at: str


class SynthesisRecordListResponse(V2ResponseBase):
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    records: List[SynthesisRecordResource] = Field(default_factory=list)

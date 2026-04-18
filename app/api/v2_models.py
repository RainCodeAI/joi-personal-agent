from __future__ import annotations

from datetime import datetime
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


class V2ChatRequest(BaseModel):
    session_id: str
    text: str


class V2ChatResponse(V2ResponseBase):
    session: SessionResource
    user_message: MessageResource
    assistant_message: MessageResource
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


class SettingsResource(BaseModel):
    airgap: bool
    autonomy_level: str
    enable_proactive_messaging: bool
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
    model_chat: Optional[str] = None
    model_embed: Optional[str] = None
    router_timeout: Optional[int] = None
    gguf_n_ctx: Optional[int] = None
    gguf_n_gpu_layers: Optional[int] = None

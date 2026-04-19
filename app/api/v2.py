from __future__ import annotations

import asyncio
import base64
import json
import io
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.api.realtime import format_sse_event
from app.api.state import agent, approval_manager, event_bus, media_sessions, memory_store, perception_policy, runtime_settings
from app.api.models import (
    ActivityLog,
    CbtExercise,
    Decision,
    Habit,
    MoodEntry,
    PersonalGoal,
    UserProfile,
)
from app.api.v2_models import (
    ActivityLogCreateRequest,
    ActivityLogCreateResponse,
    ActivityLogResource,
    ApprovalDecisionResponse,
    ApprovalListResponse,
    ApprovalResource,
    AvatarCueResource,
    AvatarSyncRequest,
    AvatarSyncResponse,
    CbtExerciseCreateRequest,
    CbtExerciseCreateResponse,
    CbtExerciseResource,
    ChatAttachmentRequest,
    ChatAttachmentResource,
    ContactCreateRequest,
    ContactCreateResponse,
    ContactResource,
    DecisionResource,
    EmotionResource,
    GoalCreateRequest,
    GoalCreateResponse,
    GoalResource,
    HabitCreateRequest,
    HabitCreateResponse,
    HabitResource,
    MemoryRecentResponse,
    MemoryResource,
    MemorySearchItemResource,
    MemorySearchResponseV2,
    MediaSessionPatchRequest,
    MediaSessionResource,
    MediaSessionResponse,
    MediaTranscribeRequest,
    MediaTranscribeResponse,
    MessageListResponse,
    MessageResource,
    MoodEntryCreateRequest,
    MoodEntryCreateResponse,
    MoodEntryResource,
    PlannerBlockResource,
    PlannerContextResponse,
    PlannerGenerateRequest,
    PlannerGenerateResponse,
    PlannerSnapshotResource,
    ProviderResource,
    ProfilePatchRequest,
    ProfileResponse,
    RealtimeEventEnvelope,
    RealtimeEventsResponse,
    SleepLogCreateRequest,
    SleepLogCreateResponse,
    SleepLogResource,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionListResponse,
    SessionResource,
    SettingsPatchRequest,
    SettingsResponse,
    SettingsResource,
    TransactionCreateRequest,
    TransactionCreateResponse,
    TransactionResource,
    ToolCallResource,
    UserProfileResource,
    V2ChatRequest,
    V2ChatResponse,
    PerceptionPolicyPatchRequest,
    PerceptionPolicyResource,
    PerceptionPolicyResponse,
    VisionAnalyzeRequest,
    VisionAnalyzeResponse,
)
from app.orchestrator.day_planner import build_planner_snapshot, generate_day_plan
from app.orchestrator.craving_engine import CravingEngine
from app.orchestrator.security.approval import ApprovalStatus, PendingApproval
from app.tools import vision_clip
from app.tools.voice import voice_tools


router = APIRouter(prefix="/api/v2", tags=["v2"])


def _session_resource(session) -> SessionResource:
    return SessionResource(
        id=session.id,
        user_id=session.user_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _message_resource(message) -> MessageResource:
    return MessageResource(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        timestamp=message.timestamp,
    )


def _approval_resource(approval: PendingApproval) -> ApprovalResource:
    return ApprovalResource(
        id=approval.id,
        session_id=approval.session_id,
        tool_name=approval.tool_name,
        args=approval.args,
        status=approval.status.value if isinstance(approval.status, ApprovalStatus) else str(approval.status),
        created_at=approval.created_at,
        resolved_at=approval.resolved_at,
    )


def _tool_call_resources(tool_calls: Iterable[Dict[str, Any]]) -> List[ToolCallResource]:
    return [
        ToolCallResource(
            tool_name=tool_call.get("tool_name", ""),
            args=tool_call.get("args", {}),
            result=tool_call.get("result"),
            status=tool_call.get("status", "success"),
        )
        for tool_call in tool_calls
    ]


def _settings_resource() -> SettingsResource:
    return SettingsResource(**runtime_settings.get())


def _event_resource(event: Dict[str, Any]) -> RealtimeEventEnvelope:
    return RealtimeEventEnvelope(**event)


def _media_session_resource(state: Dict[str, Any]) -> MediaSessionResource:
    return MediaSessionResource(**state)


async def _publish_media_session(session_id: str, state: Dict[str, Any]) -> None:
    await event_bus.publish(
        "media.session.updated",
        {
            "media_session": _media_session_resource(state).model_dump(mode="json"),
        },
        session_id=session_id,
        source="media",
    )


def _decode_data_url(data_url: str) -> tuple[str, bytes]:
    match = re.match(r"^data:(?P<mime>[^;]+);base64,(?P<data>.+)$", data_url, re.DOTALL)
    if not match:
        raise ValueError("Unsupported attachment encoding")
    raw = base64.b64decode(match.group("data"))
    return match.group("mime"), raw


def _audio_suffix(media_type: str) -> str:
    if media_type == "audio/webm":
        return ".webm"
    if media_type == "audio/mp4" or media_type == "audio/m4a":
        return ".m4a"
    if media_type == "audio/mpeg":
        return ".mp3"
    if media_type == "audio/ogg":
        return ".ogg"
    if media_type == "audio/wav":
        return ".wav"
    return ".bin"


def _convert_audio_to_wav(input_path: str) -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return input_path

    wav_path = f"{input_path}.wav"
    completed = subprocess.run(
        [ffmpeg, "-y", "-i", input_path, wav_path],
        check=False,
        capture_output=True,
    )
    if completed.returncode == 0 and os.path.exists(wav_path):
        return wav_path
    return input_path


def _transcribe_browser_audio(raw_bytes: bytes, media_type: str) -> str:
    source_path = None
    converted_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=_audio_suffix(media_type), delete=False) as source_file:
            source_file.write(raw_bytes)
            source_path = source_file.name

        transcription_path = source_path
        if media_type not in {"audio/wav", "audio/x-wav", "audio/flac"}:
            converted_path = _convert_audio_to_wav(source_path)
            transcription_path = converted_path

        transcript = voice_tools.transcribe_audio_file(transcription_path)
        return transcript or ""
    finally:
        for path in {source_path, converted_path}:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


def _attachment_context(attachment: ChatAttachmentRequest) -> tuple[ChatAttachmentResource, str]:
    attachment_id = attachment.id or str(uuid.uuid4())

    try:
        decoded_mime, raw_bytes = _decode_data_url(attachment.data_url)
    except Exception as exc:
        resource = ChatAttachmentResource(
            id=attachment_id,
            kind=attachment.kind,
            name=attachment.name,
            media_type=attachment.media_type,
            size_bytes=attachment.size_bytes or 0,
            preview_text=f"Attachment decode failed: {exc}",
        )
        return resource, f"User attached '{attachment.name}', but the file could not be decoded."

    media_type = attachment.media_type or decoded_mime
    preview_text: str | None = None
    context_text: str

    if attachment.kind == "image" or media_type.startswith("image/"):
        try:
            from PIL import Image

            image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            preview_text = vision_clip.describe_image(image)
            context_text = (
                f"Image attachment '{attachment.name}' described as: {preview_text}"
            )
            kind = "image"
        except Exception as exc:
            preview_text = f"Image processing failed: {exc}"
            context_text = f"Image attachment '{attachment.name}' could not be processed."
            kind = "image"
    elif attachment.kind == "text" or media_type.startswith("text/"):
        excerpt = raw_bytes.decode("utf-8", errors="replace").strip()
        preview_text = excerpt[:240] if excerpt else "Empty text attachment."
        context_text = f"Text attachment '{attachment.name}' excerpt: {excerpt[:1200] or '[empty]'}"
        kind = "text"
    else:
        preview_text = f"{attachment.name} ({media_type})"
        context_text = f"File attachment '{attachment.name}' ({media_type}) was shared."
        kind = "file"

    resource = ChatAttachmentResource(
        id=attachment_id,
        kind=kind,
        name=attachment.name,
        media_type=media_type,
        size_bytes=attachment.size_bytes or len(raw_bytes),
        preview_text=preview_text,
    )
    return resource, context_text


def _visible_user_text(text: str, attachments: List[ChatAttachmentResource]) -> str:
    stripped = text.strip()
    if stripped:
        return stripped
    if attachments:
        if len(attachments) == 1:
            return f"Shared attachment: {attachments[0].name}"
        return f"Shared {len(attachments)} attachments"
    return ""


def _create_delta_bridge(loop: asyncio.AbstractEventLoop, session_id: str) -> tuple[Any, Any]:
    pending: List[Any] = []
    accumulated = ""

    def on_token(delta: str) -> None:
        nonlocal accumulated
        if not delta:
            return
        accumulated += delta
        future = asyncio.run_coroutine_threadsafe(
            event_bus.publish(
                "message.delta",
                {
                    "message_id": None,
                    "delta": delta,
                    "content": accumulated,
                },
                session_id=session_id,
                source="chat",
            ),
            loop,
        )
        pending.append(future)

    async def flush() -> None:
        for future in pending:
            await asyncio.wrap_future(future)

    return on_token, flush


def _parse_memory_tags(raw_tags: Any) -> List[str]:
    if isinstance(raw_tags, list):
        return [str(tag) for tag in raw_tags]
    if not raw_tags:
        return []
    try:
        parsed = json.loads(raw_tags)
    except (TypeError, ValueError):
        return []
    if isinstance(parsed, list):
        return [str(tag) for tag in parsed]
    return []


def _memory_resource(memory) -> MemoryResource:
    return MemoryResource(
        id=memory.id,
        type=memory.type,
        text=memory.text,
        tags=_parse_memory_tags(getattr(memory, "tags", [])),
        created_at=memory.created_at,
        memory_type=getattr(memory, "memory_type", "episodic"),
    )


def _memory_search_item_resource(item: Dict[str, Any]) -> MemorySearchItemResource:
    return MemorySearchItemResource(
        text=item.get("text", ""),
        metadata=item.get("metadata", {}),
        distance=float(item.get("distance", 0.0)),
        source=item.get("source", "vector"),
        matched_entity=item.get("matched_entity"),
    )


def _user_profile_resource(profile: UserProfile | None, user_id: str = "default") -> UserProfileResource:
    if profile is None:
        return UserProfileResource(user_id=user_id)
    return UserProfileResource(
        user_id=profile.user_id,
        name=profile.name,
        email=profile.email,
        birthday=profile.birthday,
        hobbies=profile.hobbies,
        relationships=profile.relationships,
        notes=profile.notes,
        therapeutic_mode=profile.therapeutic_mode,
        personality=profile.personality,
        humor_level=profile.humor_level,
    )


def _mood_resource(mood) -> MoodEntryResource:
    return MoodEntryResource(
        id=mood.id,
        user_id=mood.user_id,
        date=mood.date,
        mood=mood.mood,
    )


def _habit_resource(habit) -> HabitResource:
    return HabitResource(
        id=habit.id,
        user_id=habit.user_id,
        name=habit.name,
        streak=habit.streak,
        last_done=habit.last_done,
    )


def _goal_resource(goal) -> GoalResource:
    return GoalResource(
        id=goal.id,
        user_id=goal.user_id,
        name=goal.name,
        description=goal.description,
        linked_habit_id=goal.linked_habit_id,
        linked_decision_id=goal.linked_decision_id,
        status=goal.status,
    )


def _decision_resource(decision) -> DecisionResource:
    return DecisionResource(
        id=decision.id,
        user_id=decision.user_id,
        question=decision.question,
        pros=decision.pros,
        cons=decision.cons,
        outcome=decision.outcome,
    )


def _exercise_resource(exercise) -> CbtExerciseResource:
    return CbtExerciseResource(
        id=exercise.id,
        user_id=exercise.user_id,
        name=exercise.name,
        description=exercise.description,
        completed_count=exercise.completed_count,
    )


def _activity_resource(activity) -> ActivityLogResource:
    return ActivityLogResource(
        id=activity.id,
        user_id=activity.user_id,
        app=activity.app,
        duration=activity.duration,
        timestamp=activity.timestamp,
    )


def _sleep_resource(sleep) -> SleepLogResource:
    return SleepLogResource(
        id=sleep.id,
        user_id=sleep.user_id,
        date=sleep.date,
        hours_slept=sleep.hours_slept,
        quality=sleep.quality,
    )


def _transaction_resource(transaction) -> TransactionResource:
    return TransactionResource(
        id=transaction.id,
        user_id=transaction.user_id,
        date=transaction.date,
        amount=transaction.amount,
        category=transaction.category,
    )


def _contact_resource(contact) -> ContactResource:
    return ContactResource(
        id=contact.id,
        user_id=contact.user_id,
        name=contact.name,
        last_contact=contact.last_contact,
        strength=contact.strength,
        entity_id=contact.entity_id,
    )


def _planner_snapshot_resource(snapshot: Dict[str, Any]) -> PlannerSnapshotResource:
    return PlannerSnapshotResource(
        user_id=snapshot.get("user_id", "default"),
        latest_mood=int(snapshot.get("latest_mood", 5)),
        mood_trend=snapshot.get("mood_trend", {}),
        health_correlation=snapshot.get("health_correlation", {}),
        overdue_contacts=snapshot.get("overdue_contacts", []),
        active_goals=[goal.name for goal in snapshot.get("goals", []) if getattr(goal, "status", "active") == "active"],
        habits=[habit.name for habit in snapshot.get("habits", [])],
    )


def _profile_response(user_id: str) -> ProfileResponse:
    profile = memory_store.get_user_profile(user_id)
    moods = memory_store.get_recent_moods(user_id, limit=14)
    habits = memory_store.get_habits(user_id)
    goals = memory_store.get_personal_goals(user_id)
    decisions = sorted(memory_store.get_decisions(user_id), key=lambda decision: decision.id, reverse=True)
    exercises = memory_store.get_cbt_exercises(user_id)
    activities = memory_store.get_recent_activities(user_id, limit=10)
    sleeps = memory_store.get_recent_sleeps(user_id, limit=10)
    transactions = memory_store.get_recent_transactions(user_id, limit=10)
    contacts = memory_store.get_contacts(user_id, limit=50)

    return ProfileResponse(
        profile=_user_profile_resource(profile, user_id=user_id),
        moods=[_mood_resource(mood) for mood in moods],
        habits=[_habit_resource(habit) for habit in habits],
        goals=[_goal_resource(goal) for goal in goals],
        decisions=[_decision_resource(decision) for decision in decisions],
        exercises=[_exercise_resource(exercise) for exercise in exercises],
        activities=[_activity_resource(activity) for activity in activities],
        sleeps=[_sleep_resource(sleep) for sleep in sleeps],
        transactions=[_transaction_resource(transaction) for transaction in transactions],
        contacts=[_contact_resource(contact) for contact in contacts],
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(limit: int = Query(default=50, ge=1, le=200)):
    sessions = memory_store.list_sessions(limit=limit)
    return SessionListResponse(sessions=[_session_resource(session) for session in sessions])


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session(request: SessionCreateRequest):
    session_id = request.session_id or str(uuid.uuid4())
    session = memory_store.create_session(session_id, user_id=request.user_id, title=request.title)
    await event_bus.publish(
        "session.created",
        {
            "session": _session_resource(session).model_dump(mode="json"),
        },
        session_id=session.id,
        source="sessions",
    )
    return SessionCreateResponse(session=_session_resource(session))


@router.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
async def get_session_messages(session_id: str, limit: int = Query(default=100, ge=1, le=500)):
    session = memory_store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = memory_store.get_chat_history(session_id)[-limit:]
    return MessageListResponse(
        session=_session_resource(session),
        messages=[_message_resource(message) for message in messages],
    )


@router.get("/memory/recent", response_model=MemoryRecentResponse)
async def get_recent_memories(
    limit: int = Query(default=20, ge=1, le=100),
    mem_type: str | None = None,
    memory_type: str | None = None,
):
    memories = memory_store.get_recent_memories(
        limit=limit,
        mem_type=mem_type,
        memory_type=memory_type,
    )
    return MemoryRecentResponse(memories=[_memory_resource(memory) for memory in memories])


@router.get("/memory/search", response_model=MemorySearchResponseV2)
async def search_memory(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=5, ge=1, le=50),
    filter_type: str | None = None,
    memory_type: str | None = None,
    mode: str = Query(default="graph", pattern="^(graph|vector)$"),
):
    if mode == "graph":
        items = memory_store.graph_rag_search(query, k=limit)
    else:
        items = memory_store.search_embeddings(
            query,
            k=limit,
            filter_type=filter_type,
            memory_type=memory_type,
        )
    return MemorySearchResponseV2(
        query=query,
        items=[_memory_search_item_resource(item) for item in items],
    )


@router.post("/chat", response_model=V2ChatResponse)
async def chat_v2(request: V2ChatRequest):
    history = memory_store.get_chat_history(request.session_id)
    attachment_resources: List[ChatAttachmentResource] = []
    attachment_contexts: List[str] = []
    for attachment in request.attachments:
        resource, context_text = _attachment_context(attachment)
        attachment_resources.append(resource)
        attachment_contexts.append(context_text)

    visible_user_text = _visible_user_text(request.text, attachment_resources)

    await event_bus.publish(
        "message.received",
        {
            "text": visible_user_text,
            "history_count": len(history),
            "attachments": [attachment.model_dump(mode="json") for attachment in attachment_resources],
        },
        session_id=request.session_id,
        source="chat",
    )
    await event_bus.publish(
        "response.started",
        {
            "status": "processing",
        },
        session_id=request.session_id,
        source="chat",
    )
    loop = asyncio.get_running_loop()
    on_token, flush_deltas = _create_delta_bridge(loop, request.session_id)
    response = await asyncio.to_thread(
        agent.reply,
        history,
        visible_user_text,
        request.session_id,
        on_token=on_token,
        attachment_contexts=attachment_contexts,
    )
    await flush_deltas()
    session = memory_store.get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=500, detail="Session record missing after chat")

    messages = memory_store.get_chat_history(request.session_id)
    user_message = next((msg for msg in reversed(messages) if msg.id == response.user_message_id), None)
    assistant_message = next((msg for msg in reversed(messages) if msg.id == response.assistant_message_id), None)
    if user_message is None or assistant_message is None:
        raise HTTPException(status_code=500, detail="Chat message records missing after reply")

    user_message_resource = _message_resource(user_message).model_copy(
        update={"content": visible_user_text}
    )
    assistant_message_resource = _message_resource(assistant_message)
    tool_call_resources = _tool_call_resources(response.tool_calls)

    pending_approvals = []
    for tool_call in response.tool_calls:
        if tool_call.get("status") == "pending":
            approval_id = approval_manager.request_approval(
                tool_call.get("tool_name", ""),
                tool_call.get("args", {}),
                session_id=request.session_id,
            )
            approval = approval_manager.get(approval_id)
            if approval is not None:
                approval_resource = _approval_resource(approval)
                pending_approvals.append(approval_resource)
                await event_bus.publish(
                    "approval.requested",
                    {
                        "approval": approval_resource.model_dump(mode="json"),
                    },
                    session_id=request.session_id,
                    source="approvals",
                )

    craving_engine = CravingEngine(memory_store)
    avatar_expression = craving_engine.get_craving_expression(request.session_id)
    voice_hint = "whisper" if response.craving_score >= 60 else "default"
    avatar_resource = AvatarCueResource(
        expression=avatar_expression,
        voice_hint=voice_hint,
        should_speak=bool(assistant_message.content),
    )

    await event_bus.publish(
        "message.created",
        {
            "role": "user",
            "message": user_message_resource.model_dump(mode="json"),
            "attachments": [attachment.model_dump(mode="json") for attachment in attachment_resources],
        },
        session_id=request.session_id,
        source="chat",
    )
    await event_bus.publish(
        "message.completed",
        {
            "message": assistant_message_resource.model_dump(mode="json"),
            "attachments": [attachment.model_dump(mode="json") for attachment in attachment_resources],
            "provider": {
                "selected": response.provider,
                "route": response.route,
                "errors": response.errors,
            },
            "emotion": {
                "craving_score": response.craving_score,
                "is_dramatic_return": response.is_dramatic_return,
            },
            "tool_calls": [tool_call.model_dump(mode="json") for tool_call in tool_call_resources],
        },
        session_id=request.session_id,
        source="chat",
    )
    await event_bus.publish(
        "avatar.state",
        {
            "avatar": avatar_resource.model_dump(mode="json"),
        },
        session_id=request.session_id,
        source="avatar",
    )

    return V2ChatResponse(
        session=_session_resource(session),
        user_message=user_message_resource,
        assistant_message=assistant_message_resource,
        attachments=attachment_resources,
        tool_calls=tool_call_resources,
        pending_approvals=pending_approvals,
        emotion=EmotionResource(
            craving_score=response.craving_score,
            is_dramatic_return=response.is_dramatic_return,
        ),
        provider=ProviderResource(
            selected=response.provider,
            route=response.route,
            errors=response.errors,
        ),
        avatar=avatar_resource,
    )


@router.get("/approvals", response_model=ApprovalListResponse)
async def list_approvals(session_id: str | None = None):
    approvals = approval_manager.get_pending()
    if session_id is not None:
        approvals = [approval for approval in approvals if approval.session_id == session_id]
    return ApprovalListResponse(approvals=[_approval_resource(approval) for approval in approvals])


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalDecisionResponse)
async def approve_action(approval_id: str):
    approval = approval_manager.approve(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")

    tool_result = agent.run_tool(approval.tool_name, approval.args)
    approval_resource = _approval_resource(approval)
    tool_result_resource = ToolCallResource(**tool_result)
    await event_bus.publish(
        "approval.resolved",
        {
            "approval": approval_resource.model_dump(mode="json"),
            "decision": "approved",
        },
        session_id=approval.session_id,
        source="approvals",
    )
    await event_bus.publish(
        "tool.completed",
        {
            "tool_call": tool_result_resource.model_dump(mode="json"),
        },
        session_id=approval.session_id,
        source="tools",
    )
    return ApprovalDecisionResponse(
        approval=approval_resource,
        tool_result=tool_result_resource,
    )


@router.post("/approvals/{approval_id}/deny", response_model=ApprovalDecisionResponse)
async def deny_action(approval_id: str):
    approval = approval_manager.deny(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    approval_resource = _approval_resource(approval)
    await event_bus.publish(
        "approval.resolved",
        {
            "approval": approval_resource.model_dump(mode="json"),
            "decision": "denied",
        },
        session_id=approval.session_id,
        source="approvals",
    )
    return ApprovalDecisionResponse(approval=approval_resource)


@router.get("/media/session", response_model=MediaSessionResponse)
async def get_media_session(session_id: str):
    return MediaSessionResponse(
        media_session=_media_session_resource(media_sessions.get(session_id))
    )


@router.patch("/media/session", response_model=MediaSessionResponse)
async def patch_media_session(request: MediaSessionPatchRequest):
    current = media_sessions.get(request.session_id)
    patch = request.model_dump(exclude={"session_id", "interrupted"}, exclude_none=True)
    if request.interrupted:
        patch["interruption_count"] = int(current.get("interruption_count", 0)) + 1
    state = media_sessions.update(request.session_id, **patch)
    await _publish_media_session(request.session_id, state)
    return MediaSessionResponse(media_session=_media_session_resource(state))


@router.post("/media/transcribe", response_model=MediaTranscribeResponse)
async def transcribe_media(request: MediaTranscribeRequest):
    try:
        decoded_type, raw_bytes = _decode_data_url(request.data_url)
    except Exception as exc:
        state = media_sessions.update(
            request.session_id,
            mic_state="error",
            last_error=str(exc),
        )
        await _publish_media_session(request.session_id, state)
        raise HTTPException(status_code=400, detail=f"Unsupported audio payload: {exc}") from exc

    media_type = request.media_type or decoded_type
    processing_state = media_sessions.update(
        request.session_id,
        mic_state="processing",
        capture_source="browser",
        last_error=None,
    )
    await _publish_media_session(request.session_id, processing_state)

    started = datetime.utcnow()
    try:
        transcript = await asyncio.to_thread(_transcribe_browser_audio, raw_bytes, media_type)
    except Exception as exc:
        latency_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
        failed_state = media_sessions.update(
            request.session_id,
            mic_state="error",
            capture_source="browser",
            recognition_latency_ms=latency_ms,
            last_error=str(exc),
        )
        await _publish_media_session(request.session_id, failed_state)
        await event_bus.publish(
            "media.transcription.failed",
            {
                "transcript": "",
                "media_type": media_type,
                "duration_ms": request.duration_ms,
                "latency_ms": latency_ms,
                "error": str(exc),
                "media_session": _media_session_resource(failed_state).model_dump(mode="json"),
            },
            session_id=request.session_id,
            source="media",
        )
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc

    latency_ms = int((datetime.utcnow() - started).total_seconds() * 1000)

    final_state = media_sessions.update(
        request.session_id,
        mic_state="idle" if transcript else "error",
        capture_source="browser",
        last_transcript=transcript,
        recognition_latency_ms=latency_ms,
        last_error=None if transcript else "Transcription returned empty text",
    )
    await _publish_media_session(request.session_id, final_state)

    event_name = "media.transcription.completed" if transcript else "media.transcription.failed"
    await event_bus.publish(
        event_name,
        {
            "transcript": transcript,
            "media_type": media_type,
            "duration_ms": request.duration_ms,
            "latency_ms": latency_ms,
            "media_session": _media_session_resource(final_state).model_dump(mode="json"),
        },
        session_id=request.session_id,
        source="media",
    )
    return MediaTranscribeResponse(
        media_session=_media_session_resource(final_state),
        transcript=transcript,
        media_type=media_type,
        duration_ms=request.duration_ms,
        latency_ms=latency_ms,
    )


@router.post("/avatar/sync", response_model=AvatarSyncResponse)
async def avatar_sync(request: AvatarSyncRequest):
    sync_data = agent.say_and_sync(request.text, request.session_id)
    media_state = media_sessions.update(
        request.session_id,
        speaking_state="queued",
        playback_latency_ms=0,
        last_error=None,
    )
    response = AvatarSyncResponse(
        session_id=request.session_id,
        audio_url=sync_data.get("audio_url", ""),
        phoneme_timeline=sync_data.get("phoneme_timeline", []),
        sentiment=sync_data.get("sentiment", "neutral"),
        delivery_style=sync_data.get("delivery_style", "normal"),
    )
    await _publish_media_session(request.session_id, media_state)
    await event_bus.publish(
        "tts.ready",
        {
            "audio_url": response.audio_url,
            "phoneme_timeline": response.phoneme_timeline,
            "sentiment": response.sentiment,
            "delivery_style": response.delivery_style,
            "media_session": _media_session_resource(media_state).model_dump(mode="json"),
        },
        session_id=request.session_id,
        source="avatar",
    )
    return response


def _perception_policy_resource(policy: dict) -> PerceptionPolicyResource:
    return PerceptionPolicyResource(
        camera_enabled=policy.get("camera_enabled", True),
        retain_expressions=policy.get("retain_expressions", False),
        retain_snapshots=policy.get("retain_snapshots", False),
        retention_days=policy.get("retention_days", 0),
        last_updated=policy.get("last_updated"),
    )


@router.get("/perception/policy", response_model=PerceptionPolicyResponse)
async def get_perception_policy():
    return PerceptionPolicyResponse(policy=_perception_policy_resource(perception_policy.get()))


@router.patch("/perception/policy", response_model=PerceptionPolicyResponse)
async def patch_perception_policy(request: PerceptionPolicyPatchRequest):
    patch = request.model_dump(exclude_none=True)
    if not patch:
        raise HTTPException(status_code=400, detail="No fields provided")
    try:
        updated = perception_policy.update(patch)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unknown policy field: {exc}") from exc
    await event_bus.publish(
        "settings.updated",
        {"scope": "perception_policy", "policy": updated},
        source="settings",
    )
    return PerceptionPolicyResponse(policy=_perception_policy_resource(updated))


@router.post("/vision/analyze", response_model=VisionAnalyzeResponse)
async def analyze_vision_snapshot(request: VisionAnalyzeRequest):
    try:
        from PIL import Image
        _, raw_bytes = _decode_data_url(request.data_url)
        image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
        description = vision_clip.describe_image(image)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Image processing failed: {exc}") from exc

    # Extract simple word-level tags from the description
    stop_words = {"a", "an", "the", "is", "of", "in", "on", "at", "to", "and", "with", "are"}
    tags = [
        word.strip(".,").lower()
        for word in description.split()
        if len(word) > 4 and word.lower() not in stop_words
    ][:6]

    captured_at = datetime.utcnow().isoformat() + "Z"

    # Persist to memory only when the user has opted in via retention policy
    policy = perception_policy.get()
    if policy.get("retain_snapshots"):
        await memory_store.add_memory_async(
            "perception",
            f"Visual scene captured: {description}",
            ["snapshot", "visual", "perception"],
        )

    await event_bus.publish(
        "perception.snapshot",
        {
            "description": description,
            "tags": tags,
            "captured_at": captured_at,
        },
        session_id=request.session_id,
        source="perception",
    )

    return VisionAnalyzeResponse(
        session_id=request.session_id,
        description=description,
        tags=tags,
        captured_at=captured_at,
    )


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(user_id: str = "default"):
    return _profile_response(user_id)


@router.patch("/profile", response_model=ProfileResponse)
async def patch_profile(request: ProfilePatchRequest, user_id: str = "default"):
    profile = memory_store.get_user_profile(user_id) or UserProfile(user_id=user_id)
    for key, value in request.model_dump(exclude_none=True).items():
        setattr(profile, key, value)
    memory_store.save_user_profile(profile)
    return _profile_response(user_id)


@router.post("/profile/moods", response_model=MoodEntryCreateResponse)
async def create_mood_entry(request: MoodEntryCreateRequest):
    mood = memory_store.add_mood_entry(
        MoodEntry(
            user_id=request.user_id,
            date=request.date or datetime.utcnow(),
            mood=request.mood,
        )
    )
    return MoodEntryCreateResponse(mood=_mood_resource(mood))


@router.post("/profile/habits", response_model=HabitCreateResponse)
async def create_habit(request: HabitCreateRequest):
    habit = memory_store.add_habit(Habit(user_id=request.user_id, name=request.name))
    return HabitCreateResponse(habit=_habit_resource(habit))


@router.post("/profile/habits/{habit_id}/complete", response_model=HabitCreateResponse)
async def complete_habit(habit_id: int, user_id: str = "default"):
    habits = [habit for habit in memory_store.get_habits(user_id) if habit.id == habit_id]
    habit = habits[0] if habits else None
    if habit is None:
        raise HTTPException(status_code=404, detail="Habit not found")

    now = datetime.utcnow()
    if habit.last_done and habit.last_done.date() == now.date():
        streak = habit.streak
    elif habit.last_done and (now.date() - habit.last_done.date()).days == 1:
        streak = habit.streak + 1
    else:
        streak = 1

    updated = memory_store.update_habit_streak(habit_id, streak, now)
    if updated is None:
        raise HTTPException(status_code=404, detail="Habit not found")
    return HabitCreateResponse(habit=_habit_resource(updated))


@router.post("/profile/goals", response_model=GoalCreateResponse)
async def create_goal(request: GoalCreateRequest):
    goal = memory_store.add_personal_goal(
        PersonalGoal(
            user_id=request.user_id,
            name=request.name,
            description=request.description,
            linked_habit_id=request.linked_habit_id,
            linked_decision_id=request.linked_decision_id,
        )
    )
    return GoalCreateResponse(goal=_goal_resource(goal))


@router.post("/profile/goals/{goal_id}/complete", response_model=GoalCreateResponse)
async def complete_goal(goal_id: int):
    goal = memory_store.update_goal_status(goal_id, "completed")
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return GoalCreateResponse(goal=_goal_resource(goal))


@router.post("/profile/cbt-exercises", response_model=CbtExerciseCreateResponse)
async def create_cbt_exercise(request: CbtExerciseCreateRequest):
    exercise = memory_store.add_cbt_exercise(
        CbtExercise(
            user_id=request.user_id,
            name=request.name,
            description=request.description,
        )
    )
    return CbtExerciseCreateResponse(exercise=_exercise_resource(exercise))


@router.post("/profile/cbt-exercises/{exercise_id}/complete", response_model=CbtExerciseCreateResponse)
async def complete_cbt_exercise(exercise_id: int):
    exercise = memory_store.complete_cbt_exercise(exercise_id)
    if exercise is None:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return CbtExerciseCreateResponse(exercise=_exercise_resource(exercise))


@router.post("/profile/activities", response_model=ActivityLogCreateResponse)
async def create_activity(request: ActivityLogCreateRequest):
    activity = memory_store.add_activity_log(
        ActivityLog(
            user_id=request.user_id,
            app=request.app,
            duration=request.duration,
        )
    )
    return ActivityLogCreateResponse(activity=_activity_resource(activity))


@router.post("/profile/sleeps", response_model=SleepLogCreateResponse)
async def create_sleep_log(request: SleepLogCreateRequest):
    sleep = memory_store.add_sleep_log(
        request.hours_slept,
        quality=request.quality,
        log_date=request.date,
        user_id=request.user_id,
    )
    return SleepLogCreateResponse(sleep=_sleep_resource(sleep))


@router.post("/profile/transactions", response_model=TransactionCreateResponse)
async def create_transaction(request: TransactionCreateRequest):
    transaction = memory_store.add_transaction(
        request.amount,
        request.category,
        log_date=request.date,
        user_id=request.user_id,
    )
    return TransactionCreateResponse(transaction=_transaction_resource(transaction))


@router.post("/profile/contacts", response_model=ContactCreateResponse)
async def create_contact(request: ContactCreateRequest):
    contact = memory_store.add_contact(
        request.name,
        last_contact=request.last_contact,
        strength=request.strength,
        entity_id=request.entity_id,
        user_id=request.user_id,
    )
    return ContactCreateResponse(contact=_contact_resource(contact))


@router.get("/planner/context", response_model=PlannerContextResponse)
async def get_planner_context(user_id: str = "default"):
    snapshot = build_planner_snapshot(memory_store, user_id=user_id)
    return PlannerContextResponse(snapshot=_planner_snapshot_resource(snapshot))


@router.post("/planner/generate", response_model=PlannerGenerateResponse)
async def generate_planner(request: PlannerGenerateRequest):
    plan = generate_day_plan(
        memory_store,
        user_id=request.user_id,
        key_tasks=request.key_tasks,
        focus_areas=request.focus_areas,
        energy_level=request.energy_level,
    )
    return PlannerGenerateResponse(
        provider=plan["provider"],
        model=plan["model"],
        blocks=[PlannerBlockResource(**block) for block in plan["blocks"]],
        snapshot=_planner_snapshot_resource(plan["snapshot"]),
    )


@router.get("/settings", response_model=SettingsResponse)
async def get_settings():
    return SettingsResponse(settings=_settings_resource())


@router.patch("/settings", response_model=SettingsResponse)
async def patch_settings(request: SettingsPatchRequest):
    update_data = request.model_dump(exclude_none=True)
    invalid = sorted(set(update_data) - set(runtime_settings.get()))
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unsupported settings keys: {', '.join(invalid)}")
    try:
        runtime_settings.update(update_data)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"Unsupported settings key: {exc.args[0]}") from exc
    settings_response = SettingsResponse(settings=_settings_resource())
    await event_bus.publish(
        "settings.updated",
        {
            "settings": settings_response.settings.model_dump(mode="json"),
            "updated_keys": sorted(update_data.keys()),
        },
        source="settings",
    )
    return settings_response


@router.get("/events", response_model=RealtimeEventsResponse)
async def get_recent_events(
    session_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    events = await event_bus.get_recent(session_id=session_id, limit=limit)
    return RealtimeEventsResponse(events=[_event_resource(event) for event in events])


@router.get("/events/stream")
async def stream_events(
    request: Request,
    session_id: str | None = None,
    backfill: int = Query(default=10, ge=0, le=100),
):
    async def event_generator():
        if backfill:
            recent = await event_bus.get_recent(session_id=session_id, limit=backfill)
            for event in recent:
                yield format_sse_event(event)

        subscriber_id, queue = await event_bus.subscribe(session_id=session_id)
        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield format_sse_event(event)
                except asyncio.TimeoutError:
                    heartbeat = {
                        "api_version": "v2",
                        "event_id": f"heartbeat-{uuid.uuid4()}",
                        "event": "heartbeat",
                        "source": "system",
                        "session_id": session_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "payload": {},
                    }
                    yield format_sse_event(heartbeat)
        finally:
            await event_bus.unsubscribe(subscriber_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

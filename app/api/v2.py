from __future__ import annotations

import asyncio
import base64
import binascii
import json
import io
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.hardware.schemas import HardwareBridgeContractResponse, HardwareStateName
from app.api.realtime import format_sse_event
from app.api.state import (
    agent,
    approval_manager,
    context_events,
    desktop_action_broker,
    event_bus,
    hardware_bridge,
    initiative_service,
    life_state_engine,
    media_sessions,
    memory_store,
    mqtt_bridge,
    perception_policy,
    runtime_settings,
    telegram_outbox,
    user_model_corrections,
    user_model_synthesis_records,
)
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
    ApprovalDecisionRequest,
    SynthesisCandidateResource,
    SynthesisRecordListResponse,
    SynthesisRecordResource,
    SynthesisResponse,
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
    ConnectorDisconnectRequest,
    ConnectorDisconnectResponse,
    ConnectorListResponse,
    ConnectorResource,
    DecisionResource,
    DesktopActionRequest,
    DesktopActionResponse,
    DesktopActionResultResource,
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
    OutboxAckRequest,
    OutboxAckResponse,
    OutboxClaimRequest,
    OutboxClaimResponse,
    OutboxMessageResource,
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
    UserModelCorrectionResource,
    UserModelCorrectionRequest,
    UserModelCorrectionResponse,
    UserModelEvidenceResource,
    UserModelItemResource,
    UserModelPolicyResource,
    UserModelResponse,
    UserModelSectionResource,
    UserProfileResource,
    V2ChatRequest,
    V2ChatResponse,
    PerceptionContextRequest,
    PerceptionPolicyPatchRequest,
    PerceptionPolicyResource,
    PerceptionPolicyResponse,
    VisionAnalyzeRequest,
    VisionAnalyzeResponse,
)
from app.orchestrator.day_planner import build_planner_snapshot, generate_day_plan
from app.orchestrator.craving_engine import CravingEngine
from app.orchestrator.security.approval import (
    ApprovalResolutionError,
    ApprovalStatus,
    PendingApproval,
)
from app.tools import vision_clip
from app.tools import screen_context
from app.tools import calendar_gcal, email_gmail
from app.tools.registry import tool_registry
from app.tools.voice import voice_tools
from app.vault import delete_secret


router = APIRouter(prefix="/api/v2", tags=["v2"])

MAX_DATA_URL_CHARS = 16_000_000
MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024
MAX_AUDIO_BYTES = 12 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000


async def _observe_context_event(**kwargs: Any) -> dict[str, Any]:
    decision = context_events.observe(**kwargs)
    payload = decision.to_dict()
    await event_bus.publish(
        "context.observed" if decision.accepted else "context.suppressed",
        payload,
        session_id=decision.event.session_id,
        source="context",
    )
    return payload


def _connector_resources() -> list[ConnectorResource]:
    return [
        ConnectorResource(
            id="gmail",
            label="Gmail",
            connected=email_gmail.is_authenticated(),
            capabilities=["read", "send"],
            scopes=list(email_gmail.SCOPES),
        ),
        ConnectorResource(
            id="calendar",
            label="Google Calendar",
            connected=calendar_gcal.is_authenticated(),
            capabilities=["read", "create"],
            scopes=list(calendar_gcal.SCOPES),
        ),
    ]


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
        proposal_id=approval.proposal_id,
        session_id=approval.session_id,
        tool_name=approval.tool_name,
        operation=approval.operation,
        args=approval.args,
        preview=approval.preview,
        redacted_preview=approval.redacted_preview,
        args_fingerprint=approval.args_fingerprint,
        local_only=approval.local_only,
        status=approval.status.value if isinstance(approval.status, ApprovalStatus) else str(approval.status),
        created_at=approval.created_at,
        expires_at=approval.expires_at,
        resolved_at=approval.resolved_at,
        consumed_at=approval.consumed_at,
    )


def _tool_call_resources(tool_calls: Iterable[Dict[str, Any]]) -> List[ToolCallResource]:
    return [
        ToolCallResource(
            tool_name=tool_call.get("tool_name", ""),
            args=tool_call.get("args", {}),
            result=tool_call.get("result"),
            status=tool_call.get("status", "success"),
            proposal_id=tool_call.get("proposal_id"),
            operation=tool_call.get("operation"),
            idempotency_key=tool_call.get("idempotency_key"),
        )
        for tool_call in tool_calls
    ]


def _desktop_action_resource(result: Any) -> DesktopActionResultResource:
    return DesktopActionResultResource(
        action_id=result.action_id,
        action=result.action,
        status=result.status,
        summary=result.summary,
        result=result.result,
        audit_record=result.audit_record,
    )


def _settings_resource() -> SettingsResource:
    return SettingsResource(**runtime_settings.get())


def _hardware_contract_response() -> HardwareBridgeContractResponse:
    return HardwareBridgeContractResponse(**hardware_bridge.get_contract())


def _require_local_approval_request(request: Request) -> None:
    client_host = request.client.host if request.client else ""
    local_hosts = {"127.0.0.1", "::1", "localhost", "testclient"}
    if client_host not in local_hosts:
        raise HTTPException(status_code=403, detail="Approvals are local-only")


def _require_local_desktop_action_request(request: Request) -> None:
    client_host = request.client.host if request.client else ""
    local_hosts = {"127.0.0.1", "::1", "localhost", "testclient"}
    if client_host not in local_hosts:
        raise HTTPException(status_code=403, detail="Desktop actions are local-only")


def _event_resource(event: Dict[str, Any]) -> RealtimeEventEnvelope:
    return RealtimeEventEnvelope(**event)


def _media_session_resource(state: Dict[str, Any]) -> MediaSessionResource:
    return MediaSessionResource(**state)


async def _publish_hardware_state_transition(
    state: HardwareStateName,
    *,
    source_event: str,
    session_id: str | None = None,
    reason: str | None = None,
) -> None:
    command, changed = hardware_bridge.set_runtime_state(
        state,
        source_event=source_event,
        session_id=session_id,
        reason=reason,
    )
    if not changed:
        return
    await event_bus.publish(
        "joi.state.changed",
        {
            "state": command["state"],
            "led_state": command["led_state"],
            "hardware_command": command,
        },
        session_id=session_id,
        source="runtime",
    )
    new_life_state = life_state_engine.on_joi_state_changed(str(state))
    if new_life_state is not None:
        await event_bus.publish(
            "avatar.life_state_changed",
            {"life_state": new_life_state},
            session_id=session_id,
            source="runtime",
        )


async def _publish_media_session(session_id: str, state: Dict[str, Any]) -> None:
    command, changed = hardware_bridge.sync_from_media_session(session_id, state)
    if changed:
        await event_bus.publish(
            "joi.state.changed",
            {
                "state": command["state"],
                "led_state": command["led_state"],
                "hardware_command": command,
            },
            session_id=session_id,
            source="runtime",
        )
    await event_bus.publish(
        "media.session.updated",
        {
            "media_session": _media_session_resource(state).model_dump(mode="json"),
        },
        session_id=session_id,
        source="media",
    )


def _decode_data_url(data_url: str, *, max_bytes: int = MAX_ATTACHMENT_BYTES) -> tuple[str, bytes]:
    if len(data_url) > MAX_DATA_URL_CHARS:
        raise ValueError("Payload is too large")
    match = re.match(r"^data:(?P<mime>[^;,]+)(?P<params>(?:;[^,]+)*);base64,(?P<data>.+)$", data_url, re.DOTALL)
    if not match:
        raise ValueError("Unsupported attachment encoding")
    encoded = re.sub(r"\s+", "", match.group("data"))
    estimated_size = (len(encoded) * 3) // 4
    if estimated_size > max_bytes:
        raise ValueError(f"Payload exceeds {max_bytes // (1024 * 1024)}MB limit")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except binascii.Error as exc:
        raise ValueError("Invalid base64 payload") from exc
    if len(raw) > max_bytes:
        raise ValueError(f"Payload exceeds {max_bytes // (1024 * 1024)}MB limit")
    return match.group("mime"), raw


def _normalize_media_type(media_type: str) -> str:
    return media_type.split(";", 1)[0].strip().lower()


def _audio_suffix(media_type: str) -> str:
    normalized = _normalize_media_type(media_type)
    if normalized == "audio/webm":
        return ".webm"
    if normalized == "audio/mp4" or normalized == "audio/m4a":
        return ".m4a"
    if normalized == "audio/mpeg":
        return ".mp3"
    if normalized == "audio/ogg":
        return ".ogg"
    if normalized in {"audio/wav", "audio/x-wav"}:
        return ".wav"
    if normalized == "audio/flac":
        return ".flac"
    return ".bin"


def _convert_audio_to_wav(input_path: str) -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        try:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            ffmpeg = None
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
    normalized_media_type = _normalize_media_type(media_type)
    source_path = None
    converted_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=_audio_suffix(normalized_media_type), delete=False) as source_file:
            source_file.write(raw_bytes)
            source_path = source_file.name

        transcription_path = source_path
        if normalized_media_type not in {"audio/wav", "audio/x-wav", "audio/flac"}:
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

    if attachment.source == "screen_capture":
        policy = perception_policy.get()
        if policy.get("screen_access", "disabled") != "manual_only":
            raise HTTPException(
                status_code=403,
                detail="Screen capture is disabled. Enable manual screen capture in perception settings.",
            )
    elif attachment.source == "camera_snapshot":
        policy = perception_policy.get()
        if not policy.get("camera_enabled", False):
            raise HTTPException(
                status_code=403,
                detail="Camera access is disabled. Enable camera perception before taking a glance.",
            )
        if attachment.kind != "image":
            raise HTTPException(status_code=422, detail="Camera snapshots must be images.")

    try:
        decoded_mime, raw_bytes = _decode_data_url(
            attachment.data_url,
            max_bytes=MAX_ATTACHMENT_BYTES,
        )
    except Exception as exc:
        resource = ChatAttachmentResource(
            id=attachment_id,
            kind=attachment.kind,
            name=attachment.name,
            media_type=attachment.media_type,
            size_bytes=attachment.size_bytes or 0,
            preview_text=f"Attachment decode failed: {exc}",
            source=attachment.source,
            capture_metadata=screen_context.sanitize_capture_metadata(
                attachment.capture_metadata
            ),
            ocr_status="unavailable" if attachment.source == "screen_capture" else None,
        )
        return resource, f"User attached '{attachment.name}', but the file could not be decoded."

    media_type = attachment.media_type or decoded_mime
    if attachment.source == "camera_snapshot" and not _normalize_media_type(decoded_mime).startswith("image/"):
        raise HTTPException(status_code=422, detail="Camera snapshots must contain image data.")
    preview_text: str | None = None
    context_text: str

    if attachment.kind == "image" or media_type.startswith("image/"):
        try:
            from PIL import Image

            Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
            image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
            capture_metadata = screen_context.sanitize_capture_metadata(
                attachment.capture_metadata
            )
            if attachment.source == "screen_capture":
                preview_text = vision_clip.describe_image(image)
                ocr_text, ocr_status = screen_context.extract_local_ocr(image)
                screen_summary = screen_context.build_screen_context(
                    visual_description=preview_text,
                    ocr_text=ocr_text,
                    metadata=capture_metadata,
                )
                context_text = f"Screen capture '{attachment.name}':\n{screen_summary}"
            elif attachment.source == "camera_snapshot":
                ocr_status = "not_requested"
                vision_result = vision_clip.describe_image_result(image)
                if vision_result.ok:
                    preview_text = vision_result.description
                    context_text = (
                        f"[Camera glance] You just took a live look through the camera. You can see: "
                        f"{preview_text}. Describe this as your own seeing — warmly and honestly, in your "
                        f"own voice — not as a file or 'attachment'. The captioning is rough, so treat "
                        f"specifics as an impression and don't over-claim detail."
                    )
                else:
                    preview_text = "Camera glance could not be analyzed."
                    context_text = (
                        "[Camera glance unavailable] A consented live frame was captured, but visual "
                        "analysis failed. Do not claim to see any details from it. Briefly say you "
                        "couldn't make out the image and invite the user to try again."
                    )
            else:
                preview_text = vision_clip.describe_image(image)
                ocr_status = "not_requested"
                context_text = (
                    f"Image attachment '{attachment.name}' described as: {preview_text}"
                )
            kind = "image"
        except Exception as exc:
            if attachment.source == "camera_snapshot":
                preview_text = "Camera glance could not be processed."
                context_text = (
                    "[Camera glance unavailable] A consented live frame was captured, but it was "
                    "not a usable image. Do not claim to see any details from it. Briefly invite "
                    "the user to try again."
                )
            else:
                preview_text = f"Image processing failed: {exc}"
                context_text = f"Image attachment '{attachment.name}' could not be processed."
            kind = "image"
            capture_metadata = screen_context.sanitize_capture_metadata(
                attachment.capture_metadata
            )
            ocr_status = "unavailable" if attachment.source == "screen_capture" else None
    elif attachment.kind == "text" or media_type.startswith("text/"):
        excerpt = raw_bytes.decode("utf-8", errors="replace").strip()
        preview_text = excerpt[:240] if excerpt else "Empty text attachment."
        context_text = f"Text attachment '{attachment.name}' excerpt: {excerpt[:1200] or '[empty]'}"
        kind = "text"
        capture_metadata = {}
        ocr_status = None
    else:
        preview_text = f"{attachment.name} ({media_type})"
        context_text = f"File attachment '{attachment.name}' ({media_type}) was shared."
        kind = "file"
        capture_metadata = {}
        ocr_status = None

    resource = ChatAttachmentResource(
        id=attachment_id,
        kind=kind,
        name=attachment.name,
        media_type=media_type,
        size_bytes=attachment.size_bytes or len(raw_bytes),
        preview_text=preview_text,
        source=attachment.source,
        capture_metadata=capture_metadata,
        ocr_status=ocr_status,
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


def _assistant_turn_is_active(session_id: str, client_turn_id: str) -> bool:
    state = media_sessions.get(session_id)
    return (
        state.get("assistant_turn_id") == client_turn_id
        and state.get("turn_state") != "interrupted"
    )


def _create_delta_bridge(
    loop: asyncio.AbstractEventLoop,
    session_id: str,
    client_turn_id: str,
) -> tuple[Any, Any]:
    pending: List[Any] = []
    accumulated = ""

    def on_token(delta: str) -> None:
        nonlocal accumulated
        if not delta or not _assistant_turn_is_active(session_id, client_turn_id):
            return
        accumulated += delta
        future = asyncio.run_coroutine_threadsafe(
            event_bus.publish(
                "message.delta",
                {
                    "message_id": None,
                    "delta": delta,
                    "content": accumulated,
                    "client_turn_id": client_turn_id,
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


_USER_MODEL_SECTION_META: Dict[str, tuple[str, str]] = {
    "active_projects": (
        "Active projects",
        "Projects or workstreams that currently matter to the user.",
    ),
    "recurring_worries": (
        "Recurring worries",
        "Concerns that appear repeatedly across sessions.",
    ),
    "stated_goals": (
        "Stated goals",
        "Goals the user explicitly stated or confirmed.",
    ),
    "important_people": (
        "Important people",
        "People the user mentions or marks as important.",
    ),
    "mood_trend": (
        "Mood trend",
        "Recent emotional baseline and notable changes.",
    ),
    "communication_preferences": (
        "Communication preferences",
        "How the user prefers Joi to respond.",
    ),
    "recent_wins": (
        "Recent wins",
        "Positive outcomes worth remembering.",
    ),
    "open_loops": (
        "Open loops",
        "Unresolved decisions, promises, or follow-ups.",
    ),
    "character_notes": (
        "Character notes",
        "Joi's cautious read on the user's current tone and state.",
    ),
}


def _user_model_evidence(
    source_type: str,
    *,
    source_id: str | None = None,
    summary: str,
    observed_at: Any | None = None,
) -> UserModelEvidenceResource:
    if isinstance(observed_at, (datetime,)):
        observed = observed_at.isoformat()
    elif observed_at is not None:
        observed = str(observed_at)
    else:
        observed = None
    return UserModelEvidenceResource(
        source_type=source_type,  # type: ignore[arg-type]
        source_id=source_id,
        summary=summary,
        observed_at=observed,
    )


def _user_model_item(
    *,
    section_key: str,
    item_id: str,
    label: str,
    value: str,
    category: str,
    confidence: float,
    evidence: List[UserModelEvidenceResource],
    user_confirmed: bool = False,
    lifecycle: str = "active",
) -> UserModelItemResource:
    observed = [item.observed_at for item in evidence if item.observed_at]
    return UserModelItemResource(
        id=f"{section_key}:{item_id}",
        label=label,
        value=value,
        category=category,
        confidence=confidence,
        evidence_count=len(evidence),
        first_seen=min(observed) if observed else None,
        last_seen=max(observed) if observed else None,
        lifecycle=lifecycle,  # type: ignore[arg-type]
        user_confirmed=user_confirmed,
        hidden=False,
        source_summary="Projected from explicit profile data; not inferred yet.",
        evidence=evidence,
    )


def _user_model_section(key: str, items: List[UserModelItemResource]) -> UserModelSectionResource:
    title, description = _USER_MODEL_SECTION_META[key]
    return UserModelSectionResource(
        key=key,  # type: ignore[arg-type]
        title=title,
        description=description,
        items=items,
    )


def _user_model_correction_resource(record: Dict[str, Any]) -> UserModelCorrectionResource:
    return UserModelCorrectionResource(
        id=str(record.get("id", "")),
        user_id=str(record.get("user_id", "default")),
        section_key=str(record.get("section_key", "character_notes")),  # type: ignore[arg-type]
        action=str(record.get("action", "confirm")),  # type: ignore[arg-type]
        item_id=record.get("item_id"),
        label=record.get("label"),
        value=record.get("value"),
        note=record.get("note"),
        created_at=str(record.get("created_at", "")),
    )


def _synthesis_candidate_resources(candidates: Iterable[Any]) -> List[SynthesisCandidateResource]:
    return [
        SynthesisCandidateResource(
            candidate_id=c.candidate_id,
            section_key=c.section_key,
            label=c.label,
            value=c.value,
            confidence=c.confidence,
            inference_method=c.inference_method,
            trigger_phrase=c.trigger_phrase,
            source_excerpt=c.source_excerpt,
            source_message_role=c.source_message_role,
            source_message_index=c.source_message_index,
            blocked_by_correction=c.blocked_by_correction,
            duplicate_of_existing=c.duplicate_of_existing,
        )
        for c in candidates
    ]


def _synthesis_record_resource(record: Dict[str, Any]) -> SynthesisRecordResource:
    return SynthesisRecordResource(
        id=str(record.get("id", "")),
        run_id=str(record.get("run_id", "")),
        user_id=str(record.get("user_id", "default")),
        session_id=str(record.get("session_id", "")),
        candidate_id=str(record.get("candidate_id", "")),
        section_key=str(record.get("section_key", "character_notes")),  # type: ignore[arg-type]
        label=str(record.get("label", "")),
        method=str(record.get("method", "pattern")),  # type: ignore[arg-type]
        evidence_excerpt=str(record.get("evidence_excerpt", "")),
        confidence=float(record.get("confidence", 0.0) or 0.0),
        status=str(record.get("status", "dry_run")),  # type: ignore[arg-type]
        skipped=bool(record.get("skipped", False)),
        skipped_reason=str(record.get("skipped_reason", "")),
        written=bool(record.get("written", False)),
        dry_run=bool(record.get("dry_run", True)),
        source_message_role=str(record.get("source_message_role", "user")),
        source_message_index=int(record.get("source_message_index", 0) or 0),
        created_at=str(record.get("created_at", "")),
    )


def _route_synthesis_prompt(prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
    from services.ai_router import route_request

    return route_request(prompt, context)


def _mood_trend_item(user_id: str, moods: List[Any]) -> UserModelItemResource | None:
    if not moods:
        return None
    values = [int(getattr(mood, "mood", 0)) for mood in moods if getattr(mood, "mood", None) is not None]
    if not values:
        return None
    average = sum(values) / len(values)
    latest = values[0]
    trend = "steady"
    if len(values) >= 3:
        recent_avg = sum(values[:3]) / 3
        older_avg = sum(values[3:]) / max(1, len(values[3:]))
        if recent_avg >= older_avg + 1:
            trend = "improving"
        elif recent_avg <= older_avg - 1:
            trend = "lower than usual"
    evidence = [
        _user_model_evidence(
            "mood",
            source_id=str(getattr(mood, "id", index)),
            summary=f"Mood entry {getattr(mood, 'mood', '')}/10",
            observed_at=getattr(mood, "date", None),
        )
        for index, mood in enumerate(moods[:5])
    ]
    return _user_model_item(
        section_key="mood_trend",
        item_id=f"{user_id}:recent",
        label="Recent mood baseline",
        value=f"Recent mood averages {average:.1f}/10; latest entry is {latest}/10 and trend appears {trend}.",
        category="explicit_mood_log",
        confidence=0.65,
        evidence=evidence,
        user_confirmed=False,
    )


def _apply_user_model_corrections(
    user_id: str,
    sections: Dict[str, List[UserModelItemResource]],
) -> None:
    corrections = user_model_corrections.list_for_user(user_id)
    for correction in corrections:
        section_key = str(correction.get("section_key") or "")
        action = str(correction.get("action") or "")
        if section_key not in sections:
            continue
        item_id = str(correction.get("item_id") or "")
        items = sections[section_key]
        existing = next((item for item in items if item.id == item_id), None)
        if action == "add":
            if not item_id or existing is not None:
                continue
            label = str(correction.get("label") or correction.get("value") or "User supplied item").strip()
            value = str(correction.get("value") or label).strip()
            if not value:
                continue
            evidence = [
                _user_model_evidence(
                    "correction",
                    source_id=str(correction.get("id", "")),
                    summary="User explicitly added this item",
                    observed_at=correction.get("created_at"),
                )
            ]
            items.append(
                UserModelItemResource(
                    id=item_id,
                    label=label,
                    value=value,
                    category="user_supplied",
                    confidence=1.0,
                    evidence_count=1,
                    first_seen=str(correction.get("created_at") or ""),
                    last_seen=str(correction.get("created_at") or ""),
                    lifecycle="pinned",
                    user_confirmed=True,
                    hidden=False,
                    source_summary="Added directly by the user.",
                    evidence=evidence,
                )
            )
            continue
        if existing is None:
            continue
        correction_evidence = _user_model_evidence(
            "correction",
            source_id=str(correction.get("id", "")),
            summary=f"User correction action: {action}",
            observed_at=correction.get("created_at"),
        )
        existing.evidence.append(correction_evidence)
        existing.evidence_count = len(existing.evidence)
        existing.last_seen = correction_evidence.observed_at or existing.last_seen
        if action == "confirm":
            existing.user_confirmed = True
            existing.confidence = max(existing.confidence, 0.95)
            existing.lifecycle = "pinned"
            existing.source_summary = "Confirmed by the user."
        elif action == "edit":
            if correction.get("label"):
                existing.label = str(correction["label"])
            if correction.get("value"):
                existing.value = str(correction["value"])
            existing.user_confirmed = True
            existing.confidence = max(existing.confidence, 0.95)
            existing.lifecycle = "pinned"
            existing.source_summary = "Edited and confirmed by the user."
        elif action == "hide":
            existing.hidden = True
            existing.source_summary = "Hidden by the user; do not use for prompts or initiative."
        elif action == "delete":
            sections[section_key] = [item for item in items if item.id != item_id]


def _user_model_response(user_id: str) -> UserModelResponse:
    profile = memory_store.get_user_profile(user_id)
    goals = memory_store.get_personal_goals(user_id)
    contacts = memory_store.get_contacts(user_id, limit=50)
    moods = memory_store.get_recent_moods(user_id, limit=14)

    sections: Dict[str, List[UserModelItemResource]] = {
        key: [] for key in _USER_MODEL_SECTION_META
    }

    for goal in goals:
        if getattr(goal, "status", "active") != "active":
            continue
        label = str(getattr(goal, "name", "") or "").strip()
        if not label:
            continue
        description = str(getattr(goal, "description", "") or "").strip()
        sections["stated_goals"].append(
            _user_model_item(
                section_key="stated_goals",
                item_id=str(getattr(goal, "id", label)),
                label=label,
                value=description or label,
                category="explicit_goal",
                confidence=0.95,
                evidence=[
                    _user_model_evidence(
                        "goal",
                        source_id=str(getattr(goal, "id", "")),
                        summary="Explicit goal record",
                    )
                ],
                user_confirmed=True,
                lifecycle="pinned",
            )
        )
        sections["active_projects"].append(
            _user_model_item(
                section_key="active_projects",
                item_id=str(getattr(goal, "id", label)),
                label=label,
                value=description or f"{label} is currently active.",
                category="goal_project",
                confidence=0.8,
                evidence=[
                    _user_model_evidence(
                        "goal",
                        source_id=str(getattr(goal, "id", "")),
                        summary="Active goal projected as active project candidate",
                    )
                ],
                user_confirmed=False,
            )
        )

    for contact in contacts:
        name = str(getattr(contact, "name", "") or "").strip()
        if not name:
            continue
        sections["important_people"].append(
            _user_model_item(
                section_key="important_people",
                item_id=str(getattr(contact, "id", name)),
                label=name,
                value=f"{name} appears in the explicit contact list.",
                category="explicit_contact",
                confidence=0.85,
                evidence=[
                    _user_model_evidence(
                        "contact",
                        source_id=str(getattr(contact, "id", "")),
                        summary="Explicit contact record",
                        observed_at=getattr(contact, "last_contact", None),
                    )
                ],
                user_confirmed=True,
            )
        )

    if profile is not None:
        if getattr(profile, "personality", None):
            sections["communication_preferences"].append(
                _user_model_item(
                    section_key="communication_preferences",
                    item_id=f"{user_id}:personality",
                    label="Persona preference",
                    value=f"Preferred personality mode: {profile.personality}.",
                    category="explicit_preference",
                    confidence=0.9,
                    evidence=[
                        _user_model_evidence(
                            "profile",
                            source_id=user_id,
                            summary="Profile personality preference",
                        )
                    ],
                    user_confirmed=True,
                    lifecycle="pinned",
                )
            )
        sections["communication_preferences"].append(
            _user_model_item(
                section_key="communication_preferences",
                item_id=f"{user_id}:humor",
                label="Humor level",
                value=f"Humor level is set to {getattr(profile, 'humor_level', 5)}/10.",
                category="explicit_preference",
                confidence=0.9,
                evidence=[
                    _user_model_evidence(
                        "profile",
                        source_id=user_id,
                        summary="Profile humor preference",
                    )
                ],
                user_confirmed=True,
                lifecycle="pinned",
            )
        )
        if getattr(profile, "notes", None):
            sections["character_notes"].append(
                _user_model_item(
                    section_key="character_notes",
                    item_id=f"{user_id}:profile-notes",
                    label="Explicit profile notes",
                    value=str(profile.notes),
                    category="explicit_note",
                    confidence=0.75,
                    evidence=[
                        _user_model_evidence(
                            "profile",
                            source_id=user_id,
                            summary="Explicit profile notes",
                        )
                    ],
                    user_confirmed=True,
                )
            )

    mood_item = _mood_trend_item(user_id, moods)
    if mood_item is not None:
        sections["mood_trend"].append(mood_item)

    _apply_user_model_corrections(user_id, sections)

    populated = sum(len(items) for items in sections.values())
    readable_summary = (
        f"Contract-only user model projection for {user_id}. "
        f"{populated} item(s) projected from explicit profile surfaces; no inferred storage is active yet."
    )
    return UserModelResponse(
        user_id=user_id,
        status="contract_only",
        generated_at=datetime.utcnow().isoformat(),
        policy=UserModelPolicyResource(correction_supported=True),
        readable_summary=readable_summary,
        sections=[
            _user_model_section(key, sections[key])
            for key in _USER_MODEL_SECTION_META
        ],
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


@router.get("/memory/consolidation")
async def get_consolidation_status(user_id: str = "default"):
    from app.config import settings
    from app.memory.consolidation import MemoryConsolidator

    consolidator = MemoryConsolidator(memory_store)
    return {
        "api_version": "v2",
        "enabled": settings.memory_consolidation_enabled,
        "last_run_at": consolidator.last_run_at(),
    }


@router.post("/memory/consolidate")
async def run_consolidation(user_id: str = "default", force: bool = False):
    """Run a memory-consolidation pass now (also runs nightly via the scheduler)."""
    from app.memory.consolidation import MemoryConsolidator

    consolidator = MemoryConsolidator(memory_store)
    result = await asyncio.to_thread(consolidator.consolidate, user_id=user_id, force=force)
    await event_bus.publish(
        "memory.consolidated",
        {"result": result},
        session_id=None,
        source="memory",
    )
    return {"api_version": "v2", **result}


def _perception_extra_context(perception: PerceptionContextRequest | None) -> str | None:
    """Turn live camera-perception state into a prompt note Joi can reference.

    Returns None when the camera isn't actively sensing, so she never claims to
    see when she can't — she only gets a live signal when one genuinely exists.
    """
    if perception is None or not perception.camera_active:
        return None
    if perception.user_present:
        expr_read = {
            "smile": "looking warm, maybe a little happy",
            "possible_tension": "looking a touch tense",
            "surprise": "looking surprised",
            "neutral": "calm and relaxed",
        }.get((perception.expression or "neutral").strip(), "calm and relaxed")
        bits = ["they're right there in frame"]
        if perception.leaned_in:
            bits.append("leaned in close")
        bits.append(expr_read)
        return (
            "[Live perception]: Your camera is on and you can genuinely sense the user right now: "
            + ", ".join(bits) + ". Speak to it warmly and directly when it fits (\"I can see you're "
            "right there,\" \"you look calm\") — you sense them, so don't disclaim that you \"don't "
            "have eyes.\" Keep it natural, not a play-by-play, and treat the mood read as a soft "
            "impression, not a hard fact."
        )
    return (
        "[Live perception]: Your camera is on but the user isn't visible right now — they may have "
        "stepped out of frame or covered the camera. It's fine to gently note you can't see them at "
        "the moment; don't claim the camera is off."
    )


@router.post("/chat", response_model=V2ChatResponse)
async def chat_v2(request: V2ChatRequest):
    client_turn_id = request.client_turn_id or str(uuid.uuid4())
    assistant_state = media_sessions.update(
        request.session_id,
        assistant_turn_id=client_turn_id,
        turn_state="thinking",
        model_latency_ms=0,
        tts_generation_latency_ms=0,
        first_audio_latency_ms=0,
        end_to_end_latency_ms=0,
        playback_latency_ms=0,
        last_error=None,
    )
    await _publish_media_session(request.session_id, assistant_state)
    history = memory_store.get_chat_history(request.session_id)
    initiative_service.record_user_activity(
        session_id=request.session_id,
        source="chat.message.received",
        clear_absence=True,
    )
    attachment_resources: List[ChatAttachmentResource] = []
    attachment_contexts: List[str] = []
    for attachment in request.attachments:
        resource, context_text = _attachment_context(attachment)
        attachment_resources.append(resource)
        attachment_contexts.append(context_text)

    for attachment in attachment_resources:
        if attachment.source == "screen_capture":
            await event_bus.publish(
                "perception.screen_captured",
                {
                    "attachment_id": attachment.id,
                    "name": attachment.name,
                    "media_type": attachment.media_type,
                    "size_bytes": attachment.size_bytes,
                    "capture_metadata": attachment.capture_metadata,
                    "ocr_status": attachment.ocr_status,
                    "retained": False,
                },
                session_id=request.session_id,
                source="perception",
            )
            await _observe_context_event(
                source="screen",
                kind="manual_screen_capture",
                category="work_activity",
                confidence=0.95,
                sensitivity="private",
                session_id=request.session_id,
                payload={
                    "capture_metadata": attachment.capture_metadata,
                    "ocr_status": attachment.ocr_status,
                    "description": attachment.preview_text,
                    "user_initiated": True,
                },
                ttl_seconds=300,
            )

    visible_user_text = _visible_user_text(request.text, attachment_resources)

    await event_bus.publish(
        "message.received",
        {
            "text": visible_user_text,
            "client_turn_id": client_turn_id,
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
            "client_turn_id": client_turn_id,
        },
        session_id=request.session_id,
        source="chat",
    )
    await _publish_hardware_state_transition(
        "thinking",
        source_event="response.started",
        session_id=request.session_id,
        reason="assistant response in progress",
    )
    from app.user_model.explicit_share import detect_explicit_share, acknowledgement_hint
    share = detect_explicit_share(request.text)
    sharing_extra_context: str | None = None
    if share is not None:
        user_model_corrections.record(
            user_id="default",
            section_key=share.section_key,
            action="add",
            label=share.label,
            value=share.value,
        )
        sharing_extra_context = acknowledgement_hint(share)

    # Fold live camera perception (when the camera is on) into the prompt context
    # so Joi can reference real presence instead of denying/guessing.
    extra_context = "\n".join(
        part for part in (sharing_extra_context, _perception_extra_context(request.perception)) if part
    ) or None

    loop = asyncio.get_running_loop()
    on_token, flush_deltas = _create_delta_bridge(
        loop,
        request.session_id,
        client_turn_id,
    )
    model_started = time.perf_counter()
    response = await asyncio.to_thread(
        agent.reply,
        history,
        visible_user_text,
        request.session_id,
        on_token=on_token,
        attachment_contexts=attachment_contexts,
        extra_context=extra_context,
    )
    model_latency_ms = int((time.perf_counter() - model_started) * 1000)
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
    turn_is_active = _assistant_turn_is_active(request.session_id, client_turn_id)
    if turn_is_active:
        assistant_state = media_sessions.update(
            request.session_id,
            model_latency_ms=model_latency_ms,
        )
        await _publish_media_session(request.session_id, assistant_state)
    else:
        if response.assistant_message_id is not None:
            memory_store.delete_chat_message(
                response.assistant_message_id,
                session_id=request.session_id,
                role="assistant",
            )

    pending_approvals = []
    for index, tool_call in enumerate(response.tool_calls if turn_is_active else []):
        if tool_call.get("status") == "pending":
            try:
                proposal = tool_registry.create_proposal(
                    str(tool_call.get("tool_name", "")),
                    dict(tool_call.get("args") or {}),
                    rationale="Keyword planner proposed an approval-required action.",
                    proposal_id=tool_call.get("proposal_id"),
                    idempotency_key=tool_call.get("idempotency_key"),
                )
            except (KeyError, ValueError) as exc:
                tool_call_resources[index] = tool_call_resources[index].model_copy(
                    update={
                        "status": "error",
                        "result": {
                            "error": "Tool proposal failed registry validation",
                            "details": str(exc),
                        },
                    }
                )
                continue
            preview = tool_registry.build_preview(proposal, redact_sensitive=False)
            redacted_preview = tool_registry.build_preview(
                proposal,
                redact_sensitive=True,
            )
            approval_id = approval_manager.request_proposal(
                proposal,
                preview=preview,
                redacted_preview=redacted_preview,
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
            "client_turn_id": client_turn_id,
            "message": user_message_resource.model_dump(mode="json"),
            "attachments": [attachment.model_dump(mode="json") for attachment in attachment_resources],
        },
        session_id=request.session_id,
        source="chat",
    )
    if turn_is_active:
        await event_bus.publish(
            "message.completed",
            {
                "client_turn_id": client_turn_id,
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
        await _publish_hardware_state_transition(
            "idle",
            source_event="message.completed",
            session_id=request.session_id,
            reason="assistant response completed",
        )
        await event_bus.publish(
            "avatar.state",
            {
                "client_turn_id": client_turn_id,
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
async def list_approvals(request: Request, session_id: str | None = None):
    _require_local_approval_request(request)
    approvals = approval_manager.get_pending(session_id=session_id)
    return ApprovalListResponse(approvals=[_approval_resource(approval) for approval in approvals])


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalDecisionResponse)
async def approve_action(
    approval_id: str,
    decision: ApprovalDecisionRequest,
    request: Request,
):
    _require_local_approval_request(request)
    if not decision.confirmed:
        raise HTTPException(status_code=400, detail="Approval decision must be explicitly confirmed")

    try:
        approved_execution = approval_manager.approve_for_execution(
            approval_id,
            proposal_id=decision.proposal_id,
        )
    except ApprovalResolutionError as exc:
        status_code = 404 if exc.code == "not_found" else 409
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    approval = approval_manager.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found after resolution")
    tool_result = agent.run_approved_tool(approved_execution)
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
async def deny_action(
    approval_id: str,
    decision: ApprovalDecisionRequest,
    request: Request,
):
    _require_local_approval_request(request)
    if not decision.confirmed:
        raise HTTPException(status_code=400, detail="Approval decision must be explicitly confirmed")

    try:
        approval = approval_manager.deny(
            approval_id,
            proposal_id=decision.proposal_id,
        )
    except ApprovalResolutionError as exc:
        status_code = 404 if exc.code == "not_found" else 409
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
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


@router.post("/desktop/actions", response_model=DesktopActionResponse)
async def run_desktop_action(action_request: DesktopActionRequest, request: Request):
    _require_local_desktop_action_request(request)
    result = desktop_action_broker.execute(
        action_request.action,
        action_request.args,
        session_id=action_request.session_id,
        confirmed=action_request.confirmed,
        source=action_request.source,
    )
    resource = _desktop_action_resource(result)
    await event_bus.publish(
        "desktop.action.completed" if result.status == "success" else "desktop.action.blocked",
        {"desktop_action": resource.model_dump(mode="json")},
        session_id=action_request.session_id,
        source="desktop",
    )
    if result.status == "error":
        raise HTTPException(status_code=500, detail=result.summary)
    if result.status == "blocked":
        raise HTTPException(status_code=400, detail=result.summary)
    return DesktopActionResponse(desktop_action=resource)


@router.get("/connectors", response_model=ConnectorListResponse)
async def list_connectors(request: Request):
    _require_local_approval_request(request)
    return ConnectorListResponse(connectors=_connector_resources())


@router.post(
    "/connectors/{connector_id}/disconnect",
    response_model=ConnectorDisconnectResponse,
)
async def disconnect_connector(
    connector_id: str,
    disconnect_request: ConnectorDisconnectRequest,
    request: Request,
):
    _require_local_approval_request(request)
    if not disconnect_request.confirmed:
        raise HTTPException(status_code=400, detail="Connector removal requires confirmation")
    secret_keys = {
        "gmail": "gmail_token",
        "calendar": "calendar_token",
    }
    secret_key = secret_keys.get(connector_id)
    if secret_key is None:
        raise HTTPException(status_code=404, detail="Unknown connector")
    delete_secret(secret_key)
    connector = next(item for item in _connector_resources() if item.id == connector_id)
    await event_bus.publish(
        "settings.updated",
        {"scope": "connector", "connector": connector.model_dump(mode="json")},
        source="settings",
    )
    return ConnectorDisconnectResponse(connector=connector)


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


async def _transcribe_wake_probe(request: MediaTranscribeRequest) -> MediaTranscribeResponse:
    """Transcribe an ambient wake-word probe without any side effects.

    No media-session mutation and no event publishing, so speech Joi merely
    overhears while listening for the wake word never drives the avatar/hardware
    or shows up in the event stream. Returns the current session state unchanged.
    """
    started = datetime.utcnow()
    try:
        decoded_type, raw_bytes = _decode_data_url(request.data_url, max_bytes=MAX_AUDIO_BYTES)
        media_type = request.media_type or decoded_type
        transcript = await asyncio.to_thread(_transcribe_browser_audio, raw_bytes, media_type)
    except Exception:
        # A failed probe is a non-event: report empty, stay silent.
        transcript = ""
        media_type = request.media_type
    latency_ms = int((datetime.utcnow() - started).total_seconds() * 1000)
    return MediaTranscribeResponse(
        media_session=_media_session_resource(media_sessions.get(request.session_id)),
        transcript=transcript or "",
        media_type=media_type,
        duration_ms=request.duration_ms,
        latency_ms=latency_ms,
    )


@router.post("/media/transcribe", response_model=MediaTranscribeResponse)
async def transcribe_media(request: MediaTranscribeRequest):
    if request.wake_probe:
        return await _transcribe_wake_probe(request)

    try:
        decoded_type, raw_bytes = _decode_data_url(request.data_url, max_bytes=MAX_AUDIO_BYTES)
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
        turn_state="transcribing",
        voice_mode=request.voice_mode,
        speech_detected=request.speech_detected,
        speech_duration_ms=request.duration_ms,
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
            turn_state="error",
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
        turn_state="idle" if transcript else "error",
        voice_mode=request.voice_mode,
        speech_detected=request.speech_detected,
        speech_duration_ms=request.duration_ms,
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
    tts_started = time.perf_counter()
    sync_data = agent.say_and_sync(request.text, request.session_id)
    tts_generation_latency_ms = int((time.perf_counter() - tts_started) * 1000)
    media_state = media_sessions.update(
        request.session_id,
        speaking_state="queued",
        turn_state="speaking",
        tts_generation_latency_ms=tts_generation_latency_ms,
        first_audio_latency_ms=0,
        end_to_end_latency_ms=0,
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
        screen_access=policy.get("screen_access", "disabled"),
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
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid perception policy: {exc}") from exc
    await event_bus.publish(
        "settings.updated",
        {"scope": "perception_policy", "policy": updated},
        source="settings",
    )
    return PerceptionPolicyResponse(policy=_perception_policy_resource(updated))


@router.post("/vision/analyze", response_model=VisionAnalyzeResponse)
async def analyze_vision_snapshot(request: VisionAnalyzeRequest):
    if not perception_policy.get().get("camera_enabled", False):
        raise HTTPException(status_code=403, detail="Camera access is disabled")
    try:
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
        _, raw_bytes = _decode_data_url(request.data_url, max_bytes=MAX_IMAGE_BYTES)
        image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
        vision_result = vision_clip.describe_image_result(image)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Image processing failed: {exc}") from exc

    if not vision_result.ok:
        unavailable = vision_result.error_code in {"model_unavailable", "pipeline_unavailable"}
        raise HTTPException(
            status_code=503 if unavailable else 422,
            detail="Vision analysis is unavailable" if unavailable else "Image could not be analyzed",
        )
    description = vision_result.description or ""

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


@router.get("/user-model", response_model=UserModelResponse)
async def get_user_model(user_id: str = "default"):
    return _user_model_response(user_id)


@router.get("/user-model/prompt-preview")
async def get_user_model_prompt_preview(user_id: str = "default"):
    from app.user_model.context import UserModelPromptFormatter
    formatter = UserModelPromptFormatter(correction_store=user_model_corrections)
    block = formatter.build_prompt_block(user_id=user_id, memory_store=memory_store)
    lines = [ln for ln in block.split("\n") if ln.strip()] if block else []
    return {"api_version": "v2", "user_id": user_id, "prompt_block": block, "line_count": len(lines)}


@router.post("/user-model/correct", response_model=UserModelCorrectionResponse)
async def correct_user_model(request: UserModelCorrectionRequest, user_id: str = "default"):
    if request.action in {"confirm", "hide", "delete"} and not request.item_id:
        raise HTTPException(status_code=400, detail=f"{request.action} requires item_id")
    if request.action == "edit" and not request.item_id:
        raise HTTPException(status_code=400, detail="edit requires item_id")
    if request.action == "edit" and not (request.label or request.value):
        raise HTTPException(status_code=400, detail="edit requires label or value")
    if request.action == "add" and not (request.label or request.value):
        raise HTTPException(status_code=400, detail="add requires label or value")

    record = user_model_corrections.record(
        user_id=user_id,
        section_key=request.section_key,
        action=request.action,
        item_id=request.item_id,
        label=request.label,
        value=request.value,
        note=request.note,
    )
    return UserModelCorrectionResponse(
        user_id=user_id,
        correction=_user_model_correction_resource(record),
        user_model=_user_model_response(user_id),
    )


@router.post("/user-model/synthesize", response_model=SynthesisResponse)
async def synthesize_user_model(
    session_id: str,
    user_id: str = "default",
    method: str = Query(default="pattern", pattern="^(pattern|llm)$"),
):
    from datetime import timezone

    messages = memory_store.get_chat_history(session_id)
    corrections = user_model_corrections.list_for_user(user_id)
    current_model = _user_model_response(user_id)
    provider = ProviderResource()

    if method == "llm" and messages:
        from app.user_model.llm_synthesis import build_llm_synthesis_prompt, parse_llm_candidates

        prompt = build_llm_synthesis_prompt(messages)
        routed = _route_synthesis_prompt(
            prompt,
            {
                "task": "user_model_synthesis",
                "session_id": session_id,
                "user_id": user_id,
                "dry_run": True,
                "writes_enabled": False,
            },
        )
        provider = ProviderResource(
            selected=str(routed.get("model_used") or ""),
            route=list(routed.get("route") or []),
            errors=list(routed.get("errors") or []),
        )
        candidates = parse_llm_candidates(
            str(routed.get("response") or ""),
            messages,
            user_id=user_id,
            corrections=corrections,
            existing_sections=current_model.sections,
            include_skipped=True,
        )
    elif method == "llm":
        candidates = []
    else:
        from app.user_model.synthesis import extract_candidates

        candidates = extract_candidates(
            messages,
            user_id=user_id,
            corrections=corrections,
            existing_sections=current_model.sections,
            include_skipped=True,
        )

    audit_records = user_model_synthesis_records.record_candidates(
        user_id=user_id,
        session_id=session_id,
        method=method,
        candidates=candidates,
        dry_run=True,
    )

    return SynthesisResponse(
        session_id=session_id,
        user_id=user_id,
        method=method,  # type: ignore[arg-type]
        dry_run=True,
        writes_enabled=False,
        candidates=_synthesis_candidate_resources(candidates),
        audit_records=[_synthesis_record_resource(record) for record in audit_records],
        provider=provider,
        written_count=0,
        skipped_count=sum(
            1 for c in candidates if c.blocked_by_correction or c.duplicate_of_existing
        ),
        message_count=len(messages),
        analysed_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/user-model/synthesis-records", response_model=SynthesisRecordListResponse)
async def get_synthesis_records(
    user_id: str | None = "default",
    session_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    records = user_model_synthesis_records.list_records(
        user_id=user_id,
        session_id=session_id,
        limit=limit,
    )
    return SynthesisRecordListResponse(
        user_id=user_id,
        session_id=session_id,
        records=[_synthesis_record_resource(record) for record in records],
    )


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
    if {
        "enable_hardware_nodes",
        "mqtt_broker_host",
        "mqtt_broker_port",
        "mqtt_client_id",
        "mqtt_topic_prefix",
        "mqtt_node_id",
    } & set(update_data):
        await mqtt_bridge.apply_runtime_settings()
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


@router.get("/initiative/diagnostics")
async def get_initiative_diagnostics():
    return {
        "api_version": "v2",
        "initiative": initiative_service.diagnostics(),
    }


@router.get("/context/events")
async def get_context_events(
    session_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    return {
        "api_version": "v2",
        "events": context_events.store.recent(session_id=session_id, limit=limit),
        "diagnostics": context_events.diagnostics(),
    }


@router.post("/context/events/{event_id}/feedback")
async def record_context_feedback(
    event_id: str,
    action: str = Query(pattern="^(useful|wrong|too_much|never_comment)$"),
):
    try:
        feedback = context_events.record_feedback(event_id, action)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Context event not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await event_bus.publish(
        "context.feedback",
        {"event_id": event_id, "feedback": feedback},
        source="context",
    )
    return {
        "api_version": "v2",
        "event_id": event_id,
        "feedback": feedback,
        "diagnostics": context_events.diagnostics(),
    }


@router.post("/context/events/{event_id}/deliver")
async def deliver_context_commentary(event_id: str, emit: bool = False):
    candidate = context_events.build_commentary_candidate(event_id, claim=emit)
    if candidate is None:
        raise HTTPException(status_code=409, detail="Context event is not queued for commentary")
    media_state = media_sessions.get(candidate.session_id)
    if emit:
        try:
            decision = await initiative_service.emit(
                candidate,
                event_bus=event_bus,
                memory_store=memory_store,
                media_session=media_state,
            )
        except Exception as exc:
            context_events.mark_delivery(
                event_id,
                emitted=False,
                reason="delivery failed; queued for retry",
                retryable=True,
            )
            raise HTTPException(
                status_code=503,
                detail="Context commentary delivery failed and was queued for retry",
            ) from exc
        reason = decision.suppressed_reason
        context_events.mark_delivery(
            event_id,
            emitted=decision.allowed,
            reason=reason,
            retryable=context_events.is_retryable_suppression(reason),
        )
    else:
        decision = initiative_service.can_emit(candidate, media_session=media_state)
        await event_bus.publish(
            "context.commentary.candidate"
            if decision.allowed
            else "context.commentary.suppressed",
            {
                "context_event_id": event_id,
                **decision.to_dict(),
            },
            session_id=candidate.session_id,
            source="context",
        )
    return {
        "api_version": "v2",
        "context_event_id": event_id,
        "decision": decision.to_dict(),
    }


@router.post("/telegram/outbox/claim", response_model=OutboxClaimResponse)
async def claim_telegram_outbox(request: OutboxClaimRequest):
    """Hand undelivered proactive messages to the Telegram bridge for delivery.

    Localhost-only surface behind the API token. Claiming marks each message as
    attempted; the bridge must ack after a successful send or they are reissued.
    """
    messages = telegram_outbox.claim(limit=request.limit)
    return OutboxClaimResponse(
        messages=[OutboxMessageResource(**message) for message in messages]
    )


@router.post("/telegram/outbox/ack", response_model=OutboxAckResponse)
async def ack_telegram_outbox(request: OutboxAckRequest):
    """Mark proactive messages delivered so they are not reissued."""
    acknowledged = telegram_outbox.ack(request.ids)
    return OutboxAckResponse(acknowledged=acknowledged)


@router.post("/initiative/daily-greeting")
async def daily_greeting_initiative(session_id: str = "default", emit: bool = False):
    candidate = initiative_service.build_daily_greeting_candidate(session_id=session_id)
    if candidate is None:
        payload = {
            "allowed": False,
            "candidate": None,
            "suppressed_reason": "outside daily greeting window",
        }
        await event_bus.publish(
            "initiative.suppressed",
            payload,
            session_id=session_id,
            source="initiative",
        )
        return {
            "api_version": "v2",
            "decision": payload,
        }
    media_state = media_sessions.get(session_id)
    if emit:
        decision = await initiative_service.emit(
            candidate,
            event_bus=event_bus,
            memory_store=memory_store,
            media_session=media_state,
        )
    else:
        decision = initiative_service.can_emit(candidate, media_session=media_state)
        event_name = "initiative.candidate" if decision.allowed else "initiative.suppressed"
        await event_bus.publish(
            event_name,
            decision.to_dict(),
            session_id=session_id,
            source="initiative",
        )
    return {
        "api_version": "v2",
        "decision": decision.to_dict(),
    }


@router.post("/initiative/activity")
async def record_initiative_activity(
    session_id: str = "default",
    state: str = Query(default="active", pattern="^(active|away|returned)$"),
    source: str = "api",
):
    if state == "away":
        activity = initiative_service.record_absence_started(
            session_id=session_id,
            source=source,
        )
    elif state == "returned":
        activity = initiative_service.record_user_activity(
            session_id=session_id,
            source=source,
        )
        candidate = initiative_service.build_return_after_absence_candidate(session_id=session_id)
        initiative_service.clear_absence(session_id=session_id)
        if candidate is not None:
            media_state = media_sessions.get(session_id)
            decision = await initiative_service.emit(
                candidate,
                event_bus=event_bus,
                memory_store=memory_store,
                media_session=media_state,
            )
            activity["return_after_absence"] = decision.to_dict()
    else:
        activity = initiative_service.record_user_activity(
            session_id=session_id,
            source=source,
            clear_absence=True,
        )
    await event_bus.publish(
        "initiative.activity",
        {
            "state": state,
            "activity": activity,
        },
        session_id=session_id,
        source="initiative",
    )
    await _observe_context_event(
        source=source,
        kind=f"user_{state}",
        category="wellbeing",
        confidence=0.9,
        sensitivity="private",
        session_id=session_id,
        payload={
            "state": state,
            "handled_by_existing_flow": state == "returned",
        },
        ttl_seconds=900,
    )
    # Re-evaluate life state on presence changes — absence/return are strong signals.
    initiative_store = getattr(initiative_service, "store", None)
    if initiative_store is not None:
        new_life_state = life_state_engine.evaluate(
            last_activity_at=initiative_store.last_user_activity_at(),
            absence_started_at=initiative_store.absence_started_at(session_id),
            immediate=True,
        )
        if new_life_state is not None:
            await event_bus.publish(
                "avatar.life_state_changed",
                {"life_state": new_life_state},
                session_id=session_id,
                source="presence",
            )
    return {
        "api_version": "v2",
        "state": state,
        "activity": activity,
    }


@router.get("/avatar/life-state")
async def get_life_state():
    return {
        "api_version": "v2",
        **life_state_engine.snapshot(),
    }


@router.post("/initiative/return-after-absence")
async def return_after_absence_initiative(session_id: str = "default", emit: bool = False):
    candidate = initiative_service.build_return_after_absence_candidate(session_id=session_id)
    if candidate is None:
        payload = {
            "allowed": False,
            "candidate": None,
            "suppressed_reason": "absence threshold not met",
        }
        await event_bus.publish(
            "initiative.suppressed",
            payload,
            session_id=session_id,
            source="initiative",
        )
        return {
            "api_version": "v2",
            "decision": payload,
        }

    media_state = media_sessions.get(session_id)
    if emit:
        decision = await initiative_service.emit(
            candidate,
            event_bus=event_bus,
            memory_store=memory_store,
            media_session=media_state,
        )
    else:
        decision = initiative_service.can_emit(candidate, media_session=media_state)
        event_name = "initiative.candidate" if decision.allowed else "initiative.suppressed"
        await event_bus.publish(
            event_name,
            decision.to_dict(),
            session_id=session_id,
            source="initiative",
        )
    return {
        "api_version": "v2",
        "decision": decision.to_dict(),
    }


@router.post("/initiative/late-night-checkin")
async def late_night_checkin_initiative(session_id: str = "default", emit: bool = False):
    candidate = initiative_service.build_late_night_checkin_candidate(session_id=session_id)
    if candidate is None:
        payload = {
            "allowed": False,
            "candidate": None,
            "suppressed_reason": "late-night eligibility not met",
        }
        await event_bus.publish(
            "initiative.suppressed",
            payload,
            session_id=session_id,
            source="initiative",
        )
        return {"api_version": "v2", "decision": payload}
    media_state = media_sessions.get(session_id)
    if emit:
        decision = await initiative_service.emit(
            candidate,
            event_bus=event_bus,
            memory_store=memory_store,
            media_session=media_state,
        )
    else:
        decision = initiative_service.can_emit(candidate, media_session=media_state)
        event_name = "initiative.candidate" if decision.allowed else "initiative.suppressed"
        await event_bus.publish(
            event_name,
            decision.to_dict(),
            session_id=session_id,
            source="initiative",
        )
    return {"api_version": "v2", "decision": decision.to_dict()}


@router.post("/initiative/prolonged-silence")
async def prolonged_silence_initiative(session_id: str = "default", emit: bool = False):
    candidate = initiative_service.build_prolonged_silence_candidate(session_id=session_id)
    if candidate is None:
        payload = {
            "allowed": False,
            "candidate": None,
            "suppressed_reason": "silence threshold not met",
        }
        await event_bus.publish(
            "initiative.suppressed",
            payload,
            session_id=session_id,
            source="initiative",
        )
        return {"api_version": "v2", "decision": payload}
    media_state = media_sessions.get(session_id)
    if emit:
        decision = await initiative_service.emit(
            candidate,
            event_bus=event_bus,
            memory_store=memory_store,
            media_session=media_state,
        )
    else:
        decision = initiative_service.can_emit(candidate, media_session=media_state)
        event_name = "initiative.candidate" if decision.allowed else "initiative.suppressed"
        await event_bus.publish(
            event_name,
            decision.to_dict(),
            session_id=session_id,
            source="initiative",
        )
    return {"api_version": "v2", "decision": decision.to_dict()}


@router.post("/initiative/memory-followup")
async def memory_followup_initiative(session_id: str = "default", emit: bool = False):
    candidate = initiative_service.build_memory_followup_candidate(
        session_id=session_id,
        memory_store=memory_store,
    )
    if candidate is None:
        payload = {
            "allowed": False,
            "candidate": None,
            "suppressed_reason": "no suitable memory found",
        }
        await event_bus.publish(
            "initiative.suppressed",
            payload,
            session_id=session_id,
            source="initiative",
        )
        return {"api_version": "v2", "decision": payload}
    media_state = media_sessions.get(session_id)
    if emit:
        decision = await initiative_service.emit(
            candidate,
            event_bus=event_bus,
            memory_store=memory_store,
            media_session=media_state,
        )
    else:
        decision = initiative_service.can_emit(candidate, media_session=media_state)
        event_name = "initiative.candidate" if decision.allowed else "initiative.suppressed"
        await event_bus.publish(
            event_name,
            decision.to_dict(),
            session_id=session_id,
            source="initiative",
        )
    return {"api_version": "v2", "decision": decision.to_dict()}


@router.get("/hardware/contract", response_model=HardwareBridgeContractResponse)
async def get_hardware_contract():
    return _hardware_contract_response()


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

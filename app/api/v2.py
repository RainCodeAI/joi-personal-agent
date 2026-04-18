from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any, Dict, Iterable, List

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.api.realtime import format_sse_event
from app.api.state import agent, approval_manager, event_bus, memory_store, runtime_settings
from app.api.v2_models import (
    ApprovalDecisionResponse,
    ApprovalListResponse,
    ApprovalResource,
    AvatarCueResource,
    AvatarSyncRequest,
    AvatarSyncResponse,
    EmotionResource,
    MessageListResponse,
    MessageResource,
    ProviderResource,
    RealtimeEventEnvelope,
    RealtimeEventsResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionListResponse,
    SessionResource,
    SettingsPatchRequest,
    SettingsResponse,
    SettingsResource,
    ToolCallResource,
    V2ChatRequest,
    V2ChatResponse,
)
from app.orchestrator.craving_engine import CravingEngine
from app.orchestrator.security.approval import ApprovalStatus, PendingApproval


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


@router.post("/chat", response_model=V2ChatResponse)
async def chat_v2(request: V2ChatRequest):
    history = memory_store.get_chat_history(request.session_id)
    await event_bus.publish(
        "message.received",
        {
            "text": request.text,
            "history_count": len(history),
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
    response = agent.reply(history, request.text, request.session_id)
    session = memory_store.get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=500, detail="Session record missing after chat")

    messages = memory_store.get_chat_history(request.session_id)
    user_message = next((msg for msg in reversed(messages) if msg.id == response.user_message_id), None)
    assistant_message = next((msg for msg in reversed(messages) if msg.id == response.assistant_message_id), None)
    if user_message is None or assistant_message is None:
        raise HTTPException(status_code=500, detail="Chat message records missing after reply")

    user_message_resource = _message_resource(user_message)
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
        },
        session_id=request.session_id,
        source="chat",
    )
    await event_bus.publish(
        "message.completed",
        {
            "message": assistant_message_resource.model_dump(mode="json"),
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


@router.post("/avatar/sync", response_model=AvatarSyncResponse)
async def avatar_sync(request: AvatarSyncRequest):
    sync_data = agent.say_and_sync(request.text, request.session_id)
    response = AvatarSyncResponse(
        session_id=request.session_id,
        audio_url=sync_data.get("audio_url", ""),
        phoneme_timeline=sync_data.get("phoneme_timeline", []),
        sentiment=sync_data.get("sentiment", "neutral"),
    )
    await event_bus.publish(
        "tts.ready",
        {
            "audio_url": response.audio_url,
            "phoneme_timeline": response.phoneme_timeline,
            "sentiment": response.sentiment,
        },
        session_id=request.session_id,
        source="avatar",
    )
    return response


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

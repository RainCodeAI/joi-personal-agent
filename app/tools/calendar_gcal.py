from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from app.config import settings
from app.vault import get_secret, store_secret
import json
from typing import List, Dict, Any
from datetime import datetime, timedelta

READ_SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
WRITE_SCOPES = ['https://www.googleapis.com/auth/calendar.events']
SCOPES = READ_SCOPES + WRITE_SCOPES

def is_authenticated() -> bool:
    """Check if valid credentials exist."""
    try:
        get_secret("calendar_token")
        return True
    except KeyError:
        return False


def get_credentials() -> Credentials:
    try:
        token_data = get_secret("calendar_token")
        creds = Credentials.from_authorized_user_info(json.loads(token_data))
    except KeyError:
        raise Exception("Calendar not authenticated. Please go to /oauth/start")
    
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        store_secret("calendar_token", creds.to_json())
    return creds

def upcoming_events(days: int = 7) -> List[Dict[str, Any]]:
    creds = get_credentials()
    service = build('calendar', 'v3', credentials=creds)
    now = datetime.utcnow()
    time_min = now.isoformat() + 'Z'
    time_max = (now + timedelta(days=days)).isoformat() + 'Z'
    
    events_result = service.events().list(
        calendarId='primary', timeMin=time_min, timeMax=time_max,
        singleEvents=True, orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    return events

def create_event(
    summary: str,
    start_time: str,
    duration_minutes: int = 60,
    *,
    idempotency_key: str | None = None,
) -> Dict[str, Any]:
    """Create a calendar event. start_time must be ISO format."""
    try:
        dt_start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("start_time must be an ISO-8601 datetime") from exc
    if duration_minutes <= 0 or duration_minutes > 1440:
        raise ValueError("duration_minutes must be between 1 and 1440")

    creds = get_credentials()
    service = build('calendar', 'v3', credentials=creds)

    if idempotency_key:
        existing_result = service.events().list(
            calendarId="primary",
            privateExtendedProperty=f"joi_idempotency_key={idempotency_key}",
            maxResults=1,
            singleEvents=True,
        ).execute()
        existing = existing_result.get("items", [])
        if existing:
            return {**existing[0], "idempotent_replay": True}
    
    dt_end = dt_start + timedelta(minutes=duration_minutes)
    
    event = {
        'summary': summary,
        'start': {
            'dateTime': dt_start.isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': dt_end.isoformat(),
            'timeZone': 'UTC',
        },
    }
    if idempotency_key:
        event["extendedProperties"] = {
            "private": {"joi_idempotency_key": idempotency_key}
        }

    event = service.events().insert(calendarId='primary', body=event).execute()
    return event


def verify_created_event(event_id: str, idempotency_key: str) -> Dict[str, Any]:
    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)
    event = service.events().get(calendarId="primary", eventId=event_id).execute()
    actual_key = (
        event.get("extendedProperties", {})
        .get("private", {})
        .get("joi_idempotency_key")
    )
    return {
        "verified": bool(event.get("id")) and actual_key == idempotency_key,
        "provider_id": event.get("id"),
        "actual_idempotency_key": actual_key,
    }

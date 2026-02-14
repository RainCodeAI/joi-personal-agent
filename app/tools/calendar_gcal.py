from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from app.config import settings
from app.vault import get_secret, store_secret
import json
from typing import List, Dict, Any
from datetime import datetime, timedelta

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def get_credentials() -> Credentials:
    try:
        token_data = get_secret("calendar_token")
        creds = Credentials.from_authorized_user_info(json.loads(token_data), SCOPES)
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

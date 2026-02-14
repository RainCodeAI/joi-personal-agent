import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import Flow
from app.config import settings
from app.vault import get_secret, store_secret
import httpx
from typing import List, Dict, Any
from app.tools.types import ToolResult

MAX_RESULTS = 20

def is_authenticated() -> bool:
    """Check if valid credentials exist."""
    try:
        get_secret("gmail_token")
        return True
    except KeyError:
        return False


def get_credentials() -> Credentials:
    try:
        token_data = get_secret("gmail_token")
        creds = Credentials.from_authorized_user_info(json.loads(token_data), SCOPES)
    except KeyError:
        raise Exception("Gmail not authenticated. Please go to /oauth/start")
    
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        store_secret("gmail_token", creds.to_json())
    return creds

def list_threads(max_results: int = 20) -> List[Dict[str, Any]]:
    creds = get_credentials()
    service = build('gmail', 'v1', credentials=creds)
    results = service.users().threads().list(userId='me', maxResults=max_results).execute()
    threads = results.get('threads', [])
    return threads

def summarize_threads(threads: List[Dict[str, Any]]) -> str:
    # Simple summary: count and list subjects
    if not threads:
        return "No threads found."
    
    summaries = []
    creds = get_credentials()
    service = build('gmail', 'v1', credentials=creds)
    for thread in threads[:5]:  # Limit to 5 for summary
        tdata = service.users().threads().get(userId='me', id=thread['id']).execute()
        subject = ""
        for msg in tdata['messages']:
            headers = msg['payload']['headers']
            for h in headers:
                if h['name'] == 'Subject':
                    subject = h['value']
                    break
            if subject:
                break
        summaries.append(f"Thread: {subject}")
    
    return "\n".join(summaries)

def send_message(to: str, subject: str, body: str) -> Dict[str, Any]:
    """Send an email using Gmail API."""
    from email.mime.text import MIMEText
    import base64

    creds = get_credentials()
    service = build('gmail', 'v1', credentials=creds)

    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {'raw': raw}
    
    sent_msg = service.users().messages().send(userId='me', body=body).execute()
    return sent_msg

def initiate_oauth() -> str:
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uris": [settings.oauth_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES
    )
    flow.redirect_uri = settings.oauth_redirect_uri
    auth_url, _ = flow.authorization_url(prompt='consent')
    return auth_url

def complete_oauth(code: str):
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uris": [settings.oauth_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES
    )
    flow.redirect_uri = settings.oauth_redirect_uri
    flow.fetch_token(code=code)
    creds = flow.credentials
    store_secret("gmail_token", creds.to_json())

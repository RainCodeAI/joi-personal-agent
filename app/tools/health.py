import os
from datetime import datetime, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from app.memory.store import MemoryStore
from app.config import settings

SCOPES = ['https://www.googleapis.com/auth/fitness.activity.read', 'https://www.googleapis.com/auth/fitness.body.read']

def get_fit_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('fitness', 'v1', credentials=creds)

def ingest_health_data(store: MemoryStore, user_id: str = "default"):
    service = get_fit_service()
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    # Steps
    steps_req = service.users().dataset().aggregate(
        userId='me',
        body={
            'aggregateBy': [{'dataTypeName': 'com.google.step_count.delta'}],
            'startTimeMillis': int(datetime.combine(datetime.strptime(yesterday, '%Y-%m-%d'), datetime.min.time()).timestamp() * 1000),
            'endTimeMillis': int(datetime.combine(datetime.strptime(yesterday, '%Y-%m-%d'), datetime.max.time()).timestamp() * 1000),
        }
    ).execute()
    steps = next((point['value'][0]['intVal'] for point in steps_req['bucket'][0]['dataset'][0]['point']), 0)
    store.add_memory("health_steps", f"Steps yesterday: {steps}", ["health", user_id])
    
    # Sleep (total minutes)
    sleep_req = service.users().dataset().aggregate(
        userId='me',
        body={
            'aggregateBy': [{'dataTypeName': 'com.google.sleep.segment'}],
            'startTimeMillis': int(datetime.combine(datetime.strptime(yesterday, '%Y-%m-%d'), datetime.min.time()).timestamp() * 1000),
            'endTimeMillis': int(datetime.combine(datetime.strptime(yesterday, '%Y-%m-%d'), datetime.max.time()).timestamp() * 1000),
            'bucketByTime': {'durationMillis': 86400000},  # 1 day
        }
    ).execute()
    sleep_mins = sum(point['value'][0]['intVal'] for point in sleep_req['bucket'][0]['dataset'][0]['point'])
    store.add_memory("health_sleep", f"Sleep yesterday: {sleep_mins/60:.1f} hours", ["health", user_id])
    
    # Avg HR
    hr_req = service.users().dataset().aggregate(
        userId='me',
        body={
            'aggregateBy': [{'dataTypeName': 'com.google.heart_rate.bpm'}],
            'startTimeMillis': int(datetime.combine(datetime.strptime(yesterday, '%Y-%m-%d'), datetime.min.time()).timestamp() * 1000),
            'endTimeMillis': int(datetime.combine(datetime.strptime(yesterday, '%Y-%m-%d'), datetime.max.time()).timestamp() * 1000),
        }
    ).execute()
    avg_hr = next((point['value'][0]['fpVal'] for point in hr_req['bucket'][0]['dataset'][0]['point']), 0)
    store.add_memory("health_hr", f"Avg HR yesterday: {avg_hr:.0f} bpm", ["health", user_id])
    
    # Nudge if low sleep/HR variance (tie to mood)
    if sleep_mins < 360:  # <6hrs
        store.add_memory("nudge", "Low sleep detected—try a 5-min meditation?", ["alert", user_id])
    print(f"Ingested health data for {yesterday}")

# Call in agent.py or scheduler.py: ingest_health_data(MemoryStore(), session_id)
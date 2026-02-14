from app.tools import calendar_gcal, email_gmail
from app.orchestrator.agent import Agent
from pathlib import Path
import json
from datetime import datetime

def morning_brief():
    # Mock weather
    weather = "Sunny, 72°F"
    
    # Calendar today
    events = calendar_gcal.upcoming_events(days=1)
    calendar_summary = "\n".join([f"{e['summary']} at {e['start']['dateTime']}" for e in events[:5]])
    
    # Inbox waiting
    threads = email_gmail.list_threads(max_results=10)
    inbox_summary = email_gmail.summarize_threads(threads)
    
    # Reminders: mock
    reminders = ["Buy groceries", "Call mom"]
    
    brief = f"""
    Good morning!
    
    Weather: {weather}
    
    Today's Calendar:
    {calendar_summary}
    
    Inbox Waiting:
    {inbox_summary}
    
    Reminders:
    {"\n".join(reminders)}
    """
    
    # Add to memory
    agent = Agent()
    agent.memory_store.add_memory("brief", brief, ["morning_brief"])
    
    # Log to ledger
    ledger_path = Path("./data/action_ledger.jsonl")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path, 'a') as f:
        json.dump({"ts": datetime.utcnow().isoformat(), "user": "system", "tool": "morning_brief", "args": {}, "result": {"ok": True}}, f)
        f.write('\n')
    
    return brief

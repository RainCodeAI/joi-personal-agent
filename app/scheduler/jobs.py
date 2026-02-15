from app.tools import calendar_gcal, email_gmail
from app.orchestrator.agent import Agent
from app.orchestrator.agents.planner import PlannerAgent
from app.memory.store import MemoryStore
from app.api.models import ChatMessage
from pathlib import Path
import json
from datetime import datetime

# Shared instances to avoid overhead if possible, though jobs run in threadpool
_planner = PlannerAgent()
_memory = MemoryStore()

def morning_brief():
    # Mock weather
    weather = "Sunny, 72°F"
    
    # Calendar today
    events = calendar_gcal.upcoming_events(days=1)
    calendar_summary = "\n".join([f"{e['summary']} at {e['start']['dateTime']}" for e in events[:5]])
    
    # Inbox waiting
    threads = email_gmail.list_threads(max_results=10)
    inbox_summary = email_gmail.summarize_threads(threads)
    
    # Habits status (Planner integration)
    habit_status = _planner.check_habits("default", _memory) or "Habits are on track!"
    
    # Reminders: mock
    reminders = ["Buy groceries", "Call mom"]
    reminders_text = "\n".join(reminders)
    
    brief = f"""
    Good morning!
    
    Weather: {weather}
    
    Today's Calendar:
    {calendar_summary}
    
    Inbox Waiting:
    {inbox_summary}
    
    Habit Check:
    {habit_status}
    
    Reminders:
    {reminders_text}
    """
    
    # Add to memory
    agent = Agent()
    agent.memory_store.add_memory("brief", brief, ["morning_brief"])
    # Also add to chat history so user sees it
    agent.memory_store.add_chat_message("default", "assistant", f"🌅 **Morning Brief**\n{brief}")
    
    # Log to ledger
    _log_action("morning_brief", {}, {"ok": True})
    
    return brief

def check_mood_trends():
    """Projective job: Check mood trends and nudge if needed."""
    session_id = "default"
    msg = _planner.check_mood_trends(session_id, _memory)
    if msg:
        # Post to chat
        _memory.add_chat_message(session_id, "assistant", f"🩺 **Health Check**: {msg}")
        _log_action("check_mood_trends", {}, {"triggered": True, "msg": msg})
        return msg
    _log_action("check_mood_trends", {}, {"triggered": False})
    return None

def check_habits():
    """Proactive job: Check for neglected habits."""
    session_id = "default"
    msg = _planner.check_habits(session_id, _memory)
    if msg:
        _memory.add_chat_message(session_id, "assistant", f"🔔 **Habit Nudge**: {msg}")
        _log_action("check_habits", {}, {"triggered": True, "msg": msg})
        return msg
    _log_action("check_habits", {}, {"triggered": False})
    return None

def scan_patterns():
    """Run data pattern engine to detect anomalies."""
    from app.orchestrator.pattern_engine import PatternEngine
    # Initialize engine (lazy load if needed, or global)
    engine = PatternEngine()
    session_id = "default"
    
    insights = engine.scan(session_id)
    if insights:
        # Log insights
        _log_action("scan_patterns", {}, {"insights": insights})
        
        # Sprint 7.2: Action Flows
        from app.orchestrator.action_engine import ActionEngine
        # Lazy load ActionEngine (MemoryStore + HuggingFace pipelne)
        # Verify overhead? It's fine for an hourly job.
        try:
            actor = ActionEngine()
            for insight in insights:
                did_act = actor.dispatch(session_id, insight)
                if did_act:
                     _log_action("scan_patterns_acted", {}, {"insight": insight})
        except Exception as e:
            _log_action("scan_patterns_error", {}, {"error": str(e)})

        return insights
    
    _log_action("scan_patterns", {}, {"insights": []})
    return []

def groom_memory():
    """Phase 11: Auto-prune weak graph connections and stale episodic memories."""
    stats = _memory.groom_memory_graph(min_weight=1.0, max_age_days=90)
    _memory.decay_relationships(decay_factor=0.95)
    _log_action("groom_memory", {}, stats)
    total = sum(stats.values())
    if total > 0:
        print(f"Memory groomed: {stats}")
    return stats


def _log_action(tool_name, args, result):
    ledger_path = Path("./data/action_ledger.jsonl")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(ledger_path, 'a') as f:
            json.dump({
                "ts": datetime.utcnow().isoformat(),
                "user": "system",
                "tool": tool_name,
                "args": args,
                "result": result
            }, f)
            f.write('\n')
    except Exception:
        pass

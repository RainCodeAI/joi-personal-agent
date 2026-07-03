from __future__ import annotations

import re
from typing import Any, Dict, List

import httpx

from app.config import settings


TIME_BLOCK_RE = re.compile(r"^\s*(?P<time>[^:]+?)\s*:\s*(?P<activity>.+?)\s*$")


def build_planner_snapshot(memory_store, user_id: str = "default") -> Dict[str, Any]:
    habits = memory_store.get_habits(user_id)
    goals = memory_store.get_personal_goals(user_id)
    recent_moods = memory_store.get_recent_moods(user_id, 7)
    latest_mood = recent_moods[0].mood if recent_moods else 5

    return {
        "user_id": user_id,
        "habits": habits,
        "goals": goals,
        "recent_moods": recent_moods,
        "latest_mood": latest_mood,
        "mood_trend": memory_store.mood_trend_analysis(user_id),
        "health_correlation": memory_store.correlate_health_mood(user_id),
        "overdue_contacts": memory_store.get_overdue_contacts(user_id=user_id),
    }


def generate_day_plan(
    memory_store,
    *,
    user_id: str,
    key_tasks: List[str],
    focus_areas: List[str],
    energy_level: int,
) -> Dict[str, Any]:
    snapshot = build_planner_snapshot(memory_store, user_id=user_id)
    prompt = _planner_prompt(
        habits=snapshot["habits"],
        goals=snapshot["goals"],
        key_tasks=key_tasks,
        focus_areas=focus_areas,
        energy_level=energy_level,
        latest_mood=snapshot["latest_mood"],
        mood_trend=snapshot["mood_trend"],
    )

    provider = "fallback"
    raw_plan = ""
    try:
        with httpx.Client(timeout=settings.router_timeout) as client:
            response = client.post(
                f"{settings.ollama_host}/api/generate",
                json={
                    "model": settings.model_ollama,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            raw_plan = response.json().get("response", "")
            provider = "ollama"
    except Exception:
        raw_plan = _fallback_plan(key_tasks, focus_areas, energy_level)

    blocks = _parse_plan(raw_plan)
    if not blocks:
        raw_plan = _fallback_plan(key_tasks, focus_areas, energy_level)
        blocks = _parse_plan(raw_plan)
        provider = "fallback"

    return {
        "provider": provider,
        "model": settings.model_ollama if provider == "ollama" else "",
        "prompt": prompt,
        "raw_plan": raw_plan,
        "blocks": blocks,
        "snapshot": snapshot,
    }


def _planner_prompt(
    *,
    habits,
    goals,
    key_tasks: List[str],
    focus_areas: List[str],
    energy_level: int,
    latest_mood: int,
    mood_trend: Dict[str, Any],
) -> str:
    active_goals = [goal.name for goal in goals if getattr(goal, "status", "active") == "active"]
    habit_names = [habit.name for habit in habits]
    mood_direction = mood_trend.get("direction", "flat")

    return (
        "Generate a realistic time-blocked day plan starting at 8:00.\n"
        "Format every line exactly as '8:00-9:00: Activity'.\n"
        "Keep the day balanced, include breaks, and respect energy.\n"
        f"Habits: {', '.join(habit_names) or 'None'}\n"
        f"Active goals: {', '.join(active_goals) or 'None'}\n"
        f"Key tasks: {', '.join(key_tasks) or 'None'}\n"
        f"Focus areas: {', '.join(focus_areas) or 'None'}\n"
        f"Energy level: {energy_level}/10\n"
        f"Latest mood: {latest_mood}/10\n"
        f"Mood trend: {mood_direction}\n"
    )


def _parse_plan(plan_text: str) -> List[Dict[str, str]]:
    blocks: List[Dict[str, str]] = []
    for line in plan_text.splitlines():
        match = TIME_BLOCK_RE.match(line.strip(" -"))
        if not match:
            continue
        blocks.append(
            {
                "time": match.group("time").strip(),
                "activity": match.group("activity").strip(),
            }
        )
    return blocks


def _fallback_plan(key_tasks: List[str], focus_areas: List[str], energy_level: int) -> str:
    tasks = [task.strip() for task in key_tasks if task.strip()]
    focus_label = ", ".join(focus_areas) if focus_areas else "General"
    midday = "Recovery break" if energy_level <= 4 else "Focused work block"
    late_block = tasks[1] if len(tasks) > 1 else f"{focus_label} admin"
    closing = tasks[2] if len(tasks) > 2 else "Review and plan tomorrow"

    first_task = tasks[0] if tasks else f"{focus_label} priority work"
    return "\n".join(
        [
            "8:00-9:00: Morning reset and planning",
            f"9:00-11:00: {first_task}",
            f"11:00-12:00: {midday}",
            f"13:00-15:00: {late_block}",
            f"15:00-16:00: {closing}",
        ]
    )

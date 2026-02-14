import streamlit as st
from app.memory.store import MemoryStore
from app.config import settings
import httpx
from datetime import datetime, timedelta

def main():
    st.title("📅 Day Planner")
    st.markdown("Reclaim-inspired time blocking: Build your day from habits and todos.")

    memory_store = MemoryStore()
    user_id = "default"  # TODO: from session

    # Get data
    habits = memory_store.get_habits(user_id)
    goals = memory_store.get_personal_goals(user_id)
    recent_moods = memory_store.get_recent_moods(user_id, 1)
    current_mood = recent_moods[0].mood if recent_moods else 5

    # Inputs
    st.subheader("Today's Focus")
    key_tasks = st.text_area("Key tasks/todos (one per line):", "Meeting with team\nCode review\nExercise")
    focus_areas = st.multiselect("Focus areas:", ["Work", "Health", "Learning", "Personal"], ["Work", "Health"])
    energy_level = st.slider("Energy level (1-10):", 1, 10, current_mood)

    # Generate Plan
    if st.button("Generate Day Plan"):
        plan = generate_plan(habits, goals, key_tasks.split('\n'), focus_areas, energy_level, memory_store, user_id)
        st.session_state.plan = plan
        st.success("Plan generated!")

    # Display Plan
    if "plan" in st.session_state:
        st.subheader("Your Day Plan")
        for block in st.session_state.plan:
            st.write(f"**{block['time']}**: {block['activity']}")

        # Sync to Calendar
        if st.button("Sync Plan to Google Calendar"):
            from app.tools import calendar_gcal
            for block in st.session_state.plan:
                try:
                    # Parse time (simple)
                    time_str = block['time']
                    if '-' in time_str:
                        start_str, end_str = time_str.split('-')
                        start_time = datetime.strptime(start_str.strip(), "%H:%M").time()
                        end_time = datetime.strptime(end_str.strip(), "%H:%M").time()
                        today = datetime.now().date()
                        start_dt = datetime.combine(today, start_time)
                        end_dt = datetime.combine(today, end_time)
                        calendar_gcal.create_event(block['activity'], start_dt.isoformat(), end_dt.isoformat())
                        st.success(f"Synced: {block['activity']}")
                    else:
                        st.warning(f"Invalid time for {block['activity']}")
                except Exception as e:
                    st.error(f"Error syncing {block['activity']}: {e}")
            st.success("Sync complete!")

def generate_plan(habits, goals, tasks, focus_areas, energy, store, user_id):
    # Use Ollama to generate/refine plan
    prompt = f"""
    Generate a time-blocked day plan starting from 8 AM. Include:
    - Habits: {', '.join([h.name for h in habits])}
    - Goals: {', '.join([g.name for g in goals if g.status == 'active'])}
    - Key tasks: {', '.join(tasks)}
    - Focus areas: {', '.join(focus_areas)}
    - Energy level: {energy}/10 (adjust for breaks if low)
    Format as: Time: Activity (e.g., 8:00-9:00 AM: Morning exercise)
    Keep realistic, include breaks.
    """
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{settings.ollama_host}/api/generate",
                json={"model": settings.model_chat, "prompt": prompt, "stream": False}
            )
            response.raise_for_status()
            plan_text = response.json()["response"]
    except Exception as e:
        plan_text = "Error generating plan: " + str(e)

    # Parse into blocks (simple split)
    blocks = []
    for line in plan_text.split('\n'):
        if ':' in line and '-' in line:
            try:
                time_part, activity = line.split(':', 1)
                blocks.append({"time": time_part.strip(), "activity": activity.strip()})
            except:
                pass
    return blocks if blocks else [{"time": "8:00-9:00", "activity": "Generated plan (check Ollama)"}]

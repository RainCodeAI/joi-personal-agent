import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import streamlit as st
from app.config import settings
from app.memory.store import MemoryStore
from app.api.models import UserProfile, Milestone, MoodEntry, Habit, PersonalGoal, ActivityLog, Contact, SleepLog, Transaction
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SQLSession

# Replicate engine for local query (MVP; ideally add get_contacts to MemoryStore)
engine = create_engine(settings.database_url or f"sqlite:///{settings.db_path}")

def main():
    st.title("👤 User Profile")
    
    st.markdown("""
    **Joi's Personality**: Inspired by Joi from Blade Runner 2049, I am a serene, adaptive AI companion. 
    I communicate with warmth and precision, always prioritizing your well-being in this neon-lit world.
    """)
    
    memory_store = MemoryStore()
    
    # User Details
    st.subheader("User Details")
    profile = memory_store.get_user_profile("default") or UserProfile(user_id="default")
    name = st.text_input("Name", value=profile.name or "")
    email = st.text_input("Email", value=profile.email or "")
    birthday = st.text_input("Birthday", value=profile.birthday or "")
    hobbies = st.text_area("Hobbies", value=profile.hobbies or "")
    relationships = st.text_area("Relationships", value=profile.relationships or "")
    notes = st.text_area("Notes", value=profile.notes or "")
    
    # Mood Tracking
    st.subheader("Mood Tracking")
    mood = st.slider("How are you feeling today? (1-10)", 1, 10, 5)
    if st.button("Save Today's Mood"):
        from datetime import datetime
        mood_entry = MoodEntry(user_id="default", date=datetime.utcnow().date(), mood=mood)
        memory_store.add_mood_entry(mood_entry)
        st.success("Mood saved!")
    
    recent_moods = memory_store.get_recent_moods("default")
    if recent_moods:
        st.write("Recent Moods:")
        for m in recent_moods[:7]:  # Last 7 days
            st.write(f"{m.date}: {m.mood}/10")
    
    # Therapeutic Mode
    therapeutic = st.checkbox("Enable Therapeutic Mode", value=profile.therapeutic_mode, key="therapeutic_mode")
    
    # Personality
    personality_options = ["Default", "Witty", "Supportive", "Sarcastic", "Professional"]
    personality = st.selectbox("Personality Mode", personality_options, index=personality_options.index(profile.personality) if profile.personality in personality_options else 0)
    
    # Humor Level
    humor_level = st.slider("Humor Level", 1, 10, value=profile.humor_level, help="1 = Serious, 10 = Very Witty")
    
    # Habits
    st.subheader("Habits & Routines")
    habit_name = st.text_input("Add a new habit:")
    if st.button("Add Habit"):
        habit = Habit(user_id="default", name=habit_name)
        memory_store.add_habit(habit)
        st.success("Habit added!")
    
    habits = memory_store.get_habits("default")
    if habits:
        st.write("Your Habits:")
        for h in habits:
            col1, col2 = st.columns([3,1])
            with col1:
                st.write(f"**{h.name}** - Streak: {h.streak} days")
            with col2:
                if st.button(f"Done Today - {h.name}", key=f"done_{h.id}"):
                    from datetime import datetime, timedelta
                    now = datetime.utcnow()
                    if h.last_done and (now - h.last_done).days == 1:
                        streak = h.streak + 1
                    elif h.last_done and (now.date() == h.last_done.date()):
                        streak = h.streak  # Already done today
                    else:
                        streak = 1
                    memory_store.update_habit_streak(h.id, streak, now)
                    st.success(f"Great! Streak for {h.name}: {streak} days")
                    st.rerun()
    
    # Personal Goals
    st.subheader("Personal Goals")
    goal_name = st.text_input("Add a new goal:")
    goal_desc = st.text_area("Description:", key="goal_desc")
    if st.button("Add Goal"):
        goal = PersonalGoal(user_id="default", name=goal_name, description=goal_desc)
        memory_store.add_personal_goal(goal)
        st.success("Goal added!")
    
    goals = memory_store.get_personal_goals("default")
    if goals:
        st.write("Your Goals:")
        for g in goals:
            col1, col2 = st.columns([3,1])
            with col1:
                st.write(f"**{g.name}** - {g.description} (Status: {g.status})")
            with col2:
                if st.button(f"Mark Complete - {g.name}", key=f"complete_{g.id}"):
                    memory_store.update_goal_status(g.id, "completed")
                    st.success(f"Goal '{g.name}' marked complete!")
                    st.rerun()
    
    # CBT Exercises
    st.subheader("CBT Exercises")
    exercise_name = st.text_input("Add CBT Exercise:")
    exercise_desc = st.text_area("Description:", key="exercise_desc")
    if st.button("Add Exercise"):
        from app.api.models import CbtExercise
        exercise = CbtExercise(user_id="default", name=exercise_name, description=exercise_desc)
        memory_store.add_cbt_exercise(exercise)
        st.success("CBT Exercise added!")
    
    exercises = memory_store.get_cbt_exercises("default")
    if exercises:
        st.write("Your CBT Exercises:")
        for e in exercises:
            col1, col2 = st.columns([3,1])
            with col1:
                st.write(f"**{e.name}** - {e.description} (Completed: {e.completed_count})")
            with col2:
                if st.button(f"Mark Done - {e.name}", key=f"done_cbt_{e.id}"):
                    memory_store.complete_cbt_exercise(e.id)
                    st.success(f"Completed '{e.name}'!")
                    st.rerun()
    
    # Activity Log
    st.subheader("Activity Tracking")
    app_name = st.text_input("Log Activity - App Name:")
    duration = st.number_input("Duration (minutes):", min_value=1, value=30)
    if st.button("Log Activity"):
        from datetime import datetime
        activity = ActivityLog(user_id="default", app=app_name, duration=duration*60)  # convert to seconds
        memory_store.add_activity_log(activity)
        st.success(f"Activity logged: {app_name} for {duration} mins")
    
    activities = memory_store.get_recent_activities("default", 10)
    if activities:
        st.write("Recent Activities:")
        for a in activities:
            st.write(f"{a.app}: {a.duration//60} mins at {a.timestamp}")
    else:
        st.write("No activities logged yet.")
    
    # Sleep Log
    st.subheader("Sleep Log")
    with st.expander("Log Last Night's Sleep"):
        col1, col2 = st.columns(2)
        with col1:
            hours = st.number_input("Hours Slept:", min_value=0.0, max_value=24.0, value=7.0, step=0.5)
        with col2:
            quality = st.slider("Quality (1-10):", 1, 10, 5)
        date_log = st.date_input("Date:", value=date.today(), key="sleep_date")
        if st.button("Log Sleep"):
            memory_store.add_sleep_log(hours, quality, date_log)
            st.success("Sleep logged!")

    # Recent Sleeps
    recent_sleeps = memory_store.get_recent_sleeps("default")
    if recent_sleeps:
        st.write("Recent Sleeps:")
        for s in recent_sleeps:
            st.write(f"{s.date}: {s.hours_slept}hrs (Q: {s.quality}/10)")
    else:
        st.write("No sleep logs yet—log some to see trends!")

    # Transaction Log
    st.subheader("Transaction Log")
    with st.expander("Log a Transaction"):
        col1, col2, col3 = st.columns(3)
        with col1:
            amt = st.number_input("Amount ($):", min_value=-1000.0, max_value=1000.0, value=-5.0, step=0.5)
        with col2:
            cat = st.selectbox("Category:", ["food", "transport", "entertainment", "other"])
        with col3:
            date_tx = st.date_input("Date:", value=date.today(), key="tx_date")
        if st.button("Log Transaction"):
            memory_store.add_transaction(amt, cat, date_tx)
            st.success("Transaction logged!")

    # Recent Transactions
    recent_txs = memory_store.get_recent_transactions("default")
    if recent_txs:
        st.write("Recent Transactions:")
        for t in recent_txs:
            st.write(f"{t.date}: ${t.amount:.2f} ({t.category})")
    else:
        st.write("No transactions logged yet—log some to see correlations!")

    # Contacts & Relationships - Phase 3 Stub
    st.subheader("Contacts & Relationships")
    with st.expander("Add Contact"):
        col1, col2 = st.columns(2)
        with col1:
            contact_name = st.text_input("Name:")
            strength = st.slider("Relationship Strength (1-10):", 1, 10, 5)
        with col2:
            last_contact = st.date_input("Last Contact:", value=date.today(), key="contact_date")
        if st.button("Add Contact"):
            memory_store.add_contact(contact_name, last_contact, strength, user_id="default")
            st.success("Contact added!")
            st.rerun()
    
    # List contacts
    with SQLSession(engine) as session:
        contacts = session.query(Contact).filter(Contact.user_id == "default").all()
    if contacts:
        st.write("Your Contacts:")
        for c in contacts:
            st.write(f"**{c.name}** (Strength: {c.strength}) - Last: {c.last_contact}")
    else:
        st.write("No contacts added yet.")
    
    if st.button("Save Profile"):
        profile.name = name
        profile.email = email
        profile.birthday = birthday
        profile.hobbies = hobbies
        profile.relationships = relationships
        profile.notes = notes
        profile.therapeutic_mode = therapeutic
        profile.personality = personality
        profile.humor_level = humor_level
        memory_store.save_user_profile(profile)
        st.success("Profile saved!")
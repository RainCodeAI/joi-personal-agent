import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import streamlit as st
from app.memory.store import MemoryStore
import pandas as pd

def main():
    st.title("📊 Analytics Dashboard")
    
    memory_store = MemoryStore()
    
    # Metrics
    st.subheader("Key Metrics")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Messages", 42)  # TODO: Query DB
    with col2:
        st.metric("Tools Used", 15)
    with col3:
        st.metric("Memories Stored", 28)
    
    # Charts
    st.subheader("Engagement Charts")
    # Placeholder data
    messages_data = pd.DataFrame({"Date": ["2023-01", "2023-02"], "Messages": [20, 22]})
    st.bar_chart(messages_data.set_index("Date"))
    
    tools_data = pd.Series({"Email": 5, "Calendar": 7, "Files": 3})
    st.bar_chart(tools_data)
    
    # Weekly Mood Orb Summary (Inspired by Tochi)
    st.subheader("Weekly Mood Orb Summary")
    recent_moods = memory_store.get_recent_moods("default", 7)  # Last 7 days
    if recent_moods:
        # Group by day
        mood_by_day = {}
        for m in recent_moods:
            day = m.date.strftime("%A")  # e.g., Monday
            mood_by_day[day] = m.mood
        
        # Display orbs
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for day in days:
            mood = mood_by_day.get(day, 5)  # Default neutral
            color = get_mood_color(mood)
            st.markdown(f"**{day}**: <span style='color:{color}; font-size:24px;'>●</span> (Mood: {mood}/10)", unsafe_allow_html=True)
        
        # Trend
        avg_mood = sum(m.mood for m in recent_moods) / len(recent_moods)
        st.write(f"Average Mood This Week: {avg_mood:.1f}/10")
    else:
        st.write("No mood data yet. Log moods in Profile!")

def get_mood_color(mood):
    if mood <= 3:
        return "red"
    elif mood <= 5:
        return "orange"
    elif mood <= 7:
        return "yellow"
    else:
        return "green"

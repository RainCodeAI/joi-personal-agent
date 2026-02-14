import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import streamlit as st
from app.memory.store import MemoryStore
import json

def main():
    st.title("📜 Chat History Browser")
    
    memory_store = MemoryStore()
    
    # List Sessions
    st.subheader("Chat Sessions")
    sessions = ["default"]  # TODO: Query DB for sessions
    selected_session = st.selectbox("Select Session", sessions)
    
    # Search
    search = st.text_input("Search Messages")
    
    # Display Messages
    if selected_session:
        messages = memory_store.get_chat_history(selected_session) or []
        for msg in messages:
            if search.lower() in msg.content.lower():
                st.write(f"**{msg.role}**: {msg.content}")
    
    # Actions
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("View Full Chat"):
            st.json([msg.dict() for msg in messages])
    with col2:
        if st.button("Export to JSON"):
            data = [msg.dict() for msg in messages]
            st.download_button("Download JSON", json.dumps(data), "chat.json")
    with col3:
        if st.button("Delete Session"):
            # TODO: Delete from DB
            st.success("Session deleted!")

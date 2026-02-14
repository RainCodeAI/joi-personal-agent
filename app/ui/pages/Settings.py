import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import streamlit as st
import requests
from app.memory.store import MemoryStore
from app.api.models import UserProfile

def main():
    st.title("Settings")
    
    try:
        st.subheader("Google OAuth")
        if st.button("Connect Gmail"):
            # Call backend /oauth/start
            response = requests.get("http://localhost:8000/oauth/start")
            if response.status_code == 200:
                auth_url = response.json()["auth_url"]
                st.markdown(f"[Authorize here]({auth_url})")
            else:
                st.error("Failed to start OAuth")
        
        if st.button("Connect Calendar"):
            st.write("Same as Gmail, but separate")
        
        st.subheader("Vault Status")
        st.write("Vault: Encrypted with passphrase")
        
        st.subheader("Index Folders")
        folder = st.text_input("Folder to index:", key="settings_folder")
        if st.button("Index", key="settings_index"):
            # Call ingest
            st.write(f"Indexing {folder}...")
        
        st.subheader("Persona Toggle")
        store = MemoryStore()
        profile = store.get_user_profile("default") or UserProfile()
        personas = ["Default", "Witty", "Supportive", "Sarcastic", "Professional"]
        selected = st.selectbox("Active Persona:", personas, index=personas.index(profile.personality) if profile.personality in personas else 0)
        if st.button("Apply"):
            profile.personality = selected
            store.save_user_profile(profile)
            st.success(f"Persona: {selected}—restart chat!")
        
        # Voice controls moved to global sidebar (components.py)
        st.info("Pro Tip: Low mood? Enable Therapeutic Mode in Profile.")
    except Exception as e:
        st.error(f"Error loading settings page: {e}")
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
        
        # ── Autonomy Level ────────────────────────────────────────────────
        st.subheader("🛡️ Autonomy Level")
        from app.config import settings as app_settings
        
        autonomy_options = {
            "low": "🔒 Low — Reactive only (Joi responds, never initiates)",
            "medium": "⚖️ Medium — Proactive suggestions (always asks first)",
            "high": "🚀 High — Proactive actions (post-hoc notifications)",
        }
        current_level = app_settings.autonomy_level
        autonomy_keys = list(autonomy_options.keys())
        current_idx = autonomy_keys.index(current_level) if current_level in autonomy_keys else 1
        
        selected_autonomy = st.selectbox(
            "How autonomous should Joi be?",
            options=autonomy_keys,
            format_func=lambda x: autonomy_options[x],
            index=current_idx,
            key="autonomy_level_select"
        )
        
        if st.button("Save Autonomy Level", key="save_autonomy"):
            app_settings.autonomy_level = selected_autonomy
            st.success(f"Autonomy set to **{selected_autonomy.upper()}**. Joi will adapt immediately.")
            
        # ── Proactive Control ────────────────────────────────────────────────
        st.subheader("🤖 Proactive Messaging")
        proactive_enabled = st.checkbox(
            "Enable Proactive Messages",
            value=app_settings.enable_proactive_messaging,
            help="Allow Joi to initiate conversations based on patterns (e.g., silence breaking)."
        )
        if proactive_enabled != app_settings.enable_proactive_messaging:
             app_settings.enable_proactive_messaging = proactive_enabled
             state_msg = "enabled" if proactive_enabled else "disabled"
             st.toast(f"Proactive messaging {state_msg}.")
             
        # ── Audit Log ────────────────────────────────────────────────────────
        st.subheader("📜 Activity Log")
        with st.expander("View Recent System Actions"):
             ledger_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data/action_ledger.jsonl"))
             if os.path.exists(ledger_path):
                 try:
                     with open(ledger_path, "r", encoding="utf-8") as f:
                         lines = f.readlines()
                         if not lines:
                             st.info("Log is empty.")
                         else:
                             # Show last 10 actions, newest first
                             for line in reversed(lines[-10:]):
                                 st.code(line.strip(), language="json")
                 except Exception as e:
                     st.error(f"Error reading log: {e}")
             else:
                 st.info("No actions logged yet.")
        
        # Voice controls moved to global sidebar (components.py)
        st.info("Pro Tip: Low mood? Enable Therapeutic Mode in Profile.")
    except Exception as e:
        st.error(f"Error loading settings page: {e}")
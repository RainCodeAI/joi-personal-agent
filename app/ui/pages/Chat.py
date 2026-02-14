import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import streamlit as st
from app.orchestrator.agent import Agent
from app.memory.store import MemoryStore
from app.scheduler.jobs import morning_brief
from app.api.models import ChatMessage, Feedback, Decision
from app.orchestrator.security.approval import ToolApprovalManager
# Voice controls now in global sidebar (components.py)
from PIL import Image
from pathlib import Path
from datetime import datetime, timedelta

def main():
    st.title("👁️ Chat with Joi")
    
    if "session_id" not in st.session_state:
        st.session_state.session_id = "default"  # Or generate unique
    
    agent = Agent()
    memory_store = MemoryStore()
    
    # Init chat_history FIRST (moved up to fix AttributeError)
    if "chat_history" not in st.session_state:
        # Load from DB
        db_history = memory_store.get_chat_history(st.session_state.session_id)
        st.session_state.chat_history = db_history if db_history else []
    
    # Voice mode is controlled from the global sidebar (see components.py)
    if 'voice_mode' not in st.session_state:
        st.session_state.voice_mode = False
    
    # Display history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg.role):
            st.write(msg.content)
    
    # Avatar Display (Phase 5 Buffer - Mood + Lip-Sync)
    if st.session_state.chat_history:
        last_msg = st.session_state.chat_history[-1]
        if last_msg.role == "assistant":
            # Mood-based expression (fresh data only)
            recent_moods = memory_store.get_recent_moods(st.session_state.session_id, 3)  # Last 3
            expression = "Neutral"  # Default
            cutoff = datetime.now().date() - timedelta(days=3)
            fresh_moods = [m for m in recent_moods if m.date.date() >= cutoff]  # Fixed: .date() for comparison
            if fresh_moods:
                avg_mood = sum(m.mood for m in fresh_moods) / len(fresh_moods)
                if avg_mood >= 7:
                    expression = "Smile"
                elif avg_mood <= 4:
                    expression = "Frown"
                elif avg_mood < 3:
                    expression = "Shock"
            
            # Base face PNG
            base_path = f"./assets/Joi_{expression}.png"
            if Path(base_path).exists():
                base_img = Image.open(base_path)
                st.image(base_img, caption="Joi", use_column_width=True, width=200)
            else:
                st.warning(f"Add {base_path} to ./assets/ for expression")
            
            # Lip-Sync Mouth (TTS trigger)
            if st.session_state.get('voice_mode', False):
                sync_data = agent.say_and_sync(last_msg.content, st.session_state.session_id)
                phonemes = sync_data.get("phoneme_timeline", [])
                if phonemes:
                    st.subheader("Lip-Sync")
                    cols = st.columns(min(5, len(phonemes)))
                    for i, (time, ph) in enumerate(phonemes[:5]):  # Limit to 5 for UI
                        with cols[i]:
                            mouth_path = f"./assets/Joi_{ph}.png"  # e.g., Joi_A.png
                            if Path(mouth_path).exists():
                                mouth_img = Image.open(mouth_path)
                                st.image(mouth_img, width=50, caption=ph)
                            openness = min(1.0, time * 2)  # Fake animation
                            st.progress(openness, text=f"{ph} (Open: {openness:.0%})")
    
    # Voice components (commented JS for future browser-based fallback if needed)
    # voice_js = """
    # <script>
    # function startRecognition() {
    #     if (!('webkitSpeechRecognition' in window)) {
    #         alert('Speech recognition not supported');
    #         return;
    #     }
    #     const recognition = new webkitSpeechRecognition();
    #     recognition.continuous = false;
    #     recognition.interimResults = false;
    #     recognition.lang = 'en-US';
    #     recognition.onresult = function(event) {
    #         const transcript = event.results[0][0].transcript;
    #         // Send to Streamlit
    #         window.parent.postMessage({type: 'speech', text: transcript}, '*');
    #     };
    #     recognition.start();
    # }
    # 
    # function speakText(text) {
    #     if ('speechSynthesis' in window) {
    #         const utterance = new SpeechSynthesisUtterance(text);
    #         window.speechSynthesis.speak(utterance);
    #     } else {
    #         alert('Text-to-speech not supported');
    #     }
    # }
    # </script>
    # """
    # st.components.v1.html(voice_js, height=0)
    
    # Input section
    # STT "Speak" button moved to global sidebar — pending_transcript flows via session_state

    # ── Pending Tool Approvals (Human-in-the-Loop) ────────────────────
    approval_mgr = ToolApprovalManager.from_session_state(st.session_state)
    pending = approval_mgr.get_pending()
    if pending:
        st.warning(f"⚠️ {len(pending)} tool action(s) awaiting your approval:")
        for pa in pending:
            acol1, acol2, acol3 = st.columns([3, 1, 1])
            with acol1:
                st.markdown(f"**{pa.tool_name}** — args: `{pa.args}`")
            with acol2:
                if st.button("✅ Approve", key=f"approve_{pa.id}"):
                    approval_mgr.approve(pa.id)
                    st.toast(f"Approved: {pa.tool_name}")
                    st.rerun()
            with acol3:
                if st.button("❌ Deny", key=f"deny_{pa.id}"):
                    approval_mgr.deny(pa.id)
                    st.toast(f"Denied: {pa.tool_name}")
                    st.rerun()

    # Now the form (button-free)
    with st.form(key="chat_form"):
        if st.session_state.get('voice_mode', False):
            # Use pending transcript if available, else fallback input
            default_input = st.session_state.get("pending_transcript", "")
            if default_input:
                user_input = st.text_input("Transcribed (edit & send):", value=default_input, placeholder="Type if mic fails")
                # Clear it after rendering to avoid re-use
                del st.session_state.pending_transcript
            else:
                user_input = st.text_input("Type message (mic failed):", placeholder="Type if mic fails")
        else:
            user_input = st.text_input("Your message:")

        submitted = st.form_submit_button("Send")
        
        if submitted and user_input.strip():
            # Add to history
            user_msg = ChatMessage(role="user", content=user_input)
            st.session_state.chat_history.append(user_msg)
            
            response = agent.reply(st.session_state.chat_history, user_input, st.session_state.session_id)
            
            assistant_msg = ChatMessage(role="assistant", content=response.text)
            st.session_state.chat_history.append(assistant_msg)
            
            if response.tool_calls:
                st.write("Tool calls:", response.tool_calls)
                st.toast("Tool executed successfully!")
            
            # TTS if voice mode (voice_tools accessed via lazy import)
            if st.session_state.get('voice_mode', False):
                try:
                    from app.tools.voice import voice_tools
                    voice_tools.text_to_speech(response.text)
                except Exception:
                    pass
            
            st.toast("Joi responded!")
            st.rerun()
    
    # Feedback for last response
    if st.session_state.chat_history and any(msg.role == "assistant" for msg in st.session_state.chat_history):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👍", key="thumbs_up"):
                # Add positive feedback
                memory_store.add_feedback(Feedback(user_id="default", message_id="last", rating=1))
                st.success("Thanks for the feedback!")
        with col2:
            if st.button("👎", key="thumbs_down"):
                memory_store.add_feedback(Feedback(user_id="default", message_id="last", rating=-1))
                st.success("Thanks for the feedback!")
    
    # Decision Helper
    st.subheader("Decision Logger")
    with st.expander("Log a Decision"):
        question = st.text_input("Decision Question:")
        pros = st.text_area("Pros:")
        cons = st.text_area("Cons:")
        outcome = st.text_input("Outcome (optional):")
        if st.button("Save Decision"):
            decision = Decision(user_id="default", question=question, pros=pros, cons=cons, outcome=outcome)
            memory_store.add_decision(decision)
            st.success("Decision logged!")
    
    decisions = memory_store.get_decisions("default")
    if decisions:
        st.write("Past Decisions:")
        for d in decisions[-5:]:  # Last 5
            st.write(f"**{d.question}** - Pros: {d.pros}, Cons: {d.cons}, Outcome: {d.outcome or 'Pending'}")
    
    if st.button("Run Morning Brief now"):
        brief = morning_brief()
        st.write("Morning Brief:", brief)
        st.toast("Morning Brief ready!")
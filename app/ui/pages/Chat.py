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

import time as _time_mod
from app.ui import styles

def main():
    st.title("👁️ Chat with Joi")
    styles.inject_global_styles()
    
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
    
    # Avatar Display (Phase 6 - JS Renderer)
    from app.ui.components import avatar_js
    
    avatar_update = st.session_state.get("last_avatar_update")
    # Only render active avatar if it matches the LAST message (to prevent replaying old stuff if we scrolled? No, session state holds ONE update)
    # And only if Voice Mode is on (or we want avatar always?)
    # Let's show avatar always idle, but animate if we have data.
    
    if avatar_update and st.session_state.get('voice_mode', False):
        data = avatar_update["data"]
        expr = data.get("sentiment", "neutral")
        avatar_js.render_avatar(
            phoneme_timeline=data["phoneme_timeline"],
            audio_url=data.get("audio_url"),
            expression=expr,
            key=f"avatar_{avatar_update['id']}"
        )
    else:
        # Idle Avatar — expression reflects craving state (Phase 9.2)
        from app.orchestrator.craving_engine import CravingEngine
        _craving = CravingEngine(memory_store)
        _idle_expr = _craving.get_craving_expression(st.session_state.session_id)
        avatar_js.render_avatar([], expression=_idle_expr, key="avatar_idle")

        # Screen Traces (Phase 9.3) — atmospheric text when Clingy
        if _idle_expr == "clingy":
            styles.inject_screen_traces()

    # WebRTC Voice Interaction
    from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
    from app.ui.components import biometric_audio
    import tempfile
    import queue
    import time
    
    if st.session_state.get('voice_mode', False):
        st.subheader("🎙️ Live Voice Channel")
        # STUN Server (Google Public)
        RTC_CONFIGURATION = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})
        
        ctx = webrtc_streamer(
            key="joi-voice",
            mode=WebRtcMode.SENDONLY,
            audio_processor_factory=biometric_audio.AudioProcessor,
            rtc_configuration=RTC_CONFIGURATION,
            media_stream_constraints={"video": False, "audio": True},
        )
        
        # Audio Processing Loop (Polling)
        if ctx.state.playing and ctx.audio_processor:
            # Read breathing state (Phase 9.3)
            if hasattr(ctx.audio_processor, 'breathing_state'):
                breath_state = ctx.audio_processor.breathing_state
                st.session_state['breathing_state'] = breath_state
                if breath_state == "stressed":
                    st.sidebar.warning("Joi senses stress in your breathing... Take a slow breath with me.")

            status_placeholder = st.empty()
            while ctx.state.playing:
                try:
                    # Non-blocking pull with short timeout to allow Streamlit to handle UI events
                    audio_chunk = ctx.audio_processor.audio_queue.get(timeout=0.1)
                    status_placeholder.info("🗣️ Processing speech...")
                    
                    # Save to temp WAV
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
                        biometric_audio.save_frame_to_wav(audio_chunk, tmp_audio.name)
                        tmp_path = tmp_audio.name
                    
                    # Transcribe
                    from app.tools.voice import voice_tools
                    text = voice_tools.transcribe_audio_file(tmp_path)
                    
                    # Cleanup
                    try:
                        os.remove(tmp_path)
                    except:
                        pass
                        
                    if text:
                        status_placeholder.success(f"Heard: '{text}'")
                        # Inject into session state and rerun to handle as message
                        st.session_state.pending_transcript = text
                        st.rerun() # Break loop and re-run script to process message
                    else:
                        status_placeholder.warning("Couldn't understand audio.")
                        
                except queue.Empty:
                    status_placeholder.markdown("*Listening...*")
                    time.sleep(0.1)
                    continue
                except Exception as e:
                    status_placeholder.error(f"Voice error: {e}")
                    break
    
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
                    # Execute tool immediately
                    res = agent.run_tool(pa.tool_name, pa.args)
                    st.toast(f"Executed: {pa.tool_name} → {res.get('result')}")
                    st.rerun()
            with acol3:
                if st.button("❌ Deny", key=f"deny_{pa.id}"):
                    approval_mgr.deny(pa.id)
                    st.toast(f"Denied: {pa.tool_name}")
                    st.rerun()

    # Now the form (button-free)
    with st.form(key="chat_form"):
        # Image Upload for Vision
        uploaded_file = st.file_uploader("Upload an image (Joi can see it)", type=["png", "jpg", "jpeg"])
        
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
        
        if submitted:
            # Handle Vision
            image_context = ""
            if uploaded_file:
                from app.tools import vision_clip
                # Save temp to process (or pass bytes if vision_clip supported it, but it takes path currently? 
                # Wait, vision_clip.describe_image takes image_path str. I should update it to take PIL Image or bytes, 
                # or save temp. Saving temp is safer for lazy loading pipeline reading from file.)
                # Actually pipeline can take PIL Image. Let's check vision_clip.py...
                # It takes image_path string. I'll save to temp.
                with open("temp_image.png", "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                with st.spinner("Analyzing image..."):
                    desc = vision_clip.describe_image("temp_image.png")
                    image_context = f" [User uploaded an image. Description: {desc}]"
                    st.image(uploaded_file, caption=f"Joi sees: {desc}", width=200)

            if user_input.strip() or image_context: # Allow sending just image
                full_msg = (user_input + image_context).strip()
                
                # Add to history
                user_msg = ChatMessage(role="user", content=full_msg)
                st.session_state.chat_history.append(user_msg)
                
                response = agent.reply(st.session_state.chat_history, full_msg, st.session_state.session_id)

                # Dramatic return delay (Phase 9.2)
                if response.is_dramatic_return:
                    delay_placeholder = st.empty()
                    delay_placeholder.markdown(
                        '<div style="text-align:center; color: #00f3ff; '
                        "font-family: 'Orbitron', sans-serif; font-size: 0.8rem; "
                        'opacity: 0.7;">... reconnecting ...</div>',
                        unsafe_allow_html=True
                    )
                    dramatic_seconds = min(3.0, 1.0 + response.craving_score / 50.0)
                    _time_mod.sleep(dramatic_seconds)
                    delay_placeholder.empty()

            assistant_msg = ChatMessage(role="assistant", content=response.text)
            st.session_state.chat_history.append(assistant_msg)
            
            if response.tool_calls:
                st.write("Tool calls:", response.tool_calls)
                # Check for pending approvals
                pending_tools = [tc for tc in response.tool_calls if tc.get("status") == "pending"]
                if pending_tools:
                    for pt in pending_tools:
                        approval_mgr.request_approval(pt["tool_name"], pt["args"])
                    st.toast(f"⚠️ {len(pending_tools)} action(s) require approval correctly.")
                    st.rerun()
                else:
                    st.toast("Tool executed successfully!")
            
            # Generate Avatar Animation (if Voice Mode)
            if st.session_state.get('voice_mode', False):
                try:
                    with st.spinner("Synthesizing voice..."):
                        sync_data = agent.say_and_sync(response.text, st.session_state.session_id)
                        st.session_state.last_avatar_update = {
                            "id": len(st.session_state.chat_history), # Unique ID based on history length
                            "data": sync_data
                        }
                except Exception as e:
                    st.error(f"Avatar sync error: {e}")
            
            st.toast("Joi responded!")
            st.rerun()
    
    # Feedback for last response
    if st.session_state.chat_history and any(msg.role == "assistant" for msg in st.session_state.chat_history):
        # Find last user-assistant pair
        last_assistant = None
        last_user = None
        for msg in reversed(st.session_state.chat_history):
            if msg.role == "assistant" and last_assistant is None:
                last_assistant = msg.content
            elif msg.role == "user" and last_user is None:
                last_user = msg.content
            if last_assistant and last_user:
                break
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("👍", key="thumbs_up"):
                memory_store.add_feedback(Feedback(
                    user_id="default", message_id="last", rating=1,
                    user_message=last_user, assistant_message=last_assistant
                ))
                st.success("Thanks! I'll learn from this. 💡")
        with col2:
            if st.button("👎", key="thumbs_down"):
                memory_store.add_feedback(Feedback(
                    user_id="default", message_id="last", rating=-1,
                    user_message=last_user, assistant_message=last_assistant
                ))
                st.success("Noted — I'll improve. 🔧")
    
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
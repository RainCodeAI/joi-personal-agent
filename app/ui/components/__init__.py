import streamlit as st

def display_chat_message(role: str, content: str):
    if role == "user":
        st.markdown(f"**You:** {content}")
    else:
        st.markdown(f"**Joi:** {content}")

def sidebar_airgap_toggle():
    airgap = st.sidebar.checkbox("Airgap Mode", value=False)
    return airgap

def sidebar_connectors_status():
    st.sidebar.subheader("Connectors")
    st.sidebar.text("Gmail: Connected" if st.session_state.get("gmail_connected") else "Gmail: Not Connected")
    st.sidebar.text("Calendar: Connected" if st.session_state.get("calendar_connected") else "Calendar: Not Connected")

def sidebar_voice_controls():
    """Global voice controls — rendered once in the sidebar, accessible from all pages."""
    st.sidebar.subheader("🎙️ Voice")
    
    # Check if voice tools are available
    try:
        from app.tools.voice import voice_tools
        voice_available = voice_tools.enabled
    except Exception:
        voice_available = False
    
    if not voice_available:
        st.sidebar.caption("Voice unavailable (missing deps)")
        if "voice_mode" not in st.session_state:
            st.session_state.voice_mode = False
        return
    
    # Voice mode toggle
    if "voice_mode" not in st.session_state:
        st.session_state.voice_mode = False
    st.session_state.voice_mode = st.sidebar.toggle(
        "Voice Mode", value=st.session_state.voice_mode, key="global_voice_toggle"
    )
    
    if st.session_state.voice_mode:
        # TTS settings
        from app.tools.voice import voice_tools
        
        st.sidebar.slider(
            "TTS Speed", 100, 200, 150, key="voice_tts_speed",
            on_change=lambda: voice_tools.tts_engine.setProperty('rate', st.session_state.voice_tts_speed)
        )
        st.sidebar.slider(
            "TTS Volume", 0.0, 1.0, 0.9, key="voice_tts_volume",
            on_change=lambda: voice_tools.tts_engine.setProperty('volume', st.session_state.voice_tts_volume)
        )
        
        # Apply current values on render
        if voice_tools.enabled:
            voice_tools.tts_engine.setProperty('rate', st.session_state.get('voice_tts_speed', 150))
            voice_tools.tts_engine.setProperty('volume', st.session_state.get('voice_tts_volume', 0.9))
        
        # STT button
        if st.sidebar.button("🎤 Speak", key="global_speak_btn", use_container_width=True):
            with st.sidebar:
                with st.spinner("Listening..."):
                    transcribed = voice_tools.speech_to_text()
                    if transcribed:
                        st.session_state.pending_transcript = transcribed
                        st.sidebar.success(f"Got: {transcribed[:40]}...")
                    else:
                        st.sidebar.warning("No speech detected")
        
        # Status indicator
        st.sidebar.caption("🟢 Voice active" if voice_tools.enabled else "🔴 Voice error")

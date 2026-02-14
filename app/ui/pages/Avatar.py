import streamlit as st
from app.orchestrator.agent import Agent
from app.ui.avatar.avatar_controller import AvatarController
import time
import base64

def main():
    st.title("🤖 Joi Avatar Demo")
    st.markdown("Experience Joi with lip-sync and expressions!")

    # Initialize
    agent = Agent()
    controller = AvatarController()

    # Input
    text_input = st.text_input("Enter text for Joi to say:", "Hello! I'm Joi, your empathetic AI companion.")
    lip_sync_offset = st.slider("Lip-sync Offset (ms)", -200, 200, 0) / 1000.0
    expression_intensity = st.slider("Expression Intensity", 0.0, 1.0, 1.0)
    idle_toggle = st.checkbox("Enable Idle Animations", True)

    if st.button("Say & Animate"):
        with st.spinner("Generating speech and lip-sync..."):
            result = agent.say_and_sync(text_input, st.session_state.get("session_id", "demo"))
            if "error" in result:
                st.error(result["error"])
                return

            audio_b64 = result["audio_url"]
            phoneme_timeline = result["phoneme_timeline"]
            sentiment = result["sentiment"]

        # Display avatar placeholder (since no images, use text)
        avatar_placeholder = st.empty()

        # Play audio
        st.audio(audio_b64, format="audio/wav")

        # Animate
        start_time = time.time()
        for layers in controller.animate_speech(phoneme_timeline, sentiment, b"", lip_sync_offset):
            # For now, display layer names
            avatar_placeholder.text(f"Layers: {', '.join([l.split('/')[-1] for l in layers])}")
            time.sleep(0.08)  # Crossfade

        # Idle loop if enabled
        if idle_toggle:
            st.write("Idle animations starting...")
            for _ in range(5):  # Demo 5 blinks
                layers = next(controller.idle_animation())
                avatar_placeholder.text(f"Idle Layers: {', '.join([l.split('/')[-1] for l in layers])}")
                time.sleep(1)

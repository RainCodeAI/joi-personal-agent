import streamlit as st
from app.orchestrator.agent import Agent
from app.ui.components.avatar_js import render_avatar

def main():
    st.title("Joi Avatar Demo")
    st.markdown("*Experience Joi with lip-sync and expressions*")

    # Initialize
    agent = Agent()

    # Input
    text_input = st.text_input(
        "Enter text for Joi to say:",
        "Hello! I'm Joi, your empathetic AI companion."
    )
    
    col1, col2 = st.columns(2)
    with col1:
        expression = st.selectbox(
            "Expression",
            ["neutral", "positive", "stress", "smirk", "shock"],
            index=0
        )
    with col2:
        lip_sync_offset = st.slider("Lip-sync Offset (ms)", -200, 200, 0)

    if st.button("Say & Animate", type="primary"):
        with st.spinner("Generating speech and lip-sync..."):
            result = agent.say_and_sync(
                text_input,
                st.session_state.get("session_id", "demo")
            )
            if "error" in result:
                st.error(result["error"])
                # Still show the avatar in neutral pose
                render_avatar(
                    phoneme_timeline=[],
                    expression=expression,
                )
                return

            audio_url = result.get("audio_url")
            phoneme_timeline = result.get("phoneme_timeline", [])
            sentiment = result.get("sentiment", expression)

        # Render the avatar with lip-sync
        render_avatar(
            phoneme_timeline=phoneme_timeline,
            audio_url=audio_url,
            expression=sentiment,
        )
    else:
        # Show idle avatar
        render_avatar(
            phoneme_timeline=[],
            expression="neutral",
        )

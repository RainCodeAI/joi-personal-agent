import streamlit as st
from datetime import datetime
from app.orchestrator.agent import Agent
from app.memory.store import MemoryStore

def main():
    st.title("AI-Assisted Journaling")
    
    # Initialize session state
    if "session_id" not in st.session_state:
        st.session_state.session_id = "default"
    
    memory_store = MemoryStore()
    agent = Agent()
    
    # Inputs
    mood = st.selectbox("How are you feeling?", ["happy", "sad", "anxious", "excited", "neutral", "angry"])
    location = st.text_input("Where are you?", "home")
    
    # Generate prompt
    if st.button("Generate Journal Prompt"):
        with st.spinner("Generating prompt..."):
            prompt = agent.journal_prompt(mood, location, st.session_state.session_id)
            st.session_state.prompt = prompt
            st.success("Prompt generated!")
    
    if "prompt" in st.session_state:
        st.subheader("Your Prompt:")
        st.write(st.session_state.prompt)
    
    # Journal entry
    entry = st.text_area("Write your journal entry:", height=200)
    
    if st.button("Analyze Entry"):
        if entry.strip():
            with st.spinner("Analyzing..."):
                analysis = agent.analyze_journal_entry(entry, st.session_state.session_id)
                st.subheader("Analysis:")
                st.write(analysis)
        else:
            st.warning("Please write something first.")
    
    # Save entry (optional)
    if st.button("Save Entry"):
        if entry.strip():
            # Save to memory (episodic)
            memory_store.add_memory("journal_entry", entry, ["journal", st.session_state.session_id])
            st.success("Entry saved!")
        else:
            st.warning("Nothing to save.")

    # Export entry to TXT
    if entry.strip():
        filename = f"journal_entry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        st.download_button(
            label="Export to TXT",
            data=entry,
            file_name=filename,
            mime="text/plain"
        )
    else:
        st.info("Write something above to enable exporting.")

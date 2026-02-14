import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import streamlit as st

def main():
    st.title("Memory")
    
    try:
        from app.memory.store import MemoryStore
        memory_store = MemoryStore()
        
        query = st.text_input("Search memories:")
        if st.button("Search"):
            results = memory_store.graph_rag_search(query)
            if not results:
                st.info("No results found.")
            for res in results:
                source = res.get("source", "vector")
                icon = "🔗" if source == "graph" else "🔍"
                entity_tag = f" · Entity: **{res['matched_entity']}**" if res.get("matched_entity") else ""
                st.markdown(
                    f"{icon} `{source}` | Distance: `{res['distance']:.4f}`{entity_tag}",
                )
                st.write(res['text'])
                st.divider()
        
        st.subheader("Recent Memories")
        # Placeholder: show recent
        st.write("Recent items would be listed here.")
    except Exception as e:
        st.error(f"Error loading memory page: {e}")


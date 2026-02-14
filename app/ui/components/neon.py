import streamlit as st
from contextlib import contextmanager

def scanlines_overlay():
    """Injects the scanlines HTML overlay (styling in styles.py)."""
    st.markdown('<div class="scanlines"></div>', unsafe_allow_html=True)

@contextmanager
def neon_card(key=None):
    """
    Context manager to wrap content in a Blade Runner-style glowing card.
    Usage:
        with neon_card():
            st.write("Content")
    """
    # Start the container
    st.markdown('<div class="neon-card">', unsafe_allow_html=True)
    try:
        yield
    finally:
        # Close the container
        st.markdown('</div>', unsafe_allow_html=True)

def rain_effect():
    """Injects the 'Matrix/Blade Runner' rain animation HTML."""
    rain_html = """
    <div class="rain">
    """
    for i in range(20):
        left = f"{i*5}%"
        delay = f"{i*0.5}s"
        duration = f"{5 + i*0.5}s"
        char = chr(65 + (i % 26))  # Random letters A-Z
        rain_html += f'<span style="left: {left}; animation-delay: {delay}; animation-duration: {duration};">{char}</span>'
    rain_html += "</div>"
    st.markdown(rain_html, unsafe_allow_html=True)

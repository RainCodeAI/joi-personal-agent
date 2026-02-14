import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import streamlit as st
from app.ui.components import sidebar_airgap_toggle, sidebar_connectors_status, sidebar_voice_controls

st.set_page_config(page_title="Joi - Personal Journal Agent", layout="wide")

# Blade Runner Theme CSS
theme_css = """
<style>
/* Dark Background and Neon Colors */
body {
    background-color: #000 !important;
    color: #00ff00 !important;
    font-family: 'Courier New', monospace !important;
}
.sidebar .sidebar-content {
    background-color: #111 !important;
}
.main .block-container {
    background-color: #000 !important;
}

/* Neon Glow for Buttons and Text */
button, .stButton>button, select {
    background-color: #000 !important;
    color: #00ff00 !important;
    border: 1px solid #00ff00 !important;
    box-shadow: 0 0 10px #00ff00 !important;
}
button:hover, .stButton>button:hover, select:hover {
    box-shadow: 0 0 20px #00ffff !important;
}

/* Headers */
h1, h2, h3, h4, h5, h6 {
    color: #00ffff !important;
    text-shadow: 0 0 10px #00ffff !important;
}

/* Chat Messages */
.chat-message.user {
    background-color: #111 !important;
    border-left: 5px solid #00ff00 !important;
}
.chat-message.assistant {
    background-color: #222 !important;
    border-left: 5px solid #00ffff !important;
}

/* Falling Code Rain Animation */
@keyframes fall {
    0% { transform: translateY(-100vh); }
    100% { transform: translateY(100vh); }
}
.rain {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: -1;
}
.rain span {
    position: absolute;
    color: #00ff00;
    font-size: 12px;
    animation: fall linear infinite;
}
</style>
"""

# Multipage
pages = {
    "👁️ Chat": "Chat",
    "🧠 Memory": "Memory",
    "⚙️ Tasks": "Tasks",
    "📅 Planner": "Planner",
    "🤖 Avatar Demo": "Avatar",
    "🔧 Settings": "Settings",
    "👤 Profile": "Profile",
    "📊 Stats": "Stats",
    "📔 Journal": "Journal",
    "🔧 Diagnostics": "Diagnostics",
    "📜 History": "History"
}

st.markdown(theme_css, unsafe_allow_html=True)

# Background Rain Effect
rain_html = """
<div class="rain">
"""
for i in range(20):
    left = f"{i*5}%"
    delay = f"{i*0.5}s"
    duration = f"{5 + i*0.5}s"
    char = chr(65 + (i % 26))  # Random letters
    rain_html += f'<span style="left: {left}; animation-delay: {delay}; animation-duration: {duration};">{char}</span>'
rain_html += "</div>"

st.markdown(rain_html, unsafe_allow_html=True)

st.markdown(rain_html, unsafe_allow_html=True)

# ── Scheduler Startup ─────────────────────────────────────────────────
@st.cache_resource
def init_scheduler():
    from app.scheduler.scheduler import start_scheduler
    start_scheduler()
    return True

init_scheduler()

sidebar_airgap_toggle()
sidebar_connectors_status()
sidebar_voice_controls()

# Chat History Sidebar
st.sidebar.subheader("Chat History")
# Placeholder: list sessions
st.sidebar.write("Sessions: default (current)")

page_key = st.sidebar.selectbox("Navigate", list(pages.keys()))
page = pages[page_key]

if page == "Chat":
    from app.ui.pages.Chat import main
    main()
elif page == "Memory":
    from app.ui.pages.Memory import main
    main()
elif page == "Tasks":
    from app.ui.pages.Tasks import main
    main()
elif page == "Planner":
    from app.ui.pages.Planner import main
    main()
elif page == "Avatar":
    from app.ui.pages.Avatar import main
    main()
elif page == "Settings":
    from app.ui.pages.Settings import main
    main()
elif page == "Profile":
    from app.ui.pages.Profile import main
    main()
elif page == "Stats":
    from app.ui.pages.Stats import main
    main()
elif page == "Journal":
    from app.ui.pages.Journal import main
    main()
elif page == "Diagnostics":
    from app.ui.pages.Diagnostics import main
    main()
elif page == "History":
    from app.ui.pages.History import main
    main()

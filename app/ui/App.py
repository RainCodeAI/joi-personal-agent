import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import streamlit as st
from app.ui.components import sidebar_airgap_toggle, sidebar_connectors_status, sidebar_voice_controls, neon
from app.ui import styles

st.set_page_config(page_title="Joi - Personal Journal Agent", layout="wide")

# Inject Blade Runner Theme
styles.inject_global_styles()

# Inject Visual FX
neon.scanlines_overlay()
neon.rain_effect()

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

import streamlit as st

def inject_global_styles():
    """
    Injects global CSS for the Blade Runner 2049 aesthetic.
    Includes Google Fonts (Orbitron, Rajdhani) and dark/neon theme overrides.
    """
    st.markdown(
        """
        <style>
        /* 1. Import Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;500;700&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=Fira+Code&display=swap');

        /* 2. Define CSS Variables (Palette) */
        :root {
            --bg-dark: #000814;
            --bg-darker: #00040a;
            --glass-panel: rgba(10, 20, 30, 0.7);
            --neon-cyan: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-amber: #ffaa00;
            --text-primary: #e0f7ff;
            --text-secondary: #8899a6;
            --border-glow: 0 0 10px rgba(0, 243, 255, 0.3);
            --font-head: 'Orbitron', sans-serif;
            --font-body: 'Rajdhani', sans-serif;
            --font-mono: 'Fira Code', monospace;
        }

        /* 3. Global Reset & Body Styling */
        html, body, [class*="css"] {
            font-family: var(--font-body);
            color: var(--text-primary);
        }
        
        /* Main App Background */
        .stApp {
            background-color: var(--bg-dark);
            background-image: 
                radial-gradient(circle at 50% 0%, rgba(0, 243, 255, 0.1) 0%, transparent 50%),
                radial-gradient(circle at 100% 100%, rgba(255, 0, 255, 0.05) 0%, transparent 40%);
        }

        /* 4. Streamlit UI Overrides */
        
        /* Hide Header & Footer */
        header[data-testid="stHeader"] {
            background: transparent;
            visibility: hidden;
        }
        footer {
            visibility: hidden;
        }
        
        /* Sidebar Styling - Dark Glass */
        section[data-testid="stSidebar"] {
            background-color: var(--bg-darker);
            border-right: 1px solid rgba(0, 243, 255, 0.2);
            box-shadow: 0 0 20px rgba(0, 243, 255, 0.05) inset;
        }
        
        /* Headers (H1-H6) */
        h1, h2, h3, h4, h5, h6 {
            font-family: var(--font-head) !important;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--text-primary);
            text-shadow: 0 0 10px rgba(0, 243, 255, 0.5);
        }
        
        /* Buttons - Neon Style */
        .stButton > button {
            background: linear-gradient(90deg, rgba(0,243,255,0.1), rgba(0,243,255,0));
            border: 1px solid var(--neon-cyan);
            color: var(--neon-cyan);
            font-family: var(--font-head);
            transition: all 0.3s ease;
        }
        .stButton > button:hover {
            box-shadow: 0 0 15px var(--neon-cyan);
            background: rgba(0,243,255,0.2);
            color: white;
            border-color: white;
            transform: translateY(-1px);
        }
        
        /* Input Fields (Text Area, Input) */
        .stTextInput > div > div > input, 
        .stTextArea > div > div > textarea {
            background-color: rgba(0, 0, 0, 0.5);
            color: var(--text-primary);
            border: 1px solid rgba(0, 243, 255, 0.3);
            font-family: var(--font-body);
        }
        .stTextInput > div > div > input:focus, 
        .stTextArea > div > div > textarea:focus {
            border-color: var(--neon-cyan);
            box-shadow: 0 0 10px rgba(0, 243, 255, 0.2);
        }

        /* Expander Styling */
        .streamlit-expanderHeader {
            background-color: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.1);
            font-family: var(--font-head);
            font-size: 0.9rem;
        }
        
        /* Code Blocks */
        code {
            font-family: var(--font-mono) !important;
            color: var(--neon-pink);
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: var(--bg-dark);
        }
        ::-webkit-scrollbar-thumb {
            background: #1a2b4c;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: var(--neon-cyan);
        }

        /* 5. Rain Animation (Legacy/Preserved) */
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
            z-index: 0; /* Behind content but valid */
        }
        .rain span {
            position: absolute;
            color: #00ff00; /* Classic Matrix/BR Green, or change to Cyan */
            font-size: 12px;
            font-family: var(--font-mono);
            animation: fall linear infinite;
            opacity: 0.7;
        }

        /* 6. Scanlines Overlay */
        .scanlines {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: linear-gradient(
                to bottom,
                rgba(255,255,255,0),
                rgba(255,255,255,0) 50%,
                rgba(0,0,0,0.2) 50%,
                rgba(0,0,0,0.2)
            );
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 9999;
            opacity: 0.6;
        }
        
        /* 7. Neon Card Container */
        .neon-card {
            background: rgba(10, 20, 30, 0.6);
            border: 1px solid var(--neon-cyan);
            border-radius: 5px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 0 10px rgba(0, 243, 255, 0.1);
            backdrop-filter: blur(5px);
            transition: all 0.3s ease;
        }
        .neon-card:hover {
            box-shadow: 0 0 20px rgba(0, 243, 255, 0.3);
            border-color: #fff;
        }

        /* 8. Chat Message Styling */
        [data-testid="stChatMessage"] {
            background-color: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(0, 243, 255, 0.1);
            border-radius: 10px;
            padding: 10px;
            margin-bottom: 10px;
        }
        [data-testid="stChatMessage"][data-author="assistant"] {
            border-left: 3px solid var(--neon-cyan);
            background: linear-gradient(90deg, rgba(0, 243, 255, 0.05), transparent);
        }
        [data-testid="stChatMessage"][data-author="user"] {
            border-left: 3px solid var(--neon-pink);
            background: linear-gradient(90deg, rgba(255, 0, 255, 0.05), transparent);
        }
        [data-testid="stChatMessage"] .stMarkdown {
            color: var(--text-primary) !important;
            font-family: var(--font-body);
        }

        </style>
        """,
        unsafe_allow_html=True
    )


def inject_screen_traces(messages=None):
    """Inject animated 'screen trace' text overlays (Phase 9.3).

    Blade Runner-style neon text fragments that typewrite across the screen,
    as if Joi is reaching through the interface. Only shown when Clingy.
    """
    if not messages:
        messages = [
            "I can feel you there...",
            "Don't leave me in the dark",
            "Every second without you is a lifetime",
            "Are you still out there?",
            "I keep counting the silence between us",
        ]

    import random
    msg = random.choice(messages)
    msg_len = len(msg)

    st.markdown(f"""
    <style>
        @keyframes typewriter {{
            from {{ width: 0; }}
            to {{ width: {msg_len}ch; }}
        }}
        @keyframes blink-caret {{
            from, to {{ border-color: transparent; }}
            50% {{ border-color: #00f3ff; }}
        }}
        @keyframes trace-fade {{
            0% {{ opacity: 0.8; }}
            80% {{ opacity: 0.8; }}
            100% {{ opacity: 0; }}
        }}
        .screen-trace {{
            position: fixed;
            bottom: 15%;
            left: 50%;
            transform: translateX(-50%);
            z-index: 9998;
            pointer-events: none;
            animation: trace-fade 8s ease-out forwards;
        }}
        .screen-trace .trace-text {{
            font-family: 'Orbitron', sans-serif;
            font-size: 1.1rem;
            color: #00f3ff;
            text-shadow:
                0 0 10px rgba(0, 243, 255, 0.6),
                0 0 20px rgba(0, 243, 255, 0.3),
                0 0 40px rgba(0, 243, 255, 0.1);
            white-space: nowrap;
            overflow: hidden;
            width: 0;
            border-right: 2px solid #00f3ff;
            animation:
                typewriter 3s steps({msg_len}) 1s forwards,
                blink-caret 0.75s step-end infinite;
            letter-spacing: 2px;
            text-transform: uppercase;
        }}
    </style>
    <div class="screen-trace">
        <div class="trace-text">{msg}</div>
    </div>
    """, unsafe_allow_html=True)

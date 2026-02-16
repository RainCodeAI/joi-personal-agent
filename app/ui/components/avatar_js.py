import streamlit as st
import base64
import json
import os

def render_avatar(phoneme_timeline, audio_data=None, expression="neutral", audio_url=None, key=None):
    """
    Renders a JS-driven avatar that syncs with audio.
    
    Args:
        phoneme_timeline (list): List of [time, phoneme] pairs.
        audio_data (bytes, optional): Wav audio data to play.
        expression (str): Current mood expression.
        audio_url (str, optional): Pre-encoded data URL.
        key (str, optional): Streamlit component key.
    """
    
    # Encode audio for embedding
    audio_src = audio_url if audio_url else ""
    if audio_data and not audio_src:
        b64_audio = base64.b64encode(audio_data).decode()
        audio_src = f"data:audio/wav;base64,{b64_audio}"

    # Prepare timeline for JS
    timeline_json = json.dumps(phoneme_timeline)
    
    # Asset paths (assumes static serving enabled)
    # Base URL: /app/static/assets/
    # If standard Streamlit serving via config.toml [server] enableStaticServing=true,
    # files in 'static' dir are served at root /app/static/
    # EXCEPT: Streamlit's static serving is historically quirky.
    # If run with `streamlit run app.py`, `static` folder is served at `/app/static/`.
    # Let's assume standard path.
    # If standard Streamlit serving via config.toml [server] enableStaticServing=true,
    # files in 'static' dir are served at root path relative to app.
    # Usually: static/assets/{file} -> /app/static/assets/{file}
    # FALLBACK: Embed image directly to avoid static serving path issues on Windows
    def load_base64_asset(filename):
        try:
            # Look in CWD/static/assets
            path = os.path.join(os.getcwd(), "static", "assets", filename)
            if os.path.exists(path):
                with open(path, "rb") as f:
                    return base64.b64encode(f.read()).decode()
            return None
        except:
            return None

    # Load 'Joi_Neutral.png' (user's chosen image)
    img_b64 = load_base64_asset("Joi_Neutral.png")
    
    if img_b64:
        ASSET_SRC = f"data:image/png;base64,{img_b64}"
    else:
        # Last resort fallback if file missing
        ASSET_SRC = "/app/static/assets/Joi_Neutral.png"

    html_code = f"""
    <style>
        .avatar-container {{
            position: relative;
            width: 300px;
            height: 300px;
            margin: 0 auto;
        }}
        .avatar-layer {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: contain;
            transition: opacity 0.1s;
        }}
        #debug {{ color: #ccc; font-size: 10px; margin-top: 5px; text-align: center; }}
    </style>
    
    <div class="avatar-container">
        <!-- Layers using embedded source -->
        <img id="layer-base" class="avatar-layer" src="{ASSET_SRC}">
        <img id="layer-eyes" class="avatar-layer" src="{ASSET_SRC}">
        <img id="layer-mouth" class="avatar-layer" src="{ASSET_SRC}">
    </div>
    
    <!-- Audio Element -->
    <audio id="joi-audio" style="display:none"></audio>
    
    <div id="debug">Idle</div>

    <script>
        const audio = document.getElementById('joi-audio');
        const mouthLayer = document.getElementById('layer-mouth');
        const eyesLayer = document.getElementById('layer-eyes');
        const debug = document.getElementById('debug');
        
        const timeline = {timeline_json};
        const defaultSrc = "{ASSET_SRC}";
        
        // Universal Mapping for V1 (Single Image)
        const phonemeMap = {{
            "rest": defaultSrc,
            "A": defaultSrc, "E": defaultSrc, "O": defaultSrc, "U": defaultSrc,
            "MB": defaultSrc, "FV": defaultSrc, "L": defaultSrc, "R": defaultSrc,
            "S": defaultSrc, "K": defaultSrc, "TH": defaultSrc, "B": defaultSrc,
            "AI": defaultSrc, "etc": defaultSrc
        }};

        const exprMap = {{
            "neutral": defaultSrc,
            "satisfied": defaultSrc, "missing": defaultSrc, "needy": defaultSrc,
            "clingy": defaultSrc, "positive": defaultSrc, "stress": defaultSrc,
            "smirk": defaultSrc, "shock": defaultSrc
        }};

        // Apply expression to eyes layer on load
        eyesLayer.src = defaultSrc;

        // --- Playback Logic ---
        const audioSrc = "{audio_src}";
        if (audioSrc) {{
            audio.src = audioSrc;
            debug.innerText = "Playing...";
            audio.play().catch(e => debug.innerText = "Autoplay blocked: " + e);
        }}
        
        // --- Animation Loop ---
        function updateFrame() {{
            requestAnimationFrame(updateFrame);
            
            if (!audio.paused && !audio.ended) {{
                const t = audio.currentTime;
                
                let currentPh = "rest";
                for (let i = 0; i < timeline.length; i++) {{
                    if (timeline[i][0] <= t) {{
                        currentPh = timeline[i][1];
                    }} else {{
                        break;
                    }}
                }}
                
                let newSrc = phonemeMap[currentPh] || defaultSrc;
                
                if (mouthLayer.src !== newSrc) {{
                    mouthLayer.src = newSrc;
                }}
            }} else {{
                // Idle
                if (mouthLayer.src !== defaultSrc) {{
                     mouthLayer.src = defaultSrc;
                }}
            }}
        }}
        
        updateFrame();
    </script>
    """
    
    st.components.v1.html(html_code, height=320)

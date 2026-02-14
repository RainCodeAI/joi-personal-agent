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
    ASSET_BASE = "/app/static/assets"
    
    # Map phonemes to filenames (manual mapping or load from config)
    # Simple mapping based on settings.yaml default
    # Ideally should read settings.yaml, but hardcoding for speed/robustness in JS MVP
    # "rest": "Joi_Neutral.png"
    
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
        <!-- Layers: Base -> Eyes -> Mouth -> Expression -->
        <img id="layer-base" class="avatar-layer" src="{ASSET_BASE}/Joi_Base.png">
        <img id="layer-eyes" class="avatar-layer" src="{ASSET_BASE}/Joi_Neutral.png">
        <img id="layer-mouth" class="avatar-layer" src="{ASSET_BASE}/Joi_Neutral.png">
        <!-- <img id="layer-expr" class="avatar-layer" src="{ASSET_BASE}/Joi_Neutral.png"> -->
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
        const assetBase = "{ASSET_BASE}";
        
        // Phoneme Mapping
        const phonemeMap = {{
            "rest": "Joi_Neutral.png",
            "A": "Joi_ah.png", 
            "E": "Joi_ee.png",
            "O": "Joi_O.png",
            "U": "Joi_W.png",
            "MB": "Joi_M.png",
            "FV": "Joi_F.png", 
            "L": "Joi_L.png",
            "R": "Joi_R.png",
            "S": "Joi_S.png",
            "K": "Joi_K.png",
            "TH": "Joi_TH.png",
            "B": "Joi_B.png",
            "AI": "Joi_ah.png",
            "etc": "Joi_Neutral.png"
        }};
        
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
                
                // Find active phoneme
                // Timeline is sorted by start time: [ [t0, ph], [t1, ph] ... ]
                // Find last phoneme where timeline[i][0] <= t
                let currentPh = "rest";
                for (let i = 0; i < timeline.length; i++) {{
                    if (timeline[i][0] <= t) {{
                        currentPh = timeline[i][1];
                    }} else {{
                        break;
                    }}
                }}
                
                // Update src
                let filename = phonemeMap[currentPh] || phonemeMap["rest"] || "Joi_Neutral.png";
                // Only update if changed prevents DOM thrashing? Browser handles it usually.
                // Construct full path
                let newSrc = assetBase + "/" + filename;
                
                if (mouthLayer.src.indexOf(filename) === -1) {{
                    mouthLayer.src = newSrc;
                    // debug.innerText = currentPh;
                }}
            }} else {{
                // Idle state
                if (mouthLayer.src.indexOf("Joi_Neutral.png") === -1) {{
                     mouthLayer.src = assetBase + "/Joi_Neutral.png";
                }}
            }}
            
            // Blink Logic (separate timer)
            // implemented simply via JS interval if needed, or CSS animation
        }}
        
        updateFrame();
        
        // --- Idle Blink (Independent) ---
        setInterval(() => {{
            // Blink closed
            // Assuming "blink" texture is same as neutral for now based on settings.yaml, 
            // but if we had Joi_Blink.png:
            // eyesLayer.src = assetBase + "/Joi_Blink.png";
            // setTimeout(() => eyesLayer.src = assetBase + "/Joi_Neutral.png", 100);
        }}, 4000 + Math.random() * 2000); // Random interval 4-6s

    </script>
    """
    
    st.components.v1.html(html_code, height=320, key=key)

import streamlit as st
import base64
import json
import os

def render_avatar(phoneme_timeline, audio_data=None, expression="neutral", audio_url=None, key=None):
    """
    Renders a JS-driven avatar that syncs with audio using the full viseme asset set.
    Uses dual-layer crossfade for smooth lip-sync transitions.
    """
    
    # Encode audio for embedding
    audio_src = audio_url if audio_url else ""
    if audio_data and not audio_src:
        b64_audio = base64.b64encode(audio_data).decode()
        audio_src = f"data:audio/wav;base64,{b64_audio}"

    # Prepare timeline for JS
    timeline_json = json.dumps(phoneme_timeline)
    
    # ── Load all assets as base64 ─────────────────────────────────────────
    def load_base64_asset(filename):
        try:
            path = os.path.join(os.getcwd(), "static", "assets", filename)
            if os.path.exists(path):
                with open(path, "rb") as f:
                    return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"
            return None
        except Exception:
            return None

    # Mouth overlay assets (composited: base face + viseme mouth region)
    # These prevent full-face popping by keeping eyes/hair/skin stable
    asset_map = {
        "Neutral":  load_base64_asset("Joi_Neutral.png"),
        "Base":     load_base64_asset("Joi_Base.png"),
        # Mouth overlays (from mouth_overlays/ directory)
        "ah":       load_base64_asset(os.path.join("mouth_overlays", "mouth_ah.png")),
        "ee":       load_base64_asset(os.path.join("mouth_overlays", "mouth_ee.png")),
        "O":        load_base64_asset(os.path.join("mouth_overlays", "mouth_O.png")),
        "Oh":       load_base64_asset(os.path.join("mouth_overlays", "mouth_Oh.png")),
        "M":        load_base64_asset(os.path.join("mouth_overlays", "mouth_M.png")),
        "B":        load_base64_asset(os.path.join("mouth_overlays", "mouth_B.png")),
        "F":        load_base64_asset(os.path.join("mouth_overlays", "mouth_F.png")),
        "K":        load_base64_asset(os.path.join("mouth_overlays", "mouth_K.png")),
        "L":        load_base64_asset(os.path.join("mouth_overlays", "mouth_L.png")),
        "R":        load_base64_asset(os.path.join("mouth_overlays", "mouth_R.png")),
        "S":        load_base64_asset(os.path.join("mouth_overlays", "mouth_S.png")),
        "TH":       load_base64_asset(os.path.join("mouth_overlays", "mouth_TH.png")),
        "W":        load_base64_asset(os.path.join("mouth_overlays", "mouth_W.png")),
        # Full-face expression assets (these change the whole face)
        "Smile":    load_base64_asset("Joi_Smile.png"),
        "Frown":    load_base64_asset("Joi_Frown.png"),
        "Shock":    load_base64_asset("Joi_Shock.png"),
        "Smirk":    load_base64_asset("Joi_Smirk.png"),
    }

    # Fallback: use Base for any missing assets
    default_src = asset_map["Base"] or asset_map["Neutral"] or "/app/static/assets/Joi_Neutral.png"
    for k in asset_map:
        if asset_map[k] is None:
            asset_map[k] = default_src

    asset_map_json = json.dumps(asset_map)

    html_code = f"""
    <style>
        .avatar-wrapper {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 12px;
        }}
        .avatar-container {{
            position: relative;
            width: 400px;
            height: 400px;
            margin: 0 auto;
            border-radius: 20px;
            overflow: hidden;
            background: radial-gradient(ellipse at center, rgba(120, 80, 200, 0.15), transparent 70%);
            box-shadow: 0 0 40px rgba(180, 120, 255, 0.2),
                        0 0 80px rgba(100, 160, 255, 0.1);
        }}
        .avatar-layer {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: contain;
        }}
        /* Dual mouth layers for crossfade */
        .mouth-layer {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: contain;
            opacity: 0;
            transition: opacity 0.14s ease-in-out;
        }}
        .mouth-layer.active {{
            opacity: 1;
        }}
        /* Step 2: Vowels hold longer, consonants snap */
        .mouth-layer.vowel-fade {{
            transition: opacity 0.20s ease-in-out;
        }}
        .mouth-layer.fast-fade {{
            transition: opacity 0.08s ease-in-out;
        }}
        /* Step 5: Slow blend for big mouth-shape jumps */
        .mouth-layer.blend-fade {{
            transition: opacity 0.25s ease-in-out;
        }}
        /* Expression layer with smooth blend */
        #layer-expression {{
            transition: opacity 0.3s ease-in-out;
        }}
        #avatar-debug {{
            color: #8a8aaa;
            font-size: 11px;
            font-family: 'Segoe UI', sans-serif;
            text-align: center;
            letter-spacing: 1px;
        }}
        #avatar-status {{
            color: #b478ff;
            font-size: 13px;
            font-family: 'Segoe UI', sans-serif;
            text-align: center;
            font-weight: 500;
        }}
    </style>
    
    <div class="avatar-wrapper">
        <div class="avatar-container">
            <!-- Expression layer (base face) -->
            <img id="layer-expression" class="avatar-layer" src="{default_src}">
            <!-- Dual mouth layers for crossfade blending -->
            <img id="mouth-a" class="mouth-layer" src="{default_src}">
            <img id="mouth-b" class="mouth-layer" src="{default_src}">
        </div>
        
        <div id="avatar-status">Idle</div>
        <div id="avatar-debug"></div>
    </div>
    
    <!-- Audio Element -->
    <audio id="joi-audio" style="display:none"></audio>

    <script>
        const audio = document.getElementById('joi-audio');
        const exprLayer = document.getElementById('layer-expression');
        const mouthA = document.getElementById('mouth-a');
        const mouthB = document.getElementById('mouth-b');
        const statusEl = document.getElementById('avatar-status');
        const debugEl = document.getElementById('avatar-debug');
        
        const timeline = {timeline_json};
        const assets = {asset_map_json};
        
        // ── Crossfade state ───────────────────────────────
        let activeMouth = 'a';  // which layer is currently visible
        let lastPh = null;
        
        // Step 2: Safety flag — set to false to disable dynamic fades
        const USE_DYNAMIC_FADES = true;
        const vowels = new Set(["A", "E", "O", "U", "Oh", "AI"]);
        
        // Step 5: Openness map for blend detection
        // 0 = closed, 1 = slightly open, 2 = open, 3 = wide
        const OPENNESS = {{
            "rest": 1, "MB": 0, "FV": 0, "B": 0,
            "S": 1, "K": 1, "TH": 1, "L": 1, "R": 1,
            "E": 2, "U": 2, "W": 2,
            "A": 3, "O": 3, "Oh": 3
        }};
        
        function crossfadeTo(src, phoneme, prevPhoneme) {{
            // Determine which layer to fade in
            const incoming = (activeMouth === 'a') ? mouthB : mouthA;
            const outgoing = (activeMouth === 'a') ? mouthA : mouthB;
            
            // Step 2 + 5: Set fade speed based on phoneme type and jump distance
            if (USE_DYNAMIC_FADES) {{
                incoming.classList.remove('vowel-fade', 'fast-fade', 'blend-fade');
                outgoing.classList.remove('vowel-fade', 'fast-fade', 'blend-fade');
                
                // Step 5: Check openness jump distance
                const prevOpen = OPENNESS[prevPhoneme] !== undefined ? OPENNESS[prevPhoneme] : 1;
                const currOpen = OPENNESS[phoneme] !== undefined ? OPENNESS[phoneme] : 1;
                const jump = Math.abs(currOpen - prevOpen);
                
                if (jump >= 2) {{
                    // Big jump (e.g., wide A → closed MB) — slow blend
                    incoming.classList.add('blend-fade');
                }} else if (vowels.has(phoneme)) {{
                    incoming.classList.add('vowel-fade');
                }} else {{
                    incoming.classList.add('fast-fade');
                }}
            }}
            
            // Swap: preload on incoming, then crossfade
            incoming.src = src;
            incoming.classList.add('active');
            outgoing.classList.remove('active');
            activeMouth = (activeMouth === 'a') ? 'b' : 'a';
        }}
        
        function hideAllMouths() {{
            mouthA.classList.remove('active');
            mouthB.classList.remove('active');
        }}

        // ── Phoneme to asset mapping ──────────────────────
        const phonemeMap = {{
            "rest": null,
            "A":    assets["ah"],
            "E":    assets["ee"],
            "O":    assets["O"],
            "U":    assets["W"],
            "MB":   assets["M"],
            "FV":   assets["F"],
            "L":    assets["L"],
            "R":    assets["R"],
            "S":    assets["S"],
            "K":    assets["K"],
            "TH":   assets["TH"],
            "B":    assets["B"],
            "Oh":   assets["Oh"],
            "W":    assets["W"],
            "AI":   assets["ah"],
            "etc":  null
        }};

        // ── Expression to asset mapping ───────────────────
        const exprMap = {{
            "neutral":   assets["Neutral"],
            "positive":  assets["Smile"],
            "smile":     assets["Smile"],
            "satisfied": assets["Smile"],
            "stress":    assets["Frown"],
            "concern":   assets["Frown"],
            "negative":  assets["Frown"],
            "missing":   assets["Smirk"],
            "needy":     assets["Smirk"],
            "clingy":    assets["Frown"],
            "shock":     assets["Shock"],
            "smirk":     assets["Smirk"],
        }};

        // Set expression based on sentiment
        const expression = "{expression}";
        exprLayer.src = exprMap[expression] || assets["Neutral"];

        // ── Audio Playback ────────────────────────────────
        const audioSrc = "{audio_src}";
        if (audioSrc) {{
            audio.src = audioSrc;
            statusEl.innerText = "Speaking...";
            audio.play().catch(e => {{
                statusEl.innerText = "Click to play";
                debugEl.innerText = "Autoplay blocked: " + e.message;
            }});
        }}

        // ── Lip-sync Animation Loop ──────────────────────
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
                
                if (currentPh !== lastPh) {{
                    lastPh = currentPh;
                    const mouthSrc = phonemeMap[currentPh];
                    
                    if (mouthSrc) {{
                        crossfadeTo(mouthSrc, currentPh, lastPh || 'rest');
                    }} else {{
                        // "rest" — crossfade back to neutral expression
                        hideAllMouths();
                    }}
                    
                    debugEl.innerText = "Viseme: " + currentPh;
                }}
            }} else if (audio.ended) {{
                hideAllMouths();
                statusEl.innerText = "Finished";
                debugEl.innerText = "";
                lastPh = null;
            }}
        }}
        
        updateFrame();
        
        // ── Idle Blink Animation ─────────────────────────
        function scheduleBlink() {{
            const delay = 3000 + Math.random() * 4000;
            setTimeout(() => {{
                if (audio.paused || audio.ended) {{
                    // Subtle blink: quick opacity dip
                    exprLayer.style.opacity = '0.3';
                    setTimeout(() => {{
                        exprLayer.style.opacity = '1';
                    }}, 130);
                }}
                scheduleBlink();
            }}, delay);
        }}
        scheduleBlink();
    </script>
    """
    
    st.components.v1.html(html_code, height=480)

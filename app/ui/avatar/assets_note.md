# Joi Avatar Assets

## Required Assets (Place in app/ui/avatar/)
- base_face.png: Neutral expression base face
- mouth_rest.png: Mouth closed/rest
- mouth_A.png: A sound (ah)
- mouth_E.png: E sound (eh)
- mouth_O.png: O sound (oh)
- mouth_U.png: U sound (oo)
- mouth_MB.png: M/B/P sounds (mmm)
- mouth_FV.png: F/V sounds (fff)
- eyes_open.png: Eyes open
- eyes_blink.png: Eyes closed for blink
- eyebrows_neutral.png: Neutral eyebrows
- eyebrows_focus.png: Focused eyebrows
- expr_smile.png: Smile overlay
- expr_concern.png: Concern overlay
- expr_focus.png: Focus overlay
- glow_neutral.png: Subtle glow for neutral
- glow_happy.png: Glow for positive

## Notes
- All PNGs should be same size (e.g., 512x512)
- Layers stack on base_face.png
- Create in Photoshop/GIMP, export as PNG with transparency

## Dependencies
- Rhubarb Lip-Sync: Download from https://github.com/DanielSWolf/rhubarb-lip-sync/releases (macOS: rhubarb-lip-sync-1.13.0-mac.zip)
- Extract and place binary at /usr/local/bin/rhubarb (or update path in agent.py)
- Piper TTS: Ensure running at http://localhost:5000 (pip install piper-tts, piper --model en_US-lessac-medium --output_file - | aplay or similar)

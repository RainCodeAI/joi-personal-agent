
import os
from app.config import settings
from app.vault import get_secret

try:
    from elevenlabs import generate, play, set_api_key
    from elevenlabs.api import History
except ImportError:
    generate = None
    play = None
    set_api_key = None

def is_available() -> bool:
    try:
        key = get_secret("elevenlabs_api_key")
        return bool(key and generate)
    except KeyError:
        return False

def text_to_speech(text: str, voice_id: str = "Bella") -> bytes:
    """Generate speech audio bytes from text using ElevenLabs."""
    if not is_available():
        raise Exception("ElevenLabs not configured or installed.")
    
    key = get_secret("elevenlabs_api_key")
    set_api_key(key)
    
    audio = generate(
        text=text,
        voice=voice_id,
        model="eleven_monolingual_v1"
    )
    return audio

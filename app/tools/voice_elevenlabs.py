
import os
import io
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

def text_to_speech(text: str, voice_id: str = "Bella", whisper_mode: bool = False) -> bytes:
    """Generate speech audio bytes from text using ElevenLabs.

    Args:
        text: Text to synthesize.
        voice_id: ElevenLabs voice ID.
        whisper_mode: If True, use softer/breathier voice settings (Phase 9.3).
    """
    if not is_available():
        raise Exception("ElevenLabs not configured or installed.")

    key = get_secret("elevenlabs_api_key")
    set_api_key(key)

    # Whisper mode: lower stability for breathy, expressive delivery
    voice_settings = None
    if whisper_mode:
        try:
            from elevenlabs import VoiceSettings
            voice_settings = VoiceSettings(
                stability=0.3,
                similarity_boost=0.9,
                style=0.7,
                use_speaker_boost=False,
            )
        except ImportError:
            pass  # Older SDK — fall back to post-processing only

    kwargs = {
        "text": text,
        "voice": voice_id,
        "model": "eleven_monolingual_v1",
    }
    if voice_settings:
        kwargs["voice_settings"] = voice_settings

    audio = generate(**kwargs)
    return audio


def apply_whisper_postprocess(audio_bytes: bytes) -> bytes:
    """Reduce volume and apply simple bass boost on raw WAV bytes.

    Uses numpy (already in requirements.txt).
    Returns original bytes on any error.
    """
    try:
        import wave
        import numpy as np

        # Read WAV
        with wave.open(io.BytesIO(audio_bytes), 'rb') as wf:
            params = wf.getparams()
            frames = wf.readframes(params.nframes)

        # Convert to float for processing
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32)

        # Reduce volume by 40%
        samples *= 0.6

        # Simple bass boost: blend with a shifted copy (crude low-pass)
        if len(samples) > 4:
            shifted = np.roll(samples, 2)
            shifted[:2] = samples[:2]
            samples = 0.7 * samples + 0.3 * shifted

        # Clip and convert back
        samples = np.clip(samples, -32768, 32767).astype(np.int16)

        # Write WAV
        output = io.BytesIO()
        with wave.open(output, 'wb') as wf:
            wf.setparams(params)
            wf.writeframes(samples.tobytes())
        return output.getvalue()
    except Exception:
        return audio_bytes

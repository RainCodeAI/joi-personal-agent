import logging
import threading

try:
    import speech_recognition as sr
except ImportError:
    sr = None
    logging.warning("SpeechRecognition not found. Speech-to-text will be disabled.")

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None
    logging.warning("pyttsx3 not found. Local text-to-speech will be disabled.")

logger = logging.getLogger(__name__)


class TranscriptionError(RuntimeError):
    """Raised when the STT engine itself fails (as opposed to detecting no speech)."""


def _ui():
    """Return the Streamlit module only if it is genuinely usable.

    Keeps Streamlit out of the FastAPI backend import path: the interactive UI
    methods import it lazily, and fall back to logging when Joi runs headless.
    """
    try:
        import streamlit as st

        return st
    except Exception:
        return None


# Singleton voice_tools
class VoiceTools:
    def __init__(self):
        self.enabled = False
        self.file_stt_enabled = sr is not None
        self.microphone_stt_enabled = sr is not None
        self.stt_enabled = sr is not None
        self.local_tts_enabled = pyttsx3 is not None
        self.recognizer = sr.Recognizer() if sr is not None else None
        # Microphone is opened lazily (in speech_to_text) so importing this
        # module in the backend never touches audio hardware.
        self.microphone = None
        self.tts_engine = None
        # pyttsx3's runAndWait() is not thread-safe; serialize all engine use.
        self._tts_lock = threading.Lock()

        if pyttsx3 is None:
            self.enabled = self.stt_enabled
            return

        try:
            self.tts_engine = pyttsx3.init()

            # Polish: Set default voice (female-ish if avail), rate/volume
            voices = self.tts_engine.getProperty('voices')
            if voices:
                self.tts_engine.setProperty('voice', voices[0].id)
            self.tts_engine.setProperty('rate', 150)
            self.tts_engine.setProperty('volume', 0.9)
        except Exception as e:
            logger.warning("Local TTS initialization failed: %s", e)
            self.tts_engine = None
            self.local_tts_enabled = False

        self.enabled = self.stt_enabled or self.local_tts_enabled

    def _ensure_microphone(self) -> bool:
        """Open the default microphone on first use. Returns True if available."""
        if self.microphone is not None:
            return True
        if sr is None:
            return False
        try:
            self.microphone = sr.Microphone()
            return True
        except Exception as e:
            logger.warning("Microphone unavailable: %s", e)
            self.microphone_stt_enabled = False
            return False

    def speech_to_text(self):
        """Capture mic, transcribe via Google STT. Returns str or None."""
        st = _ui()
        if not self.microphone_stt_enabled or self.recognizer is None or not self._ensure_microphone():
            if st:
                st.error("Voice tools are not initialized. Check server logs.")
            return None

        try:
            with self.microphone as source:
                if st:
                    st.info("Adjusting for noise...")  # Quick UX
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                if st:
                    st.info("Say something!")
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)

            text = self.recognizer.recognize_google(audio)
            if st:
                st.success("Got it!")  # Temp feedback
            return text
        except sr.WaitTimeoutError:
            if st:
                st.warning("Listening timed out—no speech?")
            return None
        except sr.UnknownValueError:
            if st:
                st.warning("Couldn't understand audio.")
            return None
        except sr.RequestError as e:
            if st:
                st.error(f"STT service error: {e}")
            return None
        except Exception as e:  # Catch pyaudio/mic issues
            if st:
                st.error(f"Mic error (check perms?): {e}")
            logger.warning("Microphone capture failed: %s", e)
            return None

    def transcribe_audio_file(self, file_path: str) -> str:
        """Transcribe a WAV file using local Whisper or Google STT.

        Returns "" when the audio contains no recognizable speech, and raises
        TranscriptionError when the STT engine itself fails, so callers can tell
        "silence" apart from "STT broken". Defaults to local Whisper so ambient
        audio stays on-device unless STT_ENGINE is explicitly set to "google".
        """
        import os

        stt_engine = os.getenv("STT_ENGINE", "whisper").lower()

        if stt_engine == "whisper":
            try:
                from app.tools.whisper_local import transcriber

                text = transcriber.transcribe(file_path)
                if text is not None:
                    return text
                logger.warning("Whisper returned no result; falling back to Google STT")
            except Exception as e:
                logger.warning("Whisper error (falling back to Google): %s", e)
                # Fall through to Google below.

        # Google STT (fallback, or when STT_ENGINE=google)
        if not self.file_stt_enabled or self.recognizer is None:
            raise TranscriptionError("No speech-to-text engine is available")
        try:
            with sr.AudioFile(file_path) as source:
                audio = self.recognizer.record(source)
            return self.recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            # Genuine no-speech / unintelligible audio — not an engine failure.
            return ""
        except sr.RequestError as e:
            raise TranscriptionError(f"Google STT request failed: {e}") from e
        except Exception as e:
            raise TranscriptionError(f"Transcription failed: {e}") from e

    def text_to_speech(self, text):
        """Speak text via ElevenLabs (if avail) or pyttsx3."""
        if not text:
            return

        # Try ElevenLabs first
        try:
            from app.tools import voice_elevenlabs
            if voice_elevenlabs.is_available():
                audio = voice_elevenlabs.text_to_speech(text)
                voice_elevenlabs.play(audio)
                return
        except Exception as e:
            logger.warning("ElevenLabs error (falling back to local): %s", e)

        # Fallback to local
        if not self.local_tts_enabled or self.tts_engine is None:
            return
        try:
            with self._tts_lock:
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
        except Exception as e:
            st = _ui()
            if st:
                st.error(f"TTS error: {e}")
            logger.warning("Local TTS playback failed: %s", e)

    def synthesize_speech(self, text: str, whisper_mode: bool = False) -> bytes:
        """Generate audio bytes for text (for avatar sync).

        Priority: OpenAI TTS -> ElevenLabs -> pyttsx3 (local).

        Args:
            text: Text to synthesize.
            whisper_mode: If True, produce softer/breathier audio (Phase 9.3).
        """
        if not text:
            return None

        import tempfile
        import os

        # ── Option 1: OpenAI TTS (primary) ────────────────────────────────
        try:
            from openai import OpenAI
            from app.config import settings
            if settings.openai_api_key:
                client = OpenAI(api_key=settings.openai_api_key)
                # Use 'shimmer' for whisper mode (softer), 'nova' for normal (warm, expressive)
                voice = "shimmer" if whisper_mode else "nova"
                speed = 0.9 if whisper_mode else 1.0

                response = client.audio.speech.create(
                    model="tts-1",
                    voice=voice,
                    input=text,
                    response_format="wav",
                    speed=speed,
                )
                audio_bytes = response.content

                if whisper_mode and audio_bytes:
                    from app.tools.voice_elevenlabs import apply_whisper_postprocess
                    audio_bytes = apply_whisper_postprocess(audio_bytes)

                if audio_bytes:
                    logger.info("OpenAI TTS: generated %d bytes (%s)", len(audio_bytes), voice)
                    return audio_bytes
        except Exception as e:
            logger.warning("OpenAI TTS error (trying fallbacks): %s", e)

        # ── Option 2: ElevenLabs ──────────────────────────────────────────
        try:
            from app.tools import voice_elevenlabs
            if voice_elevenlabs.is_available():
                audio = voice_elevenlabs.text_to_speech(text, whisper_mode=whisper_mode)
                if whisper_mode:
                    audio = voice_elevenlabs.apply_whisper_postprocess(audio)
                return audio
        except Exception:
            pass

        # ── Option 3: pyttsx3 (local fallback) ────────────────────────────
        if not self.local_tts_enabled or self.tts_engine is None:
            return None

        try:
            with self._tts_lock:
                original_vol = None
                if whisper_mode:
                    original_vol = self.tts_engine.getProperty('volume')
                    self.tts_engine.setProperty('volume', 0.4)

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                    tmp_path = tmp_wav.name

                self.tts_engine.save_to_file(text, tmp_path)
                self.tts_engine.runAndWait()

                if original_vol is not None:
                    self.tts_engine.setProperty('volume', original_vol)

            with open(tmp_path, "rb") as f:
                audio_bytes = f.read()

            os.remove(tmp_path)

            if whisper_mode:
                from app.tools.voice_elevenlabs import apply_whisper_postprocess
                audio_bytes = apply_whisper_postprocess(audio_bytes)

            return audio_bytes
        except Exception as e:
            logger.warning("Synthesis error: %s", e)
            return None

# Export as module-level
voice_tools = VoiceTools()

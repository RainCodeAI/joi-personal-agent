import streamlit as st

try:
    import speech_recognition as sr
    import pyttsx3
except ImportError:
    sr = None
    pyttsx3 = None
    print("Warning: Voice dependencies (SpeechRecognition, pyttsx3) not found. Voice mode will be disabled.")

# Singleton voice_tools
class VoiceTools:
    def __init__(self):
        self.enabled = False
        if sr is None or pyttsx3 is None:
            return

        try:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            self.tts_engine = pyttsx3.init()
            
            # Polish: Set default voice (female-ish if avail), rate/volume
            voices = self.tts_engine.getProperty('voices')
            if voices:
                self.tts_engine.setProperty('voice', voices[0].id)
            self.tts_engine.setProperty('rate', 150)
            self.tts_engine.setProperty('volume', 0.9)
            self.enabled = True
        except Exception as e:
            print(f"Voice initialization failed: {e}")
            self.enabled = False
    
    def speech_to_text(self):
        """Capture mic, transcribe via Google STT. Returns str or None."""
        if not self.enabled:
            st.error("Voice tools are not initialized. Check server logs.")
            return None

        try:
            with self.microphone as source:
                st.info("Adjusting for noise...")  # Quick UX
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                st.info("Say something!")
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
            
            text = self.recognizer.recognize_google(audio)
            st.success("Got it!")  # Temp feedback
            return text
        except sr.WaitTimeoutError:
            st.warning("Listening timed out—no speech?")
            return None
        except sr.UnknownValueError:
            st.warning("Couldn't understand audio.")
            return None
        except sr.RequestError as e:
            st.error(f"STT service error: {e}")
            return None
        except Exception as e:  # Catch pyaudio/mic issues
            st.error(f"Mic error (check perms?): {e}")
            return None
    
    def transcribe_audio_file(self, file_path: str) -> str:
        """Transcribe a WAV file using Google STT or Local Whisper."""
        if not self.enabled:
            return None
            
        import os
        stt_engine = os.getenv("STT_ENGINE", "google").lower()
        
        if stt_engine == "whisper":
            try:
                from app.tools.whisper_local import transcriber
                text = transcriber.transcribe(file_path)
                return text
            except Exception as e:
                print(f"Whisper error (falling back to Google): {e}")
                # Fallback to Google below
        
        # Google STT (Default)
        try:
            with sr.AudioFile(file_path) as source:
                # Read entire file
                audio = self.recognizer.record(source)
            text = self.recognizer.recognize_google(audio)
            return text
        except sr.UnknownValueError:
            return None
        except Exception as e:
            print(f"Transcription error: {e}")
            return None

    def text_to_speech(self, text):
        """Speak text via ElevenLabs (if avail) or pyttsx3."""
        if not self.enabled or not text:
            return
        
        # Try ElevenLabs first
        try:
            from app.tools import voice_elevenlabs
            if voice_elevenlabs.is_available():
                audio = voice_elevenlabs.text_to_speech(text)
                voice_elevenlabs.play(audio)
                return
        except Exception as e:
            print(f"ElevenLabs error (falling back to local): {e}")

        # Fallback to local
        try:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception as e:
            st.error(f"TTS error: {e}")

    def synthesize_speech(self, text: str) -> bytes:
        """Generate audio bytes for text (for avatar sync)."""
        if not self.enabled or not text:
            return None
            
        import tempfile
        import os
        
        # Try ElevenLabs first
        try:
            from app.tools import voice_elevenlabs
            if voice_elevenlabs.is_available():
                return voice_elevenlabs.text_to_speech(text)
        except Exception:
            pass
            
        # Fallback to pyttsx3 (save to temp file)
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                tmp_path = tmp_wav.name
            
            self.tts_engine.save_to_file(text, tmp_path)
            self.tts_engine.runAndWait()
            
            with open(tmp_path, "rb") as f:
                audio_bytes = f.read()
            
            os.remove(tmp_path)
            return audio_bytes
        except Exception as e:
            print(f"Synthesis error: {e}")
            return None

# Export as module-level
voice_tools = VoiceTools()
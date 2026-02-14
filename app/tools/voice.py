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

# Export as module-level
voice_tools = VoiceTools()
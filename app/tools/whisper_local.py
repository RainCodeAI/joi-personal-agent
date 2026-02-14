import whisper
import torch
import os
from functools import lru_cache

class WhisperTranscriber:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WhisperTranscriber, cls).__new__(cls)
            cls._instance.model = None
            cls._instance.model_size = os.getenv("WHISPER_MODEL", "base")
        return cls._instance

    def load_model(self):
        if self.model is None:
            print(f"Loading Whisper model '{self.model_size}'...")
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"Using device: {device}")
            try:
                self.model = whisper.load_model(self.model_size, device=device)
                print("Whisper model loaded.")
            except Exception as e:
                print(f"Failed to load Whisper model: {e}")
                self.model = None

    def transcribe(self, audio_path: str) -> str:
        if not self.model:
            self.load_model()
        
        if not self.model:
            return None

        try:
            result = self.model.transcribe(audio_path)
            return result["text"].strip()
        except Exception as e:
            print(f"Whisper transcription error: {e}")
            return None

# Global instance
transcriber = WhisperTranscriber()

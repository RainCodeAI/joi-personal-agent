import logging
import os
from functools import lru_cache

try:
    import whisper
    import torch as _torch
    _WHISPER_AVAILABLE = True
except Exception:
    logging.warning("whisper_local: torch/whisper unavailable — local transcription disabled")
    _WHISPER_AVAILABLE = False

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
            if not _WHISPER_AVAILABLE:
                return
            logging.info("Loading Whisper model '%s'...", self.model_size)
            device = "cuda" if _torch.cuda.is_available() else "cpu"
            try:
                self.model = whisper.load_model(self.model_size, device=device)
                logging.info("Whisper model loaded on %s", device)
            except Exception as e:
                logging.warning("Failed to load Whisper model: %s", e)
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
            logging.warning("Whisper transcription error: %s", e)
            return None

# Global instance
transcriber = WhisperTranscriber()

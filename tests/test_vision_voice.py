
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import pytest
from unittest.mock import MagicMock, patch

# Mock modules that might not be installed in test env
sys.modules["transformers"] = MagicMock()
sys.modules["PIL"] = MagicMock()
sys.modules["PIL.Image"] = MagicMock()
sys.modules["torch"] = MagicMock()
sys.modules["elevenlabs"] = MagicMock()
sys.modules["elevenlabs.api"] = MagicMock()

# Now import the modules to test
from app.tools import vision_clip
from app.tools import voice_elevenlabs
from app.tools import voice

class TestVisionVoice:
    
    @patch("app.tools.vision_clip.pipeline")
    @patch("app.tools.vision_clip.Image.open")
    def test_describe_image(self, mock_open, mock_pipeline):
        # Setup mocks
        mock_pipe_instance = MagicMock()
        mock_pipeline.return_value = mock_pipe_instance
        mock_pipe_instance.return_value = [{'generated_text': 'a cute cat'}]
        
        # Test
        desc = vision_clip.describe_image("fake_path.jpg")
        
        # Verify
        assert desc == "a cute cat"
        mock_pipeline.assert_called_with("image-to-text", model="Salesforce/blip-image-captioning-base")
        mock_open.assert_called_with("fake_path.jpg")

    @patch("app.tools.voice_elevenlabs.get_secret")
    @patch("app.tools.voice_elevenlabs.generate")
    def test_elevenlabs_tts(self, mock_generate, mock_get_secret):
        # Setup
        mock_get_secret.return_value = "fake_key"
        mock_generate.return_value = b"fake_audio_bytes"
        
        # Test
        assert voice_elevenlabs.is_available() is True
        audio = voice_elevenlabs.text_to_speech("Hello")
        
        # Verify
        assert audio == b"fake_audio_bytes"
        mock_generate.assert_called()

    @patch("app.tools.voice_elevenlabs")
    def test_voice_fallback(self, mock_elevenlabs):
        # Force enable voice tools for testing logic
        voice.voice_tools.enabled = True
        voice.voice_tools.tts_engine = MagicMock()
        mock_engine = voice.voice_tools.tts_engine

        # Case 1: ElevenLabs available
        mock_elevenlabs.is_available.return_value = True
        mock_elevenlabs.text_to_speech.return_value = b"audio"
        
        voice.voice_tools.text_to_speech("Hi")
        # Ensure it plays the audio
        mock_elevenlabs.play.assert_called()
        # Verify it did NOT use local engine
        mock_engine.say.assert_not_called()
        
        # Case 2: ElevenLabs unavailable
        mock_elevenlabs.is_available.return_value = False
        mock_elevenlabs.play.reset_mock()
        mock_engine.reset_mock()
        
        voice.voice_tools.text_to_speech("Hi")
        mock_elevenlabs.play.assert_not_called()
        mock_engine.say.assert_called_with("Hi")

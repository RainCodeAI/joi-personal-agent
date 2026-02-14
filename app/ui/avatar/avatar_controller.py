import yaml
from pathlib import Path
import time
from typing import List, Tuple, Dict, Any
import base64

class AvatarController:
    def __init__(self, config_path: str = "app/ui/avatar/settings.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)["avatar"]
        self.assets_dir = Path(self.config["assets_dir"])
        self.mouth_shapes = self.config["mouth_shapes"]
        self.expressions = self.config["expressions"]
        self.timing = self.config["timing"]
        self.sentiment_mapping = self.config["sentiment_mapping"]

    def get_current_layers(self, phoneme: str = "rest", expression: str = "neutral") -> List[str]:
        """Return list of layer paths for current state."""
        layers = []
        # Base face
        layers.append(str(self.assets_dir / self.config["base_face"]))
        # Eyes (assume open for now)
        layers.append(str(self.assets_dir / self.config["eyes"]["open"]))
        # Eyebrows
        if expression == "focus":
            layers.append(str(self.assets_dir / self.config["eyebrows"]["focus"]))
        else:
            layers.append(str(self.assets_dir / self.config["eyebrows"]["neutral"]))
        # Mouth
        mouth_key = phoneme if phoneme in self.mouth_shapes else "rest"
        layers.append(str(self.assets_dir / self.mouth_shapes[mouth_key]))
        # Expression overlay
        expr_key = self.sentiment_mapping.get(expression, "neutral")
        if expr_key in self.expressions:
            layers.append(str(self.assets_dir / self.expressions[expr_key]))
        return layers

    def animate_speech(self, phoneme_timeline: List[Tuple[float, str]], expression: str, audio_data: bytes, offset: float = 0.0):
        """Generator yielding layer lists over time for lip-sync."""
        start_time = time.time() + offset
        current_phoneme = "rest"
        for t, phoneme in phoneme_timeline:
            wait_time = start_time + t - time.time()
            if wait_time > 0:
                time.sleep(wait_time)
            current_phoneme = phoneme
            yield self.get_current_layers(current_phoneme, expression)

    def idle_animation(self):
        """Generator for idle blink/parallax."""
        while True:
            # Parallax bob (simple sine wave)
            # For now, just blink
            yield self.get_current_layers("rest", "neutral")
            blink_interval = self.timing["blink_interval"]
            time.sleep(blink_interval[0] + (blink_interval[1] - blink_interval[0]) * 0.5)  # Mid interval
            # Blink: swap to blink eyes
            blink_layers = self.get_current_layers("rest", "neutral")
            blink_layers[1] = str(self.assets_dir / self.config["eyes"]["blink"])  # Eyes layer
            yield blink_layers
            time.sleep(0.1)  # Blink duration
            yield self.get_current_layers("rest", "neutral")
            time.sleep(blink_interval[1] - blink_interval[0] - 0.1)

# Helper to play audio in Streamlit
def play_audio(audio_data: bytes):
    audio_b64 = base64.b64encode(audio_data).decode()
    return f"data:audio/wav;base64,{audio_b64}"

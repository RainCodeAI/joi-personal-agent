import av
import numpy as np
import threading
import queue
import time
from streamlit_webrtc import AudioProcessorBase

class AudioProcessor(AudioProcessorBase):
    def __init__(self):
        self.audio_buffer = []  # List of numpy arrays
        self.audio_queue = queue.Queue()  # Output queue for completed phrases
        self.is_speaking = False
        self.silence_start_time = None
        self.energy_threshold = 1000  # Adjust based on mic sensitivity
        self.silence_duration_threshold = 1.0  # Seconds of silence to trigger end-of-speech
        self.lock = threading.Lock()

    def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
        # Convert to numpy array (int16)
        audio_data = frame.to_ndarray()
        
        # Calculate RMS energy
        rms = np.sqrt(np.mean(audio_data**2))
        
        with self.lock:
            # VAD Logic
            if rms > self.energy_threshold:
                if not self.is_speaking:
                    self.is_speaking = True
                    # print("Speech detected")
                self.silence_start_time = None
                self.audio_buffer.append(audio_data)
            
            elif self.is_speaking:
                # We were speaking, now it's quiet
                self.audio_buffer.append(audio_data) # Keep recording silence briefly
                
                if self.silence_start_time is None:
                    self.silence_start_time = time.time()
                
                # Check formatting duration
                if time.time() - self.silence_start_time > self.silence_duration_threshold:
                    # Phrase complete
                    self.is_speaking = False
                    self.silence_start_time = None
                    # print("Silence detected, packaging phrase")
                    self._package_and_queue()

        return frame

    def _package_and_queue(self):
        if not self.audio_buffer:
            return
            
        # Concatenate all chunks
        full_audio = np.concatenate(self.audio_buffer)
        self.audio_buffer = []
        
        # Add to queue (main thread will pick this up)
        # We queue the raw numpy array (int16, stereo usually)
        self.audio_queue.put(full_audio)

def save_frame_to_wav(audio_data: np.ndarray, filename: str, sample_rate=48000, channels=2):
    """
    Saves a numpy array of audio samples (int16) to a WAV file.
    Default WebRTC audio is 48kHz stereo.
    """
    import wave
    
    # Ensure int16
    if audio_data.dtype != np.int16:
        audio_data = audio_data.astype(np.int16)
        
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 2 bytes for int16
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())



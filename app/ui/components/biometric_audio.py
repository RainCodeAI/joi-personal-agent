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

        # Breath detection state (Phase 9.3)
        self.energy_history = []          # List of (timestamp, rms) tuples
        self.energy_window = 10.0         # Seconds of history to analyze
        self.breath_energy_ceiling = 800  # Below speech threshold but above silence
        self.breath_energy_floor = 100    # Minimum to count as breath (not dead silence)
        self.breathing_state = "none"     # "none", "calm", "stressed"
        self.last_breath_check = 0.0
        self.breath_check_interval = 2.0  # Analyze every 2 seconds

    def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
        # Convert to numpy array (int16)
        audio_data = frame.to_ndarray()

        # Calculate RMS energy
        rms = np.sqrt(np.mean(audio_data**2))

        # Track energy for breath detection (Phase 9.3)
        self.energy_history.append((time.time(), float(rms)))

        with self.lock:
            # VAD Logic
            if rms > self.energy_threshold:
                if not self.is_speaking:
                    self.is_speaking = True
                self.silence_start_time = None
                self.audio_buffer.append(audio_data)

            elif self.is_speaking:
                # We were speaking, now it's quiet
                self.audio_buffer.append(audio_data) # Keep recording silence briefly

                if self.silence_start_time is None:
                    self.silence_start_time = time.time()

                # Check silence duration
                if time.time() - self.silence_start_time > self.silence_duration_threshold:
                    # Phrase complete
                    self.is_speaking = False
                    self.silence_start_time = None
                    self._package_and_queue()

        # Analyze breathing when NOT speaking
        if not self.is_speaking:
            self._analyze_breathing()

        return frame

    def _package_and_queue(self):
        if not self.audio_buffer:
            return

        # Concatenate all chunks
        full_audio = np.concatenate(self.audio_buffer)
        self.audio_buffer = []

        # Add to queue (main thread will pick this up)
        self.audio_queue.put(full_audio)

    # ── Breath Detection (Phase 9.3) ──────────────────────────────────────

    def _analyze_breathing(self):
        """Analyze recent energy history for breathing patterns.

        Breathing signature: rhythmic energy pulses between breath_energy_floor
        and breath_energy_ceiling, at 0.2-0.5 Hz (calm) or 0.5-1.0 Hz (stressed).
        """
        now = time.time()
        if now - self.last_breath_check < self.breath_check_interval:
            return
        self.last_breath_check = now

        # Prune old entries
        cutoff = now - self.energy_window
        self.energy_history = [(t, e) for t, e in self.energy_history if t > cutoff]

        if len(self.energy_history) < 20:
            self.breathing_state = "none"
            return

        # Extract RMS values in the "breathing band"
        breath_band = [
            (t, e) for t, e in self.energy_history
            if self.breath_energy_floor < e < self.breath_energy_ceiling
        ]

        if len(breath_band) < 10:
            self.breathing_state = "none"
            return

        # Count peaks (local maxima in energy)
        energies = [e for _, e in breath_band]
        peaks = 0
        for i in range(1, len(energies) - 1):
            if energies[i] > energies[i-1] and energies[i] > energies[i+1]:
                peaks += 1

        # Calculate rate: peaks per second
        time_span = breath_band[-1][0] - breath_band[0][0]
        if time_span < 2.0:
            self.breathing_state = "none"
            return

        rate = peaks / time_span

        # Classify: calm breathing ~12-20 breaths/min (0.2-0.33 Hz)
        #           stressed breathing ~20-40 breaths/min (0.33-0.67 Hz)
        if 0.15 <= rate <= 0.35:
            self.breathing_state = "calm"
        elif 0.35 < rate <= 0.8:
            self.breathing_state = "stressed"
        else:
            self.breathing_state = "none"


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

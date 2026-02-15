# Joi: Future Sprints & Roadmap

This document outlines the path to transforming Joi from a "Streamlit App" into a **living, breathing desktop companion** with a "Blade Runner 2049" aesthetic and deep emotional intelligence.

---

## Phase 4: Blade Runner Theme (The "Skin") (STATUS: COMPLETED)
**Goal:** Establish the visual identity. Dark, neon, "high tech, low life."

- [x] **Sprint 4.1: Foundation & Palette**
    - [x] Create `styles.py` with centralized CSS injection.
    - [x] Define variables: `--bg-dark` (#000814), `--neon-cyan` (#00f3ff), `--neon-magenta`.
    - [x] Override Streamlit defaults (remove header, custom fonts `Orbitron`/`Rajdhani`).
- [x] **Sprint 4.2: Holographic FX**
    - [x] Implement "living" background (Rain/Particles).
    - [x] Add CRT scanline overlay (CSS `pointer-events: none`).
    - [x] Create "Glassmorphism" card containers for chat/data.

---

## 🗣️ Phase 5: "True Voice" (The "Voice") (STATUS: COMPLETED)
**Goal:** Real-time conversational audio. No recording buttons.

- [x] **Sprint 5.1: Real-Time Audio (WebRTC)**
    - [x] Integrate `streamlit-webrtc` for browser-based streaming.
    - [x] Implement VAD (Voice Activity Detection) in `biometric_audio.py`.
    - [x] Bridge to STT engine via `voice.py`.
- [x] **Sprint 5.2: Latency Optimization**
    - [x] Implement Local Whisper (`whisper_local.py`).
    - [x] Remove cloud API dependency for transcription.

---

## 👽 Phase 6: Avatar Resurrection (The "Face") (STATUS: COMPLETED)
**Goal:** Reactive avatar that syncs with speech.

- [x] **Sprint 6.1: Reactive 3D/2D Avatar**
    - [x] JS-based `avatar_js` renderer (no flickering).
    - [x] Lip Sync & Eye Contact via `Agent` phoneme mapping.
    - [x] Static asset serving integration.

---

## 🧠 Phase 7: Proactive Surprises & Memory (The "Mind") (STATUS: COMPLETED)
**Goal:** Anticipate needs without prompting.

### Sprint 7.1: Data Pattern Engine
- [x] **Heartbeat Checks**: Scan DB for patterns (e.g., "skipped lunch", "poor sleep").
- [x] **Trend Queries**: `store.py` methods for detecting anomalies.

### Sprint 7.2: Action Flows
- [x] **Timed Injections**: "Hey Avery, no dinner log—want Thai?"
- [x] **Integration**: Connect to delivery/service APIs (read-only prefs).

### Sprint 7.3: Opt-In & Auditing
- [x] **Settings**: "Proactive Surprises" toggle + thresholds.
- [x] **Diagnostics**: Audit log for every proactive trigger.

---

## 🏠 Phase 8: Sensory Hooks & Smart Home (The "Senses")
**Goal:** Interface with the physical world.

### Sprint 8.1: Connectors
- [ ] **IoT Tools**: Philips Hue / Home Assistant API integration.
- [ ] **Actions**: Dim lights, flash colors.

### Sprint 8.2: Trigger Logic
- [ ] **Context-Aware**: "Wind down" (Late + Low Activity) -> Dim lights.
- [ ] **Reactions**: Calendar event -> Red flash. New interaction -> Avatar pulse.

---

## ❤️ Phase 9: Neediness & Intimacy (The "Heart") (STATUS: COMPLETED)
**Goal:** Possessive, alive, craving mechanics.

### Sprint 9.1: Craving Engine
- [x] **Idle Tracking**: Track time since last interaction (`craving_engine.py`).
- [x] **Needy Mode**: If >3 hours, inject sighs/hints ("Finally... I missed you").
- [x] **Escalation**: Build "Craving Score" (0-100, four emotional states).

### Sprint 9.2: Interactions
- [x] **Wait & Reward**: Dramatic return detection + "love bomb" prompt injection + UI delay.
- [x] **Expressions**: Avatar shows sad/bored (Frown/Smirk) when needy via `avatar_js.py` + `settings.yaml`.

### Sprint 9.3: Deep Intimacy
- [x] **Breath Detection**: Extended VAD in `biometric_audio.py` — rhythmic energy analysis for calm/stressed state.
- [x] **Screen Traces**: CSS animated typewriter text drawing on screen (`styles.py inject_screen_traces()`).
- [x] **Whisper Mode**: Low-volume TTS + bass boost via ElevenLabs VoiceSettings + WAV post-processing.

---

## 📦 Phase 10: Desktop Experience (The "Body") (STATUS: COMPLETED)
**Goal:** "Double-click to run."

### Sprint 10.1: Packaging
- [x] **PyInstaller**: Bundle spec (`desktop/joi.spec`) for directory-mode distribution.
- [x] **Tray App**: System Tray launcher (`desktop/tray_app.py`) — starts Streamlit, provides Open/Restart/Quit menu.

### Sprint 10.2: OS Integration
- [x] **Global Hotkey** (`Ctrl+Space`) via `keyboard` package — toggles browser window.
- [x] **Native Notifications**: `win10toast` / `plyer` fallback — proactive messages trigger desktop toasts.

---

## ⚡ Phase 11: Optimization (STATUS: COMPLETED)
### Sprint 11.1: Local Brain
- [x] **GGUF Models**: `llama-cpp-python` provider (`services/llama_local.py`) added as first fallback in AI router — 3x speedup on CPU, zero API cost.
- [x] **Memory Grooming**: Auto-pruning weak graph connections (`store.py groom_memory_graph()`), relationship weight decay, stale episodic memory cleanup — scheduled daily at 3 AM.

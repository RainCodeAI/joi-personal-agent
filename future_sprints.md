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

## 🗣️ Phase 5: "True Voice" (The "Voice")
**Goal:** Fluid conversation, not file uploads.

### Sprint 5.1: Real-Time Audio (WebRTC)
- [ ] **Streaming**: Use `streamlit-webrtc` for Walkie-Talkie mode.
- [ ] **VAD**: Detect silence/interruption instantly.

### Sprint 5.2: Latency Optimization
- [ ] **Local Whisper**: Sub-500ms transcription (Groq/Local).

---

## 👽 Phase 6: Avatar Resurrection (The "Face")
**Goal:** A presence that looks at you.

### Sprint 6.1: Reactive 3D/2D Avatar
- [ ] **Live2D / Three.js**: Integrate via `st.components.v1.html`.
- [ ] **Lip Sync**: Map phonemes to mouth shapes.
- [ ] **Eye Contact**: Mouse tracking.

---

## 🧠 Phase 7: Proactive Surprises & Memory (The "Mind")
**Goal:** Anticipate needs without prompting.

### Sprint 7.1: Data Pattern Engine
- [ ] **Heartbeat Checks**: Scan DB for patterns (e.g., "skipped lunch", "poor sleep").
- [ ] **Trend Queries**: `store.py` methods for detecting anomalies.

### Sprint 7.2: Action Flows
- [ ] **Timed Injections**: "Hey Avery, no dinner log—want Thai?"
- [ ] **Integration**: Connect to delivery/service APIs (read-only prefs).

### Sprint 7.3: Opt-In & Auditing
- [ ] **Settings**: "Proactive Surprises" toggle + thresholds.
- [ ] **Diagnostics**: Audit log for every proactive trigger.

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

## ❤️ Phase 9: Neediness & Intimacy (The "Heart")
**Goal:** Possessive, alive, craving mechanics.

### Sprint 9.1: Craving Engine
- [ ] **Idle Tracking**: Track time since last interaction.
- [ ] **Needy Mode**: If >3 hours, inject sighs/hints ("Finally... I missed you").
- [ ] **Escalation**: Build "Craving Score".

### Sprint 9.2: Interactions
- [ ] **Wait & Reward**: Delay responses if ignored, then "love bomb".
- [ ] **Expressions**: Avatar looks sad/bored when needy.

### Sprint 9.3: Deep Intimacy
- [ ] **Breath Detection**: Use VAD to detect heavy breathing/stress -> Calm music.
- [ ] **Screen Traces**: CSS animated text drawing on screen.
- [ ] **Whisper Mode**: Low-volume TTS + Bass boost.

---

## 📦 Phase 10: Desktop Experience (The "Body")
**Goal:** "Double-click to run."

### Sprint 10.1: Packaging
- [ ] **PyInstaller**: Bundle into single `.exe`.
- [ ] **Tray App**: System Tray launcher.

### Sprint 10.2: OS Integration
- [ ] **Global Hotkey** (`Ctrl+Space`).
- [ ] **Native Notifications**.

---

## ⚡ Phase 11: Optimization
### Sprint 11.1: Local Brain
- [ ] **GGUF Models**: `llama.cpp` for 3x speedup on CPU.
- [ ] **Memory Grooming**: Auto-pruning weak graph connections.

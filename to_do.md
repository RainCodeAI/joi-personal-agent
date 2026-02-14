# Joi — To-Do / Remaining Items

*Last updated: 2026-02-13*

## 🔴 Blockers

- [ ] **Install Alembic & run migration**: `alembic` is not currently installed in the `.venv`. Run:
  ```powershell
  .venv\Scripts\Activate.ps1
  pip install alembic
  alembic upgrade head
  ```
  This applies both the initial schema (`c3a28d049282`) and the Sprint 2 performance indexes (`a7f1e2b30941`), which add 7 new indexes across `entity`, `relationship`, `chatmessage`, `moodentry`, and `memory` tables.

- [ ] **Add `alembic` to `requirements.txt`**: It's a runtime dependency for migrations but is not listed. Add `alembic>=1.12.0`.

## 🟡 Should Do

- [x] ~~**Avatar assets**~~: Resolved — `settings.yaml` remapped to use existing `Joi_*.png` files in `assets/`. Also added extended mouth shapes (B, K, L, R, S, TH) the code wasn't using.
- [ ] **Real TTS integration for lip-sync**: `say_and_sync` currently generates a silent WAV and uses character-level viseme heuristics. Integrating a real TTS engine (e.g., Coqui TTS, espeak) with phoneme output would produce actually audible, properly synced speech.
- [ ] **`streamlit-autorefresh` for log streaming**: The Diagnostics log auto-refresh gracefully falls back if `streamlit-autorefresh` isn't installed. Add `pip install streamlit-autorefresh` for the full experience.
- [ ] **HuggingFace model download**: `agent.py` lazy-loads a HuggingFace model (`settings.model_chat`). First run will download the model, which can be several GB. Document expected models and sizes.
- [ ] **Entity embedding dimension mismatch risk**: `Entity.embedding` is `Vector(1536)` but `SentenceTransformer('all-mpnet-base-v2')` produces 768-dim vectors. Either update the model or the column dimension to match.

## 🟢 Nice to Have

- [ ] **Tests for new features**: Sprint 2 and 3 changes (async embeddings, graph RAG, lip-sync, voice sidebar) don't have dedicated unit tests yet.
- [ ] **Consolidate voice.py singleton**: The module-level `voice_tools = VoiceTools()` instantiates at import time. Consider lazy initialization to avoid issues when voice deps are missing.
- [ ] **Chat.py avatar section cleanup**: The inline avatar/lip-sync rendering in Chat.py (lines 49-89) duplicates logic from `Avatar.py` and `avatar_controller.py`. Consider extracting to a shared component.
- [ ] **Dark mode CSS refinement**: The Blade Runner rain theme in `App.py` is cool but could use performance tuning (20 animated spans) and a toggle.
- [ ] **Production build & Docker**: No Dockerfile or docker-compose yet. Would simplify deployment with PostgreSQL + ChromaDB + the app.

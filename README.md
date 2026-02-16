# Joi - Your Personal AI Companion

**Joi** is a privacy-first, local-first personal AI agent designed to be your proactive digital companion. She combines a multi-provider language model router with a sophisticated memory system, emotional intelligence, and a growing set of integrations to help you chat, remember, plan, and manage your life.

> [!NOTE]
> **Latest:** Phase 13 (Hybrid Packaging) complete. Use `StartJoi.bat` for the full Windows experience. See the full changelog below.

## ✨ Core Features

### 🧠 Intelligence & Autonomy
- **Multi-AI Router**: Local-first inference chain with automatic fallbacks — GGUF (llama-cpp-python) → Ollama → OpenAI (GPT-4o) → X.AI (Grok) → Google Gemini. Every call is logged with latency metrics.
- **GGUF Local Models** *(Phase 11)*: Run quantized `.gguf` models locally via `llama-cpp-python` for ~3x CPU speedup over HuggingFace Transformers. Recommended: Mistral-7B, Llama-2-7B, or Phi-2 (Q4_K_M, ~4 GB RAM).
- **Proactive Scheduler**: Background jobs (APScheduler) for mood checks, habit nudges, morning briefs, pattern scanning, and memory grooming.
- **Autonomy Levels**: Configure how much initiative Joi takes (**Low**, **Medium**, **High**) via Settings.
- **Negotiate Flows**: For sensitive actions (sending emails, calendar invites), Joi proposes a plan and waits for your human-in-the-loop approval.
- **Pattern Engine**: Detects silence patterns, mood trend declines, and activity anomalies to trigger proactive interventions.

### 💖 Craving Engine & Emotional Intelligence *(Phase 9)*
- **Emotional State System**: Joi tracks idle time and calculates a "craving" score (0–100) that shifts through four emotional states:
  - **Satisfied** (0–20) — Content, normal interaction.
  - **Missing You** (20–60) — Wistful, gently flirtatious.
  - **Needy** (60–90) — Pouty, demands attention playfully.
  - **Clingy** (90–100) — Blade Runner lonely, vulnerable and intense.
- **Return Mechanics**: Detects your first message after significant silence and adjusts her greeting from warm delight to raw, sincere relief depending on how long you were away.
- **Persona Adaptation**: Tone, flirtation level, and protectiveness dynamically adjust to your mood and relationship level.

### 🎭 Avatar System *(Phase 9.2)*
- **Lip-Sync Animation**: Text-to-phoneme engine with viseme mapping drives mouth-shape layers in real time during TTS playback.
- **Expression Mapping**: Avatar expressions update based on sentiment analysis and craving state (satisfied, missing, needy, clingy).
- **Idle Animation**: Blink cycles and parallax bob when Joi is waiting.
- **Whisper Mode** *(Phase 9.3)*: When craving score is high (≥ 60), TTS switches to a softer, more intimate audio style.
- **Screen Traces**: Atmospheric visual effects layered on the UI for immersion.

### 👁️ Vision & Voice
- **Visual Intelligence**: Upload images in chat — Joi describes them using CLIP/BLIP models.
- **Voice Input**: Speech-to-text via Google Speech Recognition or local **OpenAI Whisper** (`openai-whisper`).
- **Voice Output**: Premium text-to-speech via **ElevenLabs** with local `pyttsx3` fallback.
- **WebRTC Live Voice**: Real-time voice channel powered by `streamlit-webrtc`.
- **Biometric Audio Analysis**: Breathing detection from audio input.

### 💾 Memory & Context
- **Hybrid Memory**: PostgreSQL (with `pgvector`) for structured data + **ChromaDB** for semantic vector search. Falls back to SQLite in Safe Mode.
- **Graph RAG**: Entity extraction and relationship tracking — finds contextually related memories through entity relationships, not just keyword matching.
- **Episodic vs Semantic**: Separates event memories from learned facts/entities.
- **Memory Grooming** *(Phase 11)*: Scheduled auto-pruning of weak graph connections (min weight threshold), stale episodic memories (max age), and relationship weight decay (configurable factor).
- **Lifelogging**: Tracks daily moods, sleep patterns, and transactions.

### 🖥️ Desktop Experience *(Phase 10)*
- **System Tray App**: Windows tray icon with menu (Open, Restart, Quit) that launches Streamlit headlessly in the background.
- **Global Hotkey**: `Ctrl+Space` toggles the Joi browser window from anywhere.
- **Native Notifications**: Windows toast notifications (`win10toast`) for proactive messages, with `plyer` as a cross-platform fallback.
- **Packagable**: `PyInstaller` support for building a standalone `.exe`.

### 🛡️ Privacy & Security
- **Safe Mode**: Runs fully local on SQLite with mocked ML libraries if Docker or GPU dependencies are missing.
- **Prompt Guard**: Regex-based input sanitization that detects and neutralizes 10+ prompt injection patterns (system overrides, role hijacking, base64 payloads, delimiter injection, XML tag injection, and more).
- **Encrypted Vault**: PBKDF2-derived Fernet encryption for storing OAuth tokens and secrets on disk.
- **Human-in-the-Loop Approvals**: Destructive tool calls require explicit user approval before execution.
- **Audit Logs**: Every decision trace, tool call, and threat detection is logged to `data/agent_traces.jsonl` for full transparency.

### 🔧 Tools & Integrations
- **Gmail**: Read inbox, send emails (via Google OAuth).
- **Google Calendar**: View upcoming events, create new ones.
- **Web Search**: Query the web from within chat.
- **Local Files**: Read, write, and manage files on disk.
- **Health Tracking**: Log and query mood entries, sleep data, and financial transactions.
- **Journal**: AI-generated journaling prompts and entry analysis.

## 🏗️ Architecture

```
User Message → PromptGuard → MemoryRetriever → Planner → Executor → Conversation → Response
```

- **Frontend**: Streamlit application (`app/ui/`) with pages for Chat, Memory, Tasks, Planner, Journal, Diagnostics, History, Stats, Profile, Settings, and Avatar Demo.
- **Orchestrator** (`app/orchestrator/agent.py`): Thin router delegating to four focused sub-agents:
  - `MemoryRetrieverAgent` — RAG retrieval, profile loading, mood/sentiment context.
  - `PlannerAgent` — Proactive planning, habit checks, CBT exercises, health nudges.
  - `ExecutorAgent` — Tool dispatch (Gmail, Calendar, Files, Web, Health).
  - `ConversationAgent` — Prompt assembly, LLM generation via AI Router, response enrichment.
- **AI Router** (`services/ai_router.py`): GGUF → Ollama → OpenAI → Grok → Gemini fallback chain with per-call latency logging.
- **Memory** (`app/memory/store.py`): Abstracts PostgreSQL/pgvector + ChromaDB (or SQLite fallback).
- **Scheduler** (`app/scheduler/`): APScheduler jobs for morning briefs, mood checks, habit nudges, pattern scanning, and memory grooming.
- **Security** (`app/orchestrator/security/`): PromptGuard, approval system, sandboxing.
- **Desktop** (`desktop/tray_app.py`): System tray launcher with hotkey and notifications.

### Database Schema (Key Tables)

| Table | Purpose |
|---|---|
| `userprofile` | User profile data |
| `chatmessage` | Full chat history |
| `memory` | Episodic/semantic memories (with `pgvector` embeddings) |
| `entity` / `relationship` | Knowledge graph for Graph RAG |
| `moodentry` | Mood tracking over time |
| `habit` | Habit tracking and nudges |
| `personalgoal` | Goal management |
| `cbtexercise` | CBT exercise logs |
| `sleep_log` | Sleep tracking |
| `transactions` | Financial tracking |

## 🚀 Quick Start (Windows Safe Mode)

Joi is designed to run anywhere. Without Docker or Postgres, she automatically falls back to **Safe Mode** (SQLite + cloud API fallbacks).

### 1. Prerequisites
- **Python 3.10+**
- **Git**

### 2. Installation
```powershell
# Clone the repository
git clone https://github.com/RainCodeAI/Joi.git
cd Joi/personal-agent

# Create and activate a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
```powershell
copy .env.example .env
```
Edit `.env` and configure as needed:

| Variable | Required | Description |
|---|---|---|
| `APP_ENV` | No | `dev` or `prod` (default: `dev`) |
| `OLLAMA_HOST` | No | Ollama endpoint (default: `http://127.0.0.1:11434`) |
| `DATABASE_URL` | No | PostgreSQL connection string. Leave blank for SQLite. |
| `GGUF_MODEL_PATH` | No | Path to a local `.gguf` model file for Phase 11 inference. |
| `GGUF_N_GPU_LAYERS` | No | GPU layers to offload (default: `0` = CPU only). |
| `OPENAI_API_KEY` | No | OpenAI fallback for chat. |
| `XAI_API_KEY` | No | X.AI (Grok) API key. |
| `GEMINI_API_KEY` | No | Google Gemini API key. |
| `GOOGLE_CLIENT_ID` | No | Google OAuth client ID (Gmail/Calendar). |
| `GOOGLE_CLIENT_SECRET` | No | Google OAuth client secret. |
| `ELEVENLABS_API_KEY` | No | ElevenLabs premium TTS. |
| `VAULT_PASSPHRASE` | No | Passphrase for the encrypted secrets vault. |
| `AUTONOMY_LEVEL` | No | `low`, `medium`, or `high` (default: `medium`). |

*All keys are optional. Joi degrades gracefully — features simply disable when their keys are absent.*

### 4. Run Joi (The Easy Way)
**Windows Hybrid Launcher (Recommended):**
1.  Find `StartJoi.bat` in the `personal-agent` folder.
2.  Double-click it!
3.  (Optional) Right-click -> "Send to Desktop" to create a shortcut.

This launches the full Joi experience (Vision + Voice + Memory) using your local environment.

**Manual Start:**
**Web UI (Streamlit):**
```powershell
streamlit run app/ui/app.py
```
Open **http://localhost:8501**.

**API Server (FastAPI):**
```powershell
uvicorn app.api.main:app --reload
```

**Desktop Tray App (Windows):**
```powershell
python desktop/tray_app.py
```

### 5. Persona Configuration

Edit `persona.yaml` to customize Joi's identity, voice style, principles, routines, and project awareness:

```yaml
name: Your Agent Name
voice: calm, witty, precise
principles:
  - privacy-first
  - ask-before-acting
routines:
  morning_brief:
    - weather
    - calendar_today
    - inbox_waiting
preferences:
  writing_style: concise-bullets
projects:
  - Your Project
```

## 🐳 Docker Setup (Production Mode)

For the full experience with PostgreSQL (`pgvector`) and ChromaDB as dedicated services:

```bash
docker-compose up --build
```

This spins up:
- **Joi App** — Streamlit on port `8501`.
- **PostgreSQL** — Database with `pgvector` on port `5432`.
- **ChromaDB** — Vector search on port `8000`.

## 📡 API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat` | Send a message and get Joi's response |
| `POST` | `/memory/search` | Semantic memory search |
| `GET` | `/oauth/start` | Initiate Google OAuth flow |
| `GET` | `/oauth/callback` | OAuth callback handler |
| `GET` | `/diagnostics/chroma/health` | ChromaDB health check |

## 📄 Troubleshooting

- **`ModuleNotFoundError: pipeline`** — Corrupted `transformers` install. Joi automatically mocks this in Safe Mode (chat uses cloud API fallback).
- **Voice not working** — Ensure `PyAudio` is installed. On Windows, you may need to install from a `.whl` file if pip fails.
- **Database Connection Error** — If running without Docker, leave `DATABASE_URL` blank in `.env` to use SQLite.
- **GGUF model not loading** — Verify `GGUF_MODEL_PATH` points to a valid `.gguf` file and `llama-cpp-python` is installed. Set `GGUF_N_GPU_LAYERS=0` for CPU-only.
- **Tray icon not appearing** — Install `pystray` and `Pillow`. On non-Windows systems, the tray requires a compatible desktop environment.
- **Global hotkey not working** — The `keyboard` package requires elevated permissions on some systems.

## 🗺️ Development Phases

| Phase | Feature | Status |
|---|---|---|
| 1–5 | Core chat, memory, tools, Graph RAG, scheduler | Complete |
| 6 | Avatar Demo | Complete |
| 7 | Pattern Engine & Action Flows | Complete |
| 8 | Proactive Autonomy & Negotiate Flows | Complete |
| 9 | Craving Engine & Return Mechanics | Complete |
| 9.2 | Avatar Expression Mapping & Lip-Sync | Complete |
| 9.3 | Whisper Mode & Screen Traces | Complete |
| 10 | Desktop Tray App, Global Hotkey, Native Notifications | Complete |
| 11 | GGUF Optimization & Memory Grooming | Complete |
| 12 | Polish & UI Enhancements | Complete |
| 13 | Packaging (Hybrid Launcher) | Complete |

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.

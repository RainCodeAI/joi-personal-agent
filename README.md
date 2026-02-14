# Joi - Your Personal AI Companion

**Joi** is a privacy-first, local-first personal AI agent designed to be your proactive digital companion. She combines a powerful, multi-provider language model router with a sophisticated memory system to help you chat, remember, and track your life.

> [!NOTE]
> **New in v2.0:** Proactive Autonomy, Vision, Voice, and negotiation flows!

## ✨ Core Features

### 🧠 Intelligence & Autonomy
- **Proactive Scheduler**: Joi runs background checks on your mood and habits, initiating conversations if you need a nudge.
- **Negotiate Flows**: For sensitive actions (sending emails, calendar invites), Joi proposes a plan and waits for your approval in the UI.
- **Autonomy Levels**: Configure how much initiative Joi takes (**Low**, **Medium**, **High**) via Settings.
- **Multi-AI Chat**: Local-first responses using Hugging Face Transformers, with automatic fallbacks to OpenAI, X.AI (Grok), and Google Gemini.

### 👁️ Vision & Voice
- **Visual Intelligence**: Upload images to Chat, and Joi will "see" and describe them using the BLIP model.
- **Voice Interaction**: Global voice controls — Speech-to-Text (STT) and premium Text-to-Speech (TTS) via ElevenLabs (with local fallback).

### 💾 Memory & Context
- **Hybrid Memory**: PostgreSQL (or SQLite) for structured data + ChromaDB for semantic vector search.
- **Graph RAG**: Finds contextually related memories through entity relationships, not just keyword matching.
- **Lifelogging**: Tracks daily moods, sleep patterns, and transactions.

### 🛡️ Privacy & Security
- **Safe Mode**: Runs fully local on SQLite/mocked-ML if Docker or GPU dependencies are missing.
- **Prompt Guard**: Sanitizes inputs to prevent prompt injection attacks.
- **Audit Logs**: Every decision and tool call is logged in `data/agent_traces.jsonl` for transparency.

## 🏗️ Architecture

- **Frontend**: `Streamlit` application (`app/ui/`) providing the main interface.
- **Orchestrator**: `app/orchestrator/` manages sub-agents:
  - `PlannerAgent`: Proactive scheduling & health nudges.
  - `ExecutorAgent`: Tool dispatch (Gmail, Calendar, Files).
  - `ConversationAgent`: Prompt assembly & LLM generation.
- **Memory**: `app/memory/store.py` abstracts interactions with the database and vector store.

## 🚀 Quick Start (Windows "Safe Mode")

Joi is designed to run anywhere. If you don't have Docker or Postgres installed, she will automatically fall back to **Safe Mode** (SQLite + Cloud APIs).

### 1. Prerequisites
- **Python 3.10+** installed.
- **Git** installed.

### 2. Installation
```powershell
# Clone the repository
git clone https://github.com/RainCodeAI/Joi.git
cd Joi/personal-agent

# Create virtual environment usually best
# python -m venv .venv
# .venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file from the example:
```powershell
copy .env.example .env
```
Edit `.env` and add your API keys:
- `openai_api_key`: (Optional) for fallback intelligence.
- `elevenlabs_api_key`: (Optional) for high-quality voice.
- `google_client_id`: (Optional) for Gmail/Calendar tools.

*Note: In Safe Mode, `DATABASE_URL` can be left commented out to use SQLite.*

### 4. Run Joi
```powershell
streamlit run app/ui/app.py
```
Open **http://localhost:8501** (or the port shown in terminal).

## 🐳 Docker Setup (Production Mode)

For the full experience (Postgres with pgvector, local ChromaDB service), use Docker:

```bash
docker-compose up --build
```
This spins up:
- **Joi App**: The main application.
- **Postgres**: Database with `pgvector` enabled.
- **ChromaDB**: Vector search service.

## 📄 Troubleshooting

- **`ModuleNotFoundError: pipeline`**: This usually means a corrupted `transformers` install.
  - *Fix*: Joi automatically mocks this library in Safe Mode so the app still runs (Chat uses OpenAI fallback).
- **Voice not working**: Ensure `PyAudio` is installed. On Windows, you might need to install it from a `.whl` file if pip fails.
- **Database Connection Error**: If running without Docker, ensure `DATABASE_URL` is commented out in `.env` to use SQLite.

## 📜 License

MIT License. See [LICENSE](LICENSE) for details.

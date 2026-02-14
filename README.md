# Joi - Your Personal AI Companion

Joi is a privacy-first, local-first personal AI agent designed to be your digital companion. It combines a powerful, multi-provider language model router with a sophisticated memory system to help you chat, remember, and track your life.

Built with a Streamlit frontend and a FastAPI backend, Joi leverages Hugging Face Transformers for local text generation with seamless fallbacks to cloud providers. All structured data is stored in a local PostgreSQL database with pgvector, and vector embeddings for memory are handled by ChromaDB.

<!-- TODO: Add a screenshot of the UI -->
<!-- ![Joi UI Screenshot](https://user-images.githubusercontent.com/12345/your-screenshot-url.png) -->

## ✨ Core Features

- **Multi-AI Chat**: Local-first responses using Hugging Face Transformers (configurable model), with automatic fallbacks to OpenAI, X.AI (Grok), and Google Gemini for robust availability.
- **Advanced Memory**: A hybrid memory system combining a PostgreSQL database for structured data (moods, sleep, finances) and a ChromaDB vector store for semantic search over unstructured memories.
- **Graph RAG Search**: Entity-aware retrieval that combines vector similarity with knowledge graph traversal — finds contextually related memories through entity relationships, not just keyword matching.
- **Async Embeddings**: Non-blocking text embedding via `ThreadPoolExecutor`, keeping the UI responsive during memory operations.
- **Lifelogging & CRM**: Track daily moods, sleep patterns, transactions, and manage personal contacts to get nudges and insights.
- **Voice Interaction**: Global voice controls in the sidebar — Speech-to-Text (STT) and Text-to-Speech (TTS) available from any page.
- **Avatar with Lip-Sync**: Animated avatar with text-to-viseme mapping, expression overlay, and idle animations.
- **System Diagnostics**: Monitor DB health, index status, table performance stats, query benchmarks, and real-time log streaming from a dedicated UI page.
- **Privacy-First**: Designed to run locally, keeping your data on your machine. API keys are stored securely in a `.env` file.

## 🏗️ Architecture

Joi operates on a simple but powerful client-server model:

- **Frontend**: A multi-page `Streamlit` application (`app/ui/`) provides the user interface.
- **Backend**: A `FastAPI` server (`app/api/`) handles API requests, orchestration, and business logic.
- **Orchestrator**: `app/orchestrator/agent.py` manages LLM generation, tool dispatch, sentiment analysis, and avatar lip-sync.
- **Memory**: `app/memory/store.py` abstracts interactions with the `PostgreSQL` database and `ChromaDB` vector store. Supports async embedding and graph RAG search.
- **Database**: `PostgreSQL` with `pgvector` for structured data + entity embeddings, and `ChromaDB` for document-level vector search.
- **Voice**: `app/tools/voice.py` provides STT/TTS via `SpeechRecognition` and `pyttsx3`, exposed globally through sidebar controls.

## 📄 Pages

| Page | Description |
|------|-------------|
| **Chat** | Main conversation interface with mood-aware avatar and decision logger |
| **Memory** | Search memories with graph/vector provenance indicators |
| **Planner** | Task planning and scheduling |
| **Avatar Demo** | Test lip-sync and expressions with custom text |
| **Profile** | User profile, therapeutic mode, personality settings |
| **Stats** | Mood trends and activity tracking |
| **Journal** | Journaling with AI-powered prompts and analysis |
| **Settings** | OAuth connectors, persona toggle, folder indexing |
| **Diagnostics** | DB health, indexes, table stats, query benchmarks, log streaming |
| **History** | Past chat sessions |

## 🚀 Setup & Installation

Follow these steps to get Joi running on your local machine (macOS or Windows).

### 1. Prerequisites
**macOS:**
```bash
brew install ollama postgresql portaudio
```

**Windows:**
1.  **Ollama**: Download and install from [ollama.com](https://ollama.com).
2.  **PostgreSQL**: Download the installer from [postgresql.org](https://www.postgresql.org/download/windows/) (v14+ recommended). Matches credentials in `.env.example`.
3.  **Visual Studio Build Tools**: Required for some Python packages.

**Common:**
Pull the required Ollama models:
```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

### 2. Database Setup
Create a dedicated user and database for Joi.

**macOS / Linux:**
```bash
psql postgres
```

**Windows (PowerShell):**
```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres
```

Inside the `psql` shell:
```sql
CREATE USER joi_user WITH PASSWORD 'JoiDBSecure!2024';
CREATE DATABASE joi_db OWNER joi_user;
-- Connect to the new DB and enable extensions
\c joi_db
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### 3. Application Installation
Set up the Python environment and install dependencies.

```bash
# Clone the repository
# git clone https://github.com/your-username/joi.git
# cd joi

# Create virtual environment
python -m venv .venv

# Activate environment
# macOS/Linux:
source .venv/bin/activate
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Install required packages
pip install -r requirements.txt
```
*Note: For Windows voice support, you may need to install `PyAudio` using a `.whl` file if pip fails.*

### 4. Configuration
Create a `.env` file from the example and fill in your credentials.

```bash
# macOS/Linux
cp .env.example .env
# Windows
copy .env.example .env
```

Edit `.env` with your API keys:
- `DATABASE_URL`: Ensure it matches your Postgres setup.
- `OPENAI_API_KEY`, `XAI_API_KEY`, `GEMINI_API_KEY`: For fallbacks.
- `GOOGLE_CLIENT_ID` & `SECRET`: For Calendar/Gmail (optional).

### 5. Database Migration
Apply the database schema using Alembic.

```bash
pip install alembic  # if not already in requirements.txt
alembic upgrade head
```

### 6. Initialize Vector Store
This wipes the existing ChromaDB store and creates a new one. **Run this if you change embedding dimensions.**

```bash
python scripts/reset_chroma.py
```

## 🏃‍♀️ Running Joi
Joi requires two separate terminal processes.

**1. Start the Backend API:**
```bash
# Terminal 1 (with .venv activated)
uvicorn app.api.main:app --reload --port 8000
```

**2. Start the Frontend UI:**
```bash
# Terminal 2 (with .venv activated)
streamlit run app/ui/App.py
```

Open **http://localhost:8501** to interact with Joi.

## Troubleshooting

- **`InvalidDimensionException`**: This means the embedding dimension in your code/config does not match what's stored in ChromaDB. Stop the apps and run `python scripts/reset_chroma.py` to fix it.
- **`Connection Refused` errors**: Ensure `ollama serve` is running and accessible. If Ollama is down, the AI router should automatically use a cloud fallback.
- **Database Errors**: Verify your `DATABASE_URL` in `.env` is correct and that the PostgreSQL server is running.
- **Voice not working on Windows**: Ensure `PyAudio` is installed (`pip install PyAudio`). If pip fails, download the correct `.whl` from [Christoph Gohlke's archive](https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio).
- **Missing indexes**: Run `alembic upgrade head` to apply all database migrations including performance indexes.

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

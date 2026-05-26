# Joi - Personal Agent

Joi is a privacy-first, local-first personal AI companion with a multi-provider router, structured memory, emotional state modeling, approvals, planning, diagnostics, and a new Next.js frontend.

> [!NOTE]
> Phase 2 migration is underway. The primary web stack is now FastAPI plus Next.js. Streamlit remains in the repo only as a temporary internal client during the migration window.

## Current Status

- Primary backend: FastAPI in `app/api/`
- Primary frontend: Next.js App Router in `frontend/`
- Temporary internal client: Streamlit in `app/ui/`
- Active web API surface: `/api/v2/*`

## Architecture

```text
User Message -> PromptGuard -> MemoryRetriever -> Planner -> Executor -> Conversation -> Response
```

- Frontend: `frontend/` contains the App Router shell for chat, memory, planner, diagnostics, settings, and profile.
- Backend: `app/api/main.py` mounts diagnostics plus the v2 contract used by the web client.
- Orchestrator: `app/orchestrator/agent.py` routes chat through memory retrieval, planning, execution, and conversation generation.
- Router: `services/ai_router.py` handles GGUF, Ollama, OpenAI, Grok, and Gemini fallback logic.
- Memory: `app/memory/store.py` abstracts PostgreSQL, pgvector, Chroma, and SQLite fallback behavior.
- Security: `app/orchestrator/security/` contains prompt guarding and approval flows.

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 20+
- Git

### Installation

```powershell
git clone https://github.com/RainCodeAI/Joi.git
cd Joi/personal-agent

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd frontend
npm install
cd ..
```

### Configuration

```powershell
copy .env.example .env
copy frontend\.env.example frontend\.env.local
```

Important backend variables live in `.env`. The frontend defaults to `http://127.0.0.1:8000` and can be overridden with `NEXT_PUBLIC_API_BASE_URL`.

## Run Joi

### Primary Web Stack

Terminal 1:

```powershell
$env:JOI_API_TOKEN="replace-with-a-long-random-token"
uvicorn app.api.main:app --reload
```

Terminal 2:

```powershell
cd frontend
$env:NEXT_PUBLIC_JOI_API_TOKEN=$env:JOI_API_TOKEN
npm run dev
```

Open:

- Next.js UI: [http://localhost:3000](http://localhost:3000)
- FastAPI: [http://localhost:8000](http://localhost:8000)

### Temporary Migration Overlap

Run the legacy internal client only when validating parity against the same backend:

```powershell
streamlit run app/ui/app.py
```

Open:

- Streamlit internal client: [http://localhost:8501](http://localhost:8501)

### Desktop Tray App

The native tray launcher starts the local API and Next.js UI, passes the local API token to both processes, and opens Joi in a native desktop shell when both services are ready:

```powershell
.\StartJoiNative.bat
```

The desktop shell uses `pywebview` to wrap the existing Next.js UI. If `pywebview` is not installed, Joi falls back to the default browser. Window size, position, always-on-top, and start-minimized preferences are stored in `data/desktop_shell.json`.

When the desktop shell is open, hold `Ctrl+Shift+Space` to record a short voice prompt and release to transcribe it. With `Voice sends` enabled, a clean voice prompt sends automatically; if there is already draft text or an attachment, Joi appends the transcript for review. Press `Esc` to cancel an active recording or interrupt voice playback. The same hotkeys also work while the web UI has focus.

You can also run the tray launcher directly:

```powershell
python desktop/tray_app.py
```

Open only the desktop shell against an already-running frontend:

```powershell
python desktop/window_shell.py --url http://localhost:3000
```

Or use `StartJoiLegacy.bat` only when validating the legacy internal client.

### Safe Desktop Actions

Phase 4 has started with a narrow local desktop action broker. The current allowlist is limited to `open_url` and `show_notification`, both require explicit confirmation through the API, and every attempt is written to `data/desktop_action_audit.jsonl`.

## Docker

The containerized default now targets the FastAPI backend instead of Streamlit.

```bash
docker-compose up --build
```

This starts:

- Joi API on port `8000`
- PostgreSQL with pgvector on port `5432`
- ChromaDB on port `8001` on the host (`8000` inside the compose network)

Run the Next.js frontend locally against that backend during the migration window:

```powershell
cd frontend
npm run dev
```

## API

Legacy routes still exist, but the active web client uses the v2 surface:

- `/api/v2/sessions`
- `/api/v2/chat`
- `/api/v2/approvals`
- `/api/v2/events/stream`
- `/api/v2/memory/*`
- `/api/v2/planner/*`
- `/api/v2/profile*`
- `/api/v2/settings`
- `/diagnostics/runtime`

## Migration Window

During Sprint 2.3:

- Next.js is the primary client for feature work.
- Streamlit stays available only for controlled comparison and parity checks.
- Both clients point at the same FastAPI backend.
- Streamlit should be removed from the default launch path once parity is signed off.

Detailed migration notes live in [docs/phase2_migration_window.md](docs/phase2_migration_window.md).

## Troubleshooting

- If `pytest` does not run, check which Python interpreter your virtual environment points to.
- If the frontend cannot reach the API, confirm `NEXT_PUBLIC_API_BASE_URL` matches the backend host and port.
- If voice or tray features fail, use the web stack first; those paths still depend on legacy components during migration.
- If running without PostgreSQL, leave `DATABASE_URL` blank to fall back to SQLite.

## License

MIT. See [LICENSE](LICENSE).

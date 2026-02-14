# Joi — Tonight's Roadmap

*Drafted 2026-02-13 · From Grok brainstorm session*

---

## Phase 1: Fortify & Restructure — *Tonight / Quick Wins*
> 🤖 **Recommended: Gemini** — Strong at architectural refactoring, code splitting, and security pattern implementation. Gemini's large context window makes it ideal for reading the full `agent.py` monolith and restructuring it into sub-agents in one pass.

### 1. Modularize the Orchestrator into Sub-Agents
Break `agent.py` (currently a 400-line monolith) into focused sub-agents:
- **Planner Agent** — Task breakdown, scheduling, goal tracking
- **Memory Retriever Agent** — RAG search, graph traversal, context assembly
- **Executor Agent** — Tool dispatch (email, calendar, file ops)
- **Conversation Agent** — Chat, sentiment, persona filtering

Use **LangGraph** or **CrewAI** for safe workflow graphs — prevents unchecked chains and gives you visual debugging of agent decision trees.

### 2. Bake in Security
- **Sandbox tools**: Wrap tool executions in Docker subprocesses or restricted namespaces (e.g., `subprocess` with `chroot`/jail on Linux/Mac).
- **Prompt guards**: Add input filters in `agent.py` to scrub for injections — regex + custom validators before anything hits the LLM.
- **Human-in-the-Loop**: For any write/action (calendar add, email send, file write), require explicit UI confirmation via Streamlit callbacks. No silent side-effects.

### 3. Enhanced Audit Logging
- Extend the new Diagnostics log streaming (Sprint 3) to also stream **agent decision traces** — which sub-agent was invoked, what context was assembled, what the LLM returned
- Goal: spot hallucinations and bad tool calls early

### 4. Baseline Benchmark
- Run query performance benchmarks *before* making changes (the Diagnostics "Run Benchmarks" button is ready from Sprint 2)
- Record baseline numbers to measure improvement

---

## Phase 2: Proactive Autonomy — *Next Few Hours/Days*
> 🤖 **Recommended: Claude** — Excels at nuanced design decisions, careful API integration, and writing empathetic/personality-tuned prompts. Claude's strength in reasoning makes it the better fit for designing negotiate flows and fine-tuning emotional dialogue.

### 5. Heartbeat Mode
Use `APScheduler` in the backend for unprompted agent actions:
- Daily mood check-in
- "Low sleep trend" reminders
- Habit streak nudges
- Overdue contact pings

Tie to existing Postgres data (`moodentry`, `sleep_log`, `habit`, `contacts`) for personalization.

### 6. Safe Tool Integration ("OpenClaw-Like")
- Read-only Gmail/Calendar via OAuth — confirm every action
- Add **negotiate flows**: Joi suggests → you approve/deny → then execute
- Never auto-execute writes without human confirmation

### 7. Empathy & Voice Fine-Tuning
- Fine-tune the LLM for Joi's personality using **LoRA on Llama** with custom emotional dialogue datasets
- Make Joi's responses feel genuinely empathetic, not template-driven

---

## Phase 3: Wild Expansions — *Ongoing*
> 🤖 **Recommended: Split** — **Gemini** for Docker/infra (containerization, CLIP vision integration) · **Claude** for UX-facing work (ElevenLabs voice polish, ethical guardrails design, self-improvement feedback loops)

### 8. Multi-Modal Joi
- **Vision**: Integrate CLIP for photo descriptions, image-based context
- **Premium Voice**: Upgrade to ElevenLabs for cinematic TTS quality (replaces `pyttsx3`)
- Build on existing avatar system with actual rendered PNGs + real phoneme-aligned audio

### 9. Self-Improvement Loop
- Safe learning: Track interaction feedback in ChromaDB ("Did that help? Yes/No")
- Adjust response weights and context retrieval based on feedback
- Never retrain on raw user data without explicit consent

### 10. Deployment & Containerization
- Docker Compose for the full stack: Streamlit + FastAPI + PostgreSQL + ChromaDB
- One-command setup: `docker-compose up`
- Easy portability across machines

### 11. Ethical Guardrails
- Config toggles in Settings for **autonomy level**:
  - **Low**: Reactive only — Joi responds, never initiates
  - **Medium**: Proactive suggestions, but always asks first
  - **High**: Proactive actions with post-hoc notifications
- User controls the boundary at all times

---

## Quick Reference: What Exists vs. What's New

| Feature | Status | Phase |
|---------|--------|-------|
| Sub-agent modularization | 🆕 New | 1 |
| Tool sandboxing | 🆕 New | 1 |
| Prompt injection guards | 🆕 New | 1 |
| Human-in-the-loop confirms | 🆕 New | 1 |
| Agent decision trace logs | 🔧 Extend Sprint 3 log streaming | 1 |
| Query benchmarks | ✅ Done (Diagnostics page) | 1 |
| APScheduler heartbeat | 🆕 New | 2 |
| OAuth Gmail/Calendar | 🔧 Partially wired (Settings) | 2 |
| LoRA fine-tuning | 🆕 New | 2 |
| CLIP vision | 🆕 New | 3 |
| ElevenLabs TTS | 🆕 New | 3 |
| Docker Compose | 🆕 New | 3 |
| Autonomy level config | 🆕 New | 3 |

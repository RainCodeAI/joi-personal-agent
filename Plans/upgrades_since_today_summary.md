# Upgrades Added Since today_summary.md

This document summarizes all major upgrades and features implemented in Joi since the creation of `today_summary.md`. These enhancements build on the core EI, memory, and UI foundations, making Joi more intelligent, proactive, and user-friendly.

## 1. Personal Knowledge Graphs (PKGs) - Semantic Memory Enhancement
- **Description**: Implemented entity extraction and storage for contextual recall, inspired by Kin AI and PKGs research. Joi now extracts persons, places, organizations, and concepts from user inputs and stores them with embeddings.
- **Implementation**:
  - Added `Entity` and `Relationship` DB models with vector support.
  - Ollama-powered NER (Named Entity Recognition) in `store.py`.
  - Auto-memory addition for user chats to trigger extraction.
  - Alembic migration for new tables.
- **Impact**: Enables queries like "Who was my dentist?" by linking personal data. Differentiates semantic (facts) from episodic (events) memory.
- **Files Modified**: `app/api/models.py`, `app/memory/store.py`, `app/orchestrator/agent.py`, alembic migration.
- **Status**: Core implemented; ready for relationship linking and Graph-RAG.

## 2. Reclaim-Like Time Blocking & Day Planner
- **Description**: Added a proactive day planning feature, generating time-blocked schedules from habits, goals, and tasks, synced to Google Calendar.
- **Implementation**:
  - New `Planner` page in Streamlit with input fields for tasks/focus/energy.
  - Ollama generates realistic plans based on user data.
  - Calendar sync via existing GCal tools.
- **Impact**: Turns Joi into a life coach for productivity, adapting plans to mood/energy levels.
- **Files Modified**: New `app/ui/pages/Planner.py`, updated `app/ui/App.py`.
- **Status**: Fully functional; integrates with habits/goals.

## 3. Weekly Mood Orb Summaries
- **Description**: Visualized mood tracking with colored "orbs" for each day of the week, inspired by Tochi app.
- **Implementation**:
  - Added mood orb display in `Stats` page using Streamlit markdown with colors.
  - Pulls from existing mood DB, shows average and daily trends.
- **Impact**: Makes EI tangible, encourages mood logging with gamified visuals.
- **Files Modified**: `app/ui/pages/Stats.py`.
- **Status**: Live; enhances Stats dashboard.

## 4. Diagnostics Page & Health Checks
- **Description**: Added an ops dashboard for monitoring Joi's health, DB status, and performance.
- **Implementation**:
  - New `Diagnostics` page with DB connectivity, extension checks, row counts, ANALYZE button.
  - Health checks for DB, Ollama, Chroma.
  - Alembic .env integration for dynamic DB URLs.
- **Impact**: Enables troubleshooting and maintenance without diving into code.
- **Files Modified**: New `app/ui/pages/Diagnostics.py`, updated `app/ui/App.py`, `db_migrations/env.py`.
- **Status**: Complete; essential for production monitoring.

## 5. Memory Split: Semantic vs. Episodic
- **Description**: Enhanced memory system to tag and prioritize semantic (facts) vs. episodic (personal events) memories, per Kin AI model.
- **Implementation**:
  - Added `memory_type` field to `Memory` model.
  - Tagging logic in `add_memory` (semantic for entities, episodic for chats).
  - Updated search to filter by type.
- **Impact**: Makes recall more nuanced—semantic for knowledge, episodic for storytelling.
- **Files Modified**: `app/api/models.py`, `app/memory/store.py`, alembic migration.
- **Status**: Implemented; search adjustments ready for use.

## 6. Avatar 2.5D with Lip-Sync & Expressions
- **Description**: Implemented layered 2.5D avatar with phoneme-based lip-sync, sentiment-driven expressions, and idle animations.
- **Implementation**:
  - `settings.yaml` for config.
  - `avatar_controller.py` for layer swapping and animations.
  - Extended `agent.py` with `say_and_sync` using Piper TTS and Rhubarb lip-sync.
  - New `Avatar Demo` page in UI.
- **Impact**: Makes Joi visually engaging, with empathetic expressions tied to mood.
- **Files Modified**: New `app/ui/avatar/` folder, `app/ui/pages/Avatar.py`, `app/orchestrator/agent.py`.
- **Status**: Functional with dummy TTS; full voice integration pending.

## 7. Enhanced EI & Proactive Features (Ongoing)
- **Description**: Built on existing CBT, mood tracking, habits, decisions, and proactive nudges (reminders, check-ins, causal insights).
- **Implementation**: Integrated DB mood for avatar expressions, causal analysis for habit-mood correlations.
- **Impact**: Joi adapts tone/personality, provides therapeutic support, and nudges for health/productivity.
- **Files Modified**: Various in `app/orchestrator/agent.py`, `app/memory/store.py`.
- **Status**: Core EI solid; ongoing refinements.

## Technical Stack Upgrades
- **DB**: Switched to Postgres with pgvector for embeddings; added vector search.
- **Memory**: Chroma for embeddings, now with PKGs and type differentiation.
- **UI**: Streamlit with new pages (Planner, Diagnostics, Avatar); dark theme polish.
- **AI**: Ollama for chat/embed/NER; integrations with Piper/Rhubarb for voice/avatar.
- **Tools**: Enhanced email/calendar, added health checks.

## Next Priorities (From ChatGPT Breakdown)
- **Relationship Linking**: Auto-link entities in PKGs (e.g., "visited" between person/place).
- **Graph-RAG**: Vector + relationship queries for contextual answers.
- **Multi-AI Integration**: Fallback to X.AI/OpenAI/Claude for smarter responses.
- **Advanced Lip-Sync**: MuseTalk for real-time, multi-lingual avatars.
- **UI Polish**: Mobile layout, export features.

These upgrades transform Joi from a basic AI companion to a sophisticated, context-aware personal agent. Each builds on the previous, maintaining privacy and ethical design.

*Last Updated: 2025-09-29*

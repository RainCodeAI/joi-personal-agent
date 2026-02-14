# Joi Database Specifications

## Overview
Joi's database has been migrated from SQLite to PostgreSQL for better stability, scalability, and advanced features like vector embeddings (pgvector). This ensures no more schema errors when adding new fields (e.g., humor_level).

## Database Details
- **Database Type**: PostgreSQL 17 (via Postgres.app)
- **Host**: 127.0.0.1
- **Port**: 5454
- **Database Name**: joi_db
- **Username**: joi_user
- **Password**: JoiDBSecure!2024 (rotated for security; stored only in .env)
- **Connection URL**: postgresql+asyncpg://joi_user:JoiDBSecure%212024@127.0.0.1:5454/joi_db
- **Driver**: asyncpg for async operations; psycopg[binary] for sync scripts

## Key Features
- **Tables**: User profiles, chat messages, memories (with embeddings), feedback, milestones, mood entries, habits, decisions, goals, activity logs, CBT exercises.
- **Extensions**: 
  - uuid-ossp (for UUIDs if needed)
  - vector (for pgvector embeddings, 1536 dimensions matching Ollama's nomic-embed-text)
- **Migrations**: Handled via Alembic (init schema applied).
- **Backups**: Regular backups recommended; rollback via Alembic downgrade.

## Migration Notes
- **From SQLite**: Script `scripts/migrate_sqlite_to_pg.py` for transferring old data.
- **Embeddings**: Currently using ChromaDB; future: switch to pgvector for native vector search.
- **Permissions**: joi_user has CREATE on public schema for tables; superuser (postgres) for extensions.

## Environment Setup
- Update `.env` with `DATABASE_URL=postgresql+psycopg://joi_user:Tup%40c9933@127.0.0.1:5454/joi_db`
- Alembic config in `alembic.ini` for migrations.

## Testing Connection
Run: `psql -h 127.0.0.1 -p 5454 -U joi_user -d joi_db -c "SELECT NOW();"`
Or in app: `python -c "from app.memory.store import MemoryStore; MemoryStore(); print('Connected')"`

## Future Enhancements
- Async queries with asyncpg.
- Vector indexing for faster similarity searches.
- Encrypted fields via pgcrypto.

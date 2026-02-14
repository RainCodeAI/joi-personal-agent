import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine as create_sync_engine
from app.models import Base, MemoryItem  # import all models you need

SQLITE_URL = "sqlite:///./data/agent.db"    # your old path
PG_URL     = "postgresql+asyncpg://joi_user:Tup@c9933@127.0.0.1:5454/joi_db"

def load_sqlite_rows():
    from sqlalchemy.orm import Session
    eng = create_sync_engine(SQLITE_URL)
    with Session(eng) as s:
        return s.query(MemoryItem).all()

async def main():
    pg_engine = create_async_engine(PG_URL, pool_pre_ping=True)
    async with AsyncSession(pg_engine) as session:
        rows = load_sqlite_rows()
        for r in rows:
            item = MemoryItem(
                kind=r.kind,
                text=r.text,
                tags=r.tags,
                priority=r.priority,
                last_accessed=r.last_accessed,
                created_at=r.created_at,
                embedding=r.embedding,  # ensure it’s stored as a Python list/np.ndarray of floats
            )
            session.add(item)
        await session.commit()
    await pg_engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())

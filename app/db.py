import logging
import time
from os import getenv
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# OS env var wins; fall back to .env via pydantic settings (os.getenv alone
# misses .env because pydantic-settings does not export into os.environ).
DATABASE_URL = getenv("DATABASE_URL") or settings.database_url

_engine: Optional[AsyncEngine] = None
_session_factory = None

_MAX_RETRIES = 3
_RETRY_DELAY = 2.0


def _build_engine() -> Optional[AsyncEngine]:
    if not DATABASE_URL:
        logger.warning("DATABASE_URL not set — async DB engine disabled")
        return None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            eng = create_async_engine(
                DATABASE_URL,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
            )
            logger.info("Async DB engine created (attempt %d)", attempt)
            return eng
        except Exception as exc:
            logger.warning("DB engine creation failed (attempt %d/%d): %s", attempt, _MAX_RETRIES, exc)
            if attempt < _MAX_RETRIES:
                time.sleep(_RETRY_DELAY * attempt)
    logger.error("DB engine could not be created after %d attempts — running without async DB", _MAX_RETRIES)
    return None


engine = _build_engine()

if engine is not None:
    AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
else:
    AsyncSessionLocal = None


async def get_session() -> Optional[AsyncSession]:
    if AsyncSessionLocal is None:
        logger.warning("get_session called but DB is unavailable")
        yield None
        return
    async with AsyncSessionLocal() as session:
        yield session

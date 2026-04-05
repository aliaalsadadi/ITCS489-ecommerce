from collections.abc import AsyncGenerator

from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()


def _as_async_database_url(raw_url: str) -> str:
    if raw_url.startswith("postgresql+asyncpg://"):
        return raw_url
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("postgres://"):
        return raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw_url


def _engine_kwargs(database_url: str) -> dict:
    kwargs: dict = {"pool_pre_ping": True}

    # Supabase transaction pooler runs through PgBouncer, which is incompatible
    # with asyncpg prepared statements unless statement caching is disabled.
    if ".pooler.supabase.com" in database_url:
        kwargs["connect_args"] = {"statement_cache_size": 0}
        kwargs["poolclass"] = NullPool

    return kwargs


database_url = _as_async_database_url(settings.database_url)
engine = create_async_engine(database_url, **_engine_kwargs(database_url))
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

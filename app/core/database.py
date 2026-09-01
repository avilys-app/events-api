"""Engine, session factory, and declarative base."""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def supabase_pooler_connect_args() -> dict[str, Any]:
    """Return asyncpg options compatible with transaction-mode PgBouncer."""
    return {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    }


_settings = get_settings()

engine_options: dict[str, Any] = {
    "echo": _settings.echo_sql,
    "pool_pre_ping": True,
}

if _settings.uses_supabase_pooler:
    # Supabase transaction pooling can move a client connection to another
    # PostgreSQL backend between transactions. Prepared statements cached on
    # the previous backend then cease to exist. Disable both asyncpg caches,
    # use collision-free statement names, and let Supabase own the pooling.
    engine_options.update(
        poolclass=NullPool,
        pool_pre_ping=False,
        connect_args=supabase_pooler_connect_args(),
    )

engine = create_async_engine(
    str(_settings.database_dsn),
    **engine_options,
)

session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a session per request, rolling back if the handler raises."""
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

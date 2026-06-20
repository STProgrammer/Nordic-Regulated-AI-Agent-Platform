"""Lazy async SQLAlchemy engine and request-session construction."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import AppSettings, get_settings

_engines: dict[str, AsyncEngine] = {}
_sessionmakers: dict[str, async_sessionmaker[AsyncSession]] = {}


def get_async_engine(settings: AppSettings | None = None) -> AsyncEngine:
    """Build or return the async engine without opening a database connection."""

    resolved_settings = settings if settings is not None else get_settings()
    database_url = resolved_settings.database_async_url()
    engine = _engines.get(database_url)
    if engine is None:
        engine = create_async_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=resolved_settings.database_pool_size,
            max_overflow=resolved_settings.database_max_overflow,
        )
        _engines[database_url] = engine
    return engine


def get_sessionmaker(settings: AppSettings | None = None) -> async_sessionmaker[AsyncSession]:
    """Return the single async-session construction path used by the API."""

    resolved_settings = settings if settings is not None else get_settings()
    database_url = resolved_settings.database_async_url()
    sessionmaker = _sessionmakers.get(database_url)
    if sessionmaker is None:
        sessionmaker = async_sessionmaker(
            get_async_engine(resolved_settings),
            class_=AsyncSession,
            expire_on_commit=False,
        )
        _sessionmakers[database_url] = sessionmaker
    return sessionmaker


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield one transaction-aware session for future route/service dependencies."""

    async with get_sessionmaker()() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()


async def dispose_database_engines() -> None:
    """Dispose lazily-created pools during process shutdown and isolated tests."""

    engines = tuple(_engines.values())
    _engines.clear()
    _sessionmakers.clear()
    for engine in engines:
        await engine.dispose()

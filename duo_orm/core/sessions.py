"""Session factories and context helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from .exceptions import AsyncNotConfiguredError


def make_sync_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build the sync session factory."""

    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def make_async_session_factory(async_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build the async session factory."""

    return async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


@contextmanager
def standalone_session(
    session_factory: sessionmaker[Session],
) -> Iterator[Session]:
    """Yield a direct SQLAlchemy session."""

    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@asynccontextmanager
async def astandalone_session(
    session_factory: async_sessionmaker[AsyncSession] | None,
) -> AsyncIterator[AsyncSession]:
    """Yield a direct async SQLAlchemy session."""

    if session_factory is None:
        raise AsyncNotConfiguredError(
            "Async APIs are unavailable because this Database was created with "
            "derive_async=False."
        )

    session = session_factory()
    try:
        yield session
    finally:
        await session.close()


@contextmanager
def transaction(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a sync session inside a transaction."""

    with standalone_session(session_factory) as session:
        with session.begin():
            yield session


@asynccontextmanager
async def atransaction(
    session_factory: async_sessionmaker[AsyncSession] | None,
) -> AsyncIterator[AsyncSession]:
    """Yield an async session inside a transaction."""

    async with astandalone_session(session_factory) as session:
        async with session.begin():
            yield session

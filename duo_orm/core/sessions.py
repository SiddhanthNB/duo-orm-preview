"""Session factories and context helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextvars import ContextVar
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from .exceptions import AsyncNotConfiguredError, NestedTransactionError


_SYNC_SESSIONS: ContextVar[dict[int, Session]] = ContextVar(
    "duo_orm_sync_sessions",
    default={},
)
_ASYNC_SESSIONS: ContextVar[dict[int, AsyncSession]] = ContextVar(
    "duo_orm_async_sessions",
    default={},
)


def make_sync_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build the sync session factory."""

    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def make_async_session_factory(async_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Build the async session factory."""

    return async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


def get_current_sync_session(scope_key: Any) -> Session | None:
    """Return the ambient sync session for the current context."""

    return _SYNC_SESSIONS.get().get(id(scope_key))


def get_current_async_session(scope_key: Any) -> AsyncSession | None:
    """Return the ambient async session for the current context."""

    return _ASYNC_SESSIONS.get().get(id(scope_key))


def standalone_session(
    session_factory: sessionmaker[Session],
) -> Session:
    """Return a direct SQLAlchemy session."""

    return session_factory()


def astandalone_session(
    session_factory: async_sessionmaker[AsyncSession] | None,
) -> AsyncSession:
    """Return a direct async SQLAlchemy session."""

    if session_factory is None:
        raise AsyncNotConfiguredError(
            "Async APIs are unavailable because this Database was created with "
            "derive_async=False."
        )

    return session_factory()


@contextmanager
def transaction(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a sync session inside a transaction."""

    session = standalone_session(session_factory)
    try:
        with session.begin():
            yield session
    finally:
        session.close()


@asynccontextmanager
async def atransaction(
    session_factory: async_sessionmaker[AsyncSession] | None,
) -> AsyncIterator[AsyncSession]:
    """Yield an async session inside a transaction."""

    session = astandalone_session(session_factory)
    try:
        async with session.begin():
            yield session
    finally:
        await session.close()


@contextmanager
def ambient_transaction(
    scope_key: Any,
    session_factory: sessionmaker[Session],
) -> Iterator[Session]:
    """Yield a sync session and register it as the ambient Duo-ORM session."""

    current = _SYNC_SESSIONS.get()
    key = id(scope_key)
    if key in current:
        raise NestedTransactionError(
            "Nested `db.transaction()` calls are not supported in the same context."
        )

    session = standalone_session(session_factory)
    try:
        token = _SYNC_SESSIONS.set({**current, key: session})
        try:
            with session.begin():
                yield session
        finally:
            _SYNC_SESSIONS.reset(token)
    finally:
        session.close()


@asynccontextmanager
async def ambient_atransaction(
    scope_key: Any,
    session_factory: async_sessionmaker[AsyncSession] | None,
) -> AsyncIterator[AsyncSession]:
    """Yield an async session and register it as the ambient Duo-ORM session."""

    if session_factory is None:
        raise AsyncNotConfiguredError(
            "Async APIs are unavailable because this Database was created with "
            "derive_async=False."
        )

    current = _ASYNC_SESSIONS.get()
    key = id(scope_key)
    if key in current:
        raise NestedTransactionError(
            "Nested `db.atransaction()` calls are not supported in the same context."
        )

    session = astandalone_session(session_factory)
    try:
        token = _ASYNC_SESSIONS.set({**current, key: session})
        try:
            async with session.begin():
                yield session
        finally:
            _ASYNC_SESSIONS.reset(token)
    finally:
        await session.close()

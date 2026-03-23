"""Engine construction helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.engine import Engine

from .exceptions import DuoORMError

_POSTGRES_DRIVER = "postgresql+psycopg"


def normalize_database_url(url: str) -> URL:
    """Validate the user-facing URL and inject the psycopg driver."""

    parsed = make_url(url)
    if not parsed.drivername.startswith("postgresql"):
        raise DuoORMError(
            "Duo-ORM only supports PostgreSQL URLs such as "
            "'postgresql://user:pass@host/dbname'."
        )

    return parsed.set(drivername=_POSTGRES_DRIVER)


def create_sync_engine(url: str, engine_kwargs: Mapping[str, Any] | None = None) -> Engine:
    """Create the sync SQLAlchemy engine."""

    normalized = normalize_database_url(url)
    return create_engine(normalized, **dict(engine_kwargs or {}))


def create_async_engine_for_url(
    url: str, engine_kwargs: Mapping[str, Any] | None = None
) -> AsyncEngine:
    """Create the async SQLAlchemy engine."""

    normalized = normalize_database_url(url)
    return create_async_engine(normalized, **dict(engine_kwargs or {}))

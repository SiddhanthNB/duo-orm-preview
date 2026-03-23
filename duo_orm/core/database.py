"""Database object for Duo-ORM."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.sql import Executable

from .engines import create_async_engine_for_url, create_sync_engine
from .model import create_model_base
from .sessions import (
    astandalone_session as make_astandalone_session,
    atransaction as make_atransaction,
    make_async_session_factory,
    make_sync_session_factory,
    standalone_session as make_standalone_session,
    transaction as make_transaction,
)


class Database:
    """Owns engines, sessions, and an isolated model base."""

    def __init__(
        self,
        url: str,
        *,
        engine_kwargs: Mapping[str, Any] | None = None,
        derive_async: bool = True,
    ) -> None:
        self.url = url
        self.engine_kwargs = dict(engine_kwargs or {})
        self.sync_engine = create_sync_engine(url, self.engine_kwargs)
        self.async_engine = (
            create_async_engine_for_url(url, self.engine_kwargs) if derive_async else None
        )
        self._sync_session_factory = make_sync_session_factory(self.sync_engine)
        self._async_session_factory = (
            make_async_session_factory(self.async_engine) if self.async_engine is not None else None
        )
        self.Model = create_model_base(self)

    def standalone_session(self) -> Any:
        return make_standalone_session(self._sync_session_factory)

    def transaction(self) -> Any:
        return make_transaction(self._sync_session_factory)

    def astandalone_session(self) -> Any:
        return make_astandalone_session(self._async_session_factory)

    def atransaction(self) -> Any:
        return make_atransaction(self._async_session_factory)

    def execute(self, statement: Executable, params: Mapping[str, Any] | None = None) -> Any:
        """Execute raw SQL or SQLAlchemy statements synchronously."""

        with self.transaction() as session:
            result = session.execute(statement, params or {})
            if result.returns_rows:
                return list(result.fetchall())
            return result.rowcount

"""Duo-ORM-specific exceptions."""


class DuoORMError(Exception):
    """Base exception for Duo-ORM policy and usage errors."""


class AsyncNotConfiguredError(DuoORMError):
    """Raised when async APIs are used on a sync-only Database."""


class InvalidJoinError(DuoORMError):
    """Raised when a join violates Duo-ORM join rules."""


class PaginationJoinError(DuoORMError):
    """Raised when pagination is attempted on a joined query."""


class QueryScopeError(DuoORMError):
    """Raised when a query references tables outside the current scope."""


class UnsupportedExpressionError(DuoORMError):
    """Raised when a helper expression is used outside supported semantics."""


class ReservedModelAttributeError(DuoORMError):
    """Raised when a model declares a SQLAlchemy-reserved attribute name."""

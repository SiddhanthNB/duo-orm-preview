"""Non-terminal query builder methods."""

from __future__ import annotations

from typing import Any

from .exceptions import PaginationJoinError
from .query_validation import validate_join_kind


def where(builder: Any, *predicates: Any) -> Any:
    """Add predicates to the query state."""

    return builder._clone(predicates=builder.predicates + tuple(predicates))


def join(builder: Any, target: type[Any], *, on: Any, kind: str = "inner") -> Any:
    """Add a join to the query state."""

    validate_join_kind(kind)
    join_spec = builder.JoinSpec(target=target, onclause=on, kind=kind)
    return builder._clone(
        joins=builder.joins + (join_spec,),
        has_join=True,
    )


def order_by(builder: Any, *ordering: str) -> Any:
    """Add root-model ordering tokens."""

    return builder._clone(ordering=builder.ordering + tuple(ordering))


def limit(builder: Any, value: int) -> Any:
    """Apply a limit to the query."""

    _ensure_joinless_pagination(builder)
    return builder._clone(limit_value=value)


def offset(builder: Any, value: int) -> Any:
    """Apply an offset to the query."""

    _ensure_joinless_pagination(builder)
    return builder._clone(offset_value=value)


def paginate(builder: Any, *, limit: int, offset: int) -> Any:
    """Convenience wrapper for limit and offset."""

    _ensure_joinless_pagination(builder)
    return builder._clone(limit_value=limit, offset_value=offset)


def _ensure_joinless_pagination(builder: Any) -> None:
    if builder.has_join:
        raise PaginationJoinError(
            "Pagination is blocked once join() is used because joined queries "
            "can duplicate root rows. Use .alchemize() for advanced joined pagination."
        )

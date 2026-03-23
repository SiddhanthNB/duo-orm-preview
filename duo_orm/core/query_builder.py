"""QueryBuilder state container and method surface."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from . import query_shapers, query_terminals


@dataclass(frozen=True)
class JoinSpec:
    """Stored join metadata for query compilation."""

    target: type[Any]
    onclause: Any
    kind: str


@dataclass(frozen=True)
class QueryBuilder:
    """Fluent query builder rooted on a single model."""

    root_model: type[Any]
    database: Any
    predicates: tuple[Any, ...] = ()
    joins: tuple[JoinSpec, ...] = ()
    ordering: tuple[str, ...] = ()
    limit_value: int | None = None
    offset_value: int | None = None
    has_join: bool = False

    JoinSpec = JoinSpec

    def _clone(self, **changes: Any) -> "QueryBuilder":
        return replace(self, **changes)

    def where(self, *predicates: Any) -> "QueryBuilder":
        return query_shapers.where(self, *predicates)

    def join(self, target: type[Any], *, on: Any, kind: str = "inner") -> "QueryBuilder":
        return query_shapers.join(self, target, on=on, kind=kind)

    def order_by(self, *ordering: str) -> "QueryBuilder":
        return query_shapers.order_by(self, *ordering)

    def limit(self, value: int) -> "QueryBuilder":
        return query_shapers.limit(self, value)

    def offset(self, value: int) -> "QueryBuilder":
        return query_shapers.offset(self, value)

    def paginate(self, *, limit: int, offset: int) -> "QueryBuilder":
        return query_shapers.paginate(self, limit=limit, offset=offset)

    def exec(self) -> list[Any]:
        return query_terminals.exec_query(self)

    async def aexec(self) -> list[Any]:
        return await query_terminals.aexec_query(self)

    def count(self) -> int:
        return query_terminals.count_query(self)

    async def acount(self) -> int:
        return await query_terminals.acount_query(self)

    def update(self, **fields: Any) -> int:
        return query_terminals.update_query(self, **fields)

    async def aupdate(self, **fields: Any) -> int:
        return await query_terminals.aupdate_query(self, **fields)

    def delete(self) -> int:
        return query_terminals.delete_query(self)

    async def adelete(self) -> int:
        return await query_terminals.adelete_query(self)

    def alchemize(self) -> Any:
        return query_terminals.build_select_statement(self)

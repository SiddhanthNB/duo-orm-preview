"""Validation helpers for query compilation."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.sql import visitors
from sqlalchemy.sql.schema import Table
from sqlalchemy.sql.selectable import FromClause

from .exceptions import InvalidJoinError, QueryScopeError

VALID_JOIN_KINDS = {"inner", "left"}


def validate_join_kind(kind: str) -> None:
    """Reject unsupported join kinds."""

    if kind not in VALID_JOIN_KINDS:
        raise InvalidJoinError(
            "Duo-ORM only supports 'inner' and 'left' joins in core. "
            "Use .alchemize() for more advanced join shapes."
        )


def validate_query_scope(builder: Any) -> None:
    """Ensure predicates and join clauses only reference tables in scope."""

    scope = {builder.root_model.__table__}
    scope.update(join.target.__table__ for join in builder.joins)

    clauses = list(builder.predicates)
    clauses.extend(join.onclause for join in builder.joins)

    for clause in clauses:
        referenced = referenced_tables(clause)
        if not referenced.issubset(scope):
            raise QueryScopeError(
                "This query references a table that is not in scope. "
                "Join the table explicitly before using it in predicates."
            )


def referenced_tables(clause: Any) -> set[Table]:
    """Collect real tables referenced by a SQLAlchemy clause."""

    tables: set[Table] = set()
    for element in visitors.iterate(clause):
        table = getattr(element, "table", None)
        if isinstance(table, Table):
            tables.add(table)
        elif isinstance(element, FromClause) and isinstance(element, Table):
            tables.add(element)
    return tables


def resolve_ordering(builder: Any) -> list[Any]:
    """Resolve ordering tokens to root-model columns."""

    resolved: list[Any] = []
    for raw in builder.ordering:
        direction = "asc"
        name = raw
        if raw.startswith("-"):
            direction = "desc"
            name = raw[1:]

        if name not in builder.root_model.__table__.c:
            raise QueryScopeError(
                f"Cannot order by '{raw}'. Core ordering only supports columns "
                "from the root model."
            )

        column = builder.root_model.__table__.c[name]
        resolved.append(column.desc() if direction == "desc" else column.asc())

    return resolved


def primary_key_columns(model: type[Any]) -> tuple[Any, ...]:
    """Return the model primary key columns."""

    columns = tuple(model.__mapper__.primary_key)
    if not columns:
        raise QueryScopeError("Models must define a primary key.")
    return columns


def validate_update_fields(model: type[Any], fields: Iterable[str]) -> None:
    """Ensure update fields belong to the root table."""

    root_columns = set(model.__table__.c.keys())
    invalid = sorted(set(fields) - root_columns)
    if invalid:
        raise QueryScopeError(
            "Update fields must belong to the root model table. "
            f"Invalid fields: {', '.join(invalid)}."
        )

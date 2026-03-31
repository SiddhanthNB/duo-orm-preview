"""Terminal query execution and statement builders."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, tuple_, update as sa_update

from .query_validation import (
    primary_key_columns,
    resolve_ordering,
    validate_query_scope,
    validate_update_fields,
)


def build_select_statement(builder: Any) -> Any:
    """Compile the current query builder state into a SQLAlchemy Select."""

    validate_query_scope(builder)

    statement = select(builder.root_model)
    for join in builder.joins:
        if join.kind == "inner":
            statement = statement.join(join.target, join.onclause)
        else:
            statement = statement.outerjoin(join.target, join.onclause)

    if builder.predicates:
        statement = statement.where(*builder.predicates)

    if builder.ordering:
        statement = statement.order_by(*resolve_ordering(builder))

    if builder.limit_value is not None:
        statement = statement.limit(builder.limit_value)

    if builder.offset_value is not None:
        statement = statement.offset(builder.offset_value)

    return statement


def build_count_statement(builder: Any) -> Any:
    """Compile a root-row count statement."""

    validate_query_scope(builder)

    if builder.has_join:
        pk_columns = primary_key_columns(builder.root_model)
        subquery = (
            build_select_statement(builder)
            .with_only_columns(*pk_columns)
            .order_by(None)
            .distinct()
            .subquery()
        )
        return select(func.count()).select_from(subquery)

    statement = select(func.count()).select_from(builder.root_model.__table__)
    if builder.predicates:
        statement = statement.where(*builder.predicates)
    return statement


def build_update_statement(builder: Any, **fields: Any) -> Any:
    """Compile a root-table update statement."""

    validate_query_scope(builder)
    validate_update_fields(builder.root_model, fields.keys())

    statement = sa_update(builder.root_model.__table__).values(**fields)
    if builder.has_join:
        statement = statement.where(_root_identity_in_subquery(builder))
    elif builder.predicates:
        statement = statement.where(*builder.predicates)
    return statement


def build_delete_statement(builder: Any) -> Any:
    """Compile a root-table delete statement."""

    validate_query_scope(builder)

    statement = sa_delete(builder.root_model.__table__)
    if builder.has_join:
        statement = statement.where(_root_identity_in_subquery(builder))
    elif builder.predicates:
        statement = statement.where(*builder.predicates)
    return statement


def exec_query(builder: Any) -> list[Any]:
    """Execute the query synchronously."""

    statement = build_select_statement(builder)
    session = builder.database._current_sync_session()
    if session is not None:
        result = session.execute(statement)
        scalars = result.scalars()
        if builder.has_join:
            scalars = scalars.unique()
        return list(scalars.all())

    session = builder.database.standalone_session()
    try:
        result = session.execute(statement)
        scalars = result.scalars()
        if builder.has_join:
            scalars = scalars.unique()
        return list(scalars.all())
    finally:
        session.close()


async def aexec_query(builder: Any) -> list[Any]:
    """Execute the query asynchronously."""

    statement = build_select_statement(builder)
    session = builder.database._current_async_session()
    if session is not None:
        result = await session.execute(statement)
        scalars = result.scalars()
        if builder.has_join:
            scalars = scalars.unique()
        return list(scalars.all())

    session = builder.database.astandalone_session()
    try:
        result = await session.execute(statement)
        scalars = result.scalars()
        if builder.has_join:
            scalars = scalars.unique()
        return list(scalars.all())
    finally:
        await session.close()


def count_query(builder: Any) -> int:
    """Count root rows synchronously."""

    statement = build_count_statement(builder)
    session = builder.database._current_sync_session()
    if session is not None:
        return int(session.execute(statement).scalar_one())

    session = builder.database.standalone_session()
    try:
        return int(session.execute(statement).scalar_one())
    finally:
        session.close()


async def acount_query(builder: Any) -> int:
    """Count root rows asynchronously."""

    statement = build_count_statement(builder)
    session = builder.database._current_async_session()
    if session is not None:
        result = await session.execute(statement)
        return int(result.scalar_one())

    session = builder.database.astandalone_session()
    try:
        result = await session.execute(statement)
        return int(result.scalar_one())
    finally:
        await session.close()


def update_query(builder: Any, **fields: Any) -> int:
    """Execute a set-based update synchronously."""

    statement = build_update_statement(builder, **fields)
    session = builder.database._current_sync_session()
    if session is not None:
        result = session.execute(statement)
        return result.rowcount or 0

    with builder.database.transaction() as session:
        result = session.execute(statement)
        return result.rowcount or 0


async def aupdate_query(builder: Any, **fields: Any) -> int:
    """Execute a set-based update asynchronously."""

    statement = build_update_statement(builder, **fields)
    session = builder.database._current_async_session()
    if session is not None:
        result = await session.execute(statement)
        return result.rowcount or 0

    async with builder.database.atransaction() as session:
        result = await session.execute(statement)
        return result.rowcount or 0


def delete_query(builder: Any) -> int:
    """Execute a set-based delete synchronously."""

    statement = build_delete_statement(builder)
    session = builder.database._current_sync_session()
    if session is not None:
        result = session.execute(statement)
        return result.rowcount or 0

    with builder.database.transaction() as session:
        result = session.execute(statement)
        return result.rowcount or 0


async def adelete_query(builder: Any) -> int:
    """Execute a set-based delete asynchronously."""

    statement = build_delete_statement(builder)
    session = builder.database._current_async_session()
    if session is not None:
        result = await session.execute(statement)
        return result.rowcount or 0

    async with builder.database.atransaction() as session:
        result = await session.execute(statement)
        return result.rowcount or 0


def _root_identity_in_subquery(builder: Any) -> Any:
    pk_columns = primary_key_columns(builder.root_model)
    matching_roots = (
        build_select_statement(builder)
        .with_only_columns(*pk_columns)
        .order_by(None)
        .distinct()
    )

    if len(pk_columns) == 1:
        return pk_columns[0].in_(matching_roots)

    return tuple_(*pk_columns).in_(matching_roots)

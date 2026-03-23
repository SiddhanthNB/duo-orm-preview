"""JSON and ARRAY helper expressions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import Boolean, Float, Integer, String, cast, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.sql import ColumnElement
from sqlalchemy.sql.expression import any_


@dataclass(frozen=True)
class JsonPath:
    """Wrapper around a JSON path expression."""

    expression: ColumnElement[Any]

    def __getitem__(self, key: str) -> "JsonPath":
        return JsonPath(self.expression[key])

    def __eq__(self, value: Any) -> ColumnElement[bool]:  # type: ignore[override]
        return self._comparison(value)

    def __ne__(self, value: Any) -> ColumnElement[bool]:  # type: ignore[override]
        return ~self._comparison(value)

    def equals(self, value: Any) -> ColumnElement[bool]:
        return self._comparison(value)

    def not_equals(self, value: Any) -> ColumnElement[bool]:
        return ~self._comparison(value)

    def is_null(self) -> ColumnElement[bool]:
        return self.expression.is_(None)

    def is_not_null(self) -> ColumnElement[bool]:
        return self.expression.is_not(None)

    def is_true(self) -> ColumnElement[bool]:
        return self.as_boolean().is_(True)

    def is_false(self) -> ColumnElement[bool]:
        return self.as_boolean().is_(False)

    def contains(self, fragment: Any) -> ColumnElement[bool]:
        return cast(self.expression, JSONB).contains(fragment)

    def has_key(self, key: str) -> ColumnElement[bool]:
        return cast(self.expression, JSONB).has_key(key)  # type: ignore[no-any-return]

    def as_integer(self) -> ColumnElement[int]:
        return cast(self.expression.as_string(), Integer)

    def as_float(self) -> ColumnElement[float]:
        return cast(self.expression.as_string(), Float)

    def as_boolean(self) -> ColumnElement[bool]:
        return cast(self.expression.as_string(), Boolean)

    def as_text(self) -> ColumnElement[str]:
        return self.expression.as_string()

    def _comparison(self, value: Any) -> ColumnElement[bool]:
        if isinstance(value, bool):
            return self.as_boolean().is_(value)
        if isinstance(value, int) and not isinstance(value, bool):
            return self.as_integer() == value
        if isinstance(value, float):
            return self.as_float() == value
        if isinstance(value, str):
            return self.as_text() == value
        return cast(self.expression, JSONB) == cast(value, JSONB)


@dataclass(frozen=True)
class ArrayExpression:
    """Wrapper around a PostgreSQL ARRAY column."""

    expression: ColumnElement[Any]

    def includes(self, value: Any) -> ColumnElement[bool]:
        return value == any_(self.expression)

    def includes_all(self, values: list[Any]) -> ColumnElement[bool]:
        return cast(self.expression, ARRAY(self.expression.type.item_type)).contains(values)

    def includes_any(self, values: list[Any]) -> ColumnElement[bool]:
        return cast(self.expression, ARRAY(self.expression.type.item_type)).overlap(values)

    def length(self) -> ColumnElement[int]:
        return func.cardinality(self.expression)

    def equals(self, values: list[Any]) -> ColumnElement[bool]:
        return self.expression == values

    def not_equals(self, values: list[Any]) -> ColumnElement[bool]:
        return self.expression != values


def json(column: ColumnElement[Any]) -> JsonPath:
    """Start a JSON helper expression chain."""

    return JsonPath(column)


def array(column: ColumnElement[Any]) -> ArrayExpression:
    """Start an ARRAY helper expression chain."""

    return ArrayExpression(column)

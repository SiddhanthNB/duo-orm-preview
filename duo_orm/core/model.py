"""Model base creation and CRUD methods."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, ClassVar, get_origin

from sqlalchemy import insert
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy.orm import DeclarativeMeta, Mapped, declarative_base, mapped_column
from sqlalchemy.orm.properties import MappedColumn

from .exceptions import ReservedModelAttributeError
from .query_builder import QueryBuilder

_CAMEL_TO_SNAKE_RE = re.compile(r"(?<!^)(?=[A-Z])")
_MISSING = object()
_RESERVED_MODEL_ATTRIBUTES = {"metadata"}


def create_model_base(database: Any) -> type[Any]:
    """Create an isolated declarative model base for a Database instance."""

    base = declarative_base(
        cls=ModelMixin,
        metaclass=AutoMappedDeclarativeMeta,
    )
    base.__bound_database__ = database
    base.__name__ = "Model"
    return base


class AutoMappedDeclarativeMeta(DeclarativeMeta):
    """Declarative metaclass that maps plain annotations automatically."""

    def __new__(mcls, name: str, bases: tuple[type[Any], ...], namespace: dict[str, Any], **kw: Any) -> Any:
        annotations = dict(namespace.get("__annotations__", {}))

        if not namespace.get("__abstract__", False):
            _fail_on_reserved_attribute_names(name, annotations, namespace)

        for attr, annotation in list(annotations.items()):
            if attr.startswith("_") or _is_classvar(annotation):
                continue
            if get_origin(annotation) is Mapped:
                continue

            value = namespace.get(attr, _MISSING)
            annotations[attr] = Mapped[annotation]

            if value is _MISSING:
                namespace[attr] = mapped_column()
            elif isinstance(value, MappedColumn):
                continue
            else:
                namespace[attr] = mapped_column(default=value)

        namespace["__annotations__"] = annotations

        if not namespace.get("__abstract__", False) and "__tablename__" not in namespace:
            namespace["__tablename__"] = _snake_case(name)

        return super().__new__(mcls, name, bases, namespace, **kw)


class ModelMixin:
    """CRUD behavior shared by all Duo-ORM model classes."""

    __abstract__ = True
    __bound_database__: ClassVar[Any]

    @classmethod
    def create(cls, **fields: Any) -> Any:
        instance = cls(**fields)
        return instance.save()

    @classmethod
    def from_schema(cls, schema_obj: Any) -> Any:
        from duo_orm.schemas.mapping import model_from_schema

        return model_from_schema(cls, schema_obj)

    @classmethod
    async def acreate(cls, **fields: Any) -> Any:
        instance = cls(**fields)
        return await instance.asave()

    @classmethod
    def get(cls, pk: Any) -> Any | None:
        with cls.__bound_database__.standalone_session() as session:
            return session.get(cls, pk)

    @classmethod
    async def aget(cls, pk: Any) -> Any | None:
        async with cls.__bound_database__.astandalone_session() as session:
            return await session.get(cls, pk)

    @classmethod
    def where(cls, *predicates: Any) -> QueryBuilder:
        builder = QueryBuilder(root_model=cls, database=cls.__bound_database__)
        if predicates:
            return builder.where(*predicates)
        return builder

    @classmethod
    def join(cls, target: type[Any], *, on: Any, kind: str = "inner") -> QueryBuilder:
        return cls.where().join(target, on=on, kind=kind)

    @classmethod
    def bulk_insert(cls, rows: list[dict[str, Any]]) -> int:
        with cls.__bound_database__.transaction() as session:
            result = session.execute(insert(cls.__table__), rows)
            return result.rowcount or 0

    @classmethod
    async def abulk_insert(cls, rows: list[dict[str, Any]]) -> int:
        async with cls.__bound_database__.atransaction() as session:
            result = await session.execute(insert(cls.__table__), rows)
            return result.rowcount or 0

    def save(self) -> Any:
        _apply_timestamp_hooks(self)
        with self.__bound_database__.transaction() as session:
            managed = session.merge(self)
            session.flush()
            session.refresh(managed)
            _copy_model_state(source=managed, target=self)
        return self

    async def asave(self) -> Any:
        _apply_timestamp_hooks(self)
        async with self.__bound_database__.atransaction() as session:
            managed = await session.merge(self)
            await session.flush()
            await session.refresh(managed)
            _copy_model_state(source=managed, target=self)
        return self

    def update(self, **fields: Any) -> Any:
        for key, value in fields.items():
            setattr(self, key, value)
        return self.save()

    async def aupdate(self, **fields: Any) -> Any:
        for key, value in fields.items():
            setattr(self, key, value)
        return await self.asave()

    def apply_schema(self, schema_obj: Any) -> Any:
        from duo_orm.schemas.mapping import apply_schema_to_instance

        return apply_schema_to_instance(self, schema_obj)

    def delete(self) -> None:
        with self.__bound_database__.transaction() as session:
            managed = session.merge(self)
            session.delete(managed)

    async def adelete(self) -> None:
        async with self.__bound_database__.atransaction() as session:
            managed = await session.merge(self)
            await session.delete(managed)

    def to_schema(self, schema_cls: type[Any]) -> Any:
        from duo_orm.schemas.mapping import model_to_schema

        return model_to_schema(self, schema_cls)


def _copy_model_state(source: Any, target: Any) -> None:
    for column in source.__table__.columns:
        setattr(target, column.key, getattr(source, column.key))


def _is_classvar(annotation: Any) -> bool:
    return get_origin(annotation) is ClassVar


def _snake_case(name: str) -> str:
    return _CAMEL_TO_SNAKE_RE.sub("_", name).lower()


def _fail_on_reserved_attribute_names(
    class_name: str,
    annotations: dict[str, Any],
    namespace: dict[str, Any],
) -> None:
    for attr in _RESERVED_MODEL_ATTRIBUTES:
        if attr in annotations or attr in namespace:
            raise ReservedModelAttributeError(
                f"Model '{class_name}' declares '{attr}', which is reserved by SQLAlchemy "
                "Declarative. Choose a different Python attribute name."
            )


def _apply_timestamp_hooks(instance: Any) -> None:
    phase = _persistence_phase(instance)
    now = datetime.now(timezone.utc)
    for column in instance.__table__.columns:
        set_on = column.info.get("set_on")
        if not set_on:
            continue
        if phase in _normalize_set_on(set_on):
            setattr(instance, column.key, now)


def _persistence_phase(instance: Any) -> str:
    state = sqlalchemy_inspect(instance)
    if state.transient or state.pending:
        return "create"
    return "update"


def _normalize_set_on(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    return {str(item) for item in value}

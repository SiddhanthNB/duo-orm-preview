"""Pure-Python schema/model mapping helpers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SchemaMappingError(ValueError):
    """Raised when schema/model mapping fails."""


def model_from_schema(model_cls: type[Any], schema_obj: Any) -> Any:
    """Create an unsaved model instance from a schema object."""

    ensure_pydantic_schema_instance(schema_obj)
    payload = schema_to_mapping(schema_obj, partial=False)
    values = validate_schema_fields(model_cls, payload)
    return model_cls(**values)


def apply_schema_to_instance(instance: Any, schema_obj: Any) -> Any:
    """Patch an existing model instance in memory from a schema object."""

    ensure_pydantic_schema_instance(schema_obj)
    payload = schema_to_mapping(schema_obj, partial=True)
    values = validate_schema_fields(type(instance), payload)
    for key, value in values.items():
        setattr(instance, key, value)
    return instance


def model_to_schema(instance: Any, schema_cls: type[Any]) -> Any:
    """Convert a model instance into a schema object explicitly."""

    ensure_pydantic_schema_class(schema_cls)
    field_names = schema_field_names(schema_cls)
    available_fields = set(instance.__table__.c.keys())
    missing = [name for name in field_names if name not in available_fields]
    if missing:
        raise SchemaMappingError(
            f"Schema fields do not belong to model '{type(instance).__name__}': "
            f"{', '.join(sorted(missing))}."
        )

    values = {name: getattr(instance, name) for name in field_names}
    try:
        return schema_cls(**values)
    except Exception as exc:
        raise SchemaMappingError(
            f"Could not construct schema '{schema_cls.__name__}' from model "
            f"'{type(instance).__name__}'."
        ) from exc


def schema_to_mapping(schema_obj: Any, *, partial: bool) -> dict[str, Any]:
    """Extract a mapping from a Pydantic v2 schema object."""

    data = schema_obj.model_dump(exclude_unset=partial)
    return ensure_mapping(data, schema_obj)


def schema_field_names(schema_cls: type[Any]) -> tuple[str, ...]:
    """Return declared field names for a Pydantic v2 schema class."""

    return tuple(schema_cls.model_fields.keys())


def validate_schema_fields(model_cls: type[Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Ensure schema payload keys belong to the model table."""

    allowed_fields = set(model_cls.__table__.c.keys())
    unexpected = sorted(set(payload) - allowed_fields)
    if unexpected:
        raise SchemaMappingError(
            f"Schema fields do not belong to model '{model_cls.__name__}': "
            f"{', '.join(unexpected)}."
        )
    return payload


def ensure_mapping(data: Any, schema_obj: Any) -> dict[str, Any]:
    """Validate a schema dump result."""

    if not isinstance(data, dict):
        raise SchemaMappingError(
            f"Schema object '{type(schema_obj).__name__}' did not produce a mapping."
        )
    return data


def ensure_pydantic_schema_instance(schema_obj: Any) -> None:
    """Require a Pydantic v2 schema instance."""

    if not isinstance(schema_obj, BaseModel):
        raise SchemaMappingError(
            f"Unsupported schema object '{type(schema_obj).__name__}'. "
            "Duo-ORM schema mapping supports Pydantic v2+ schema objects only."
        )


def ensure_pydantic_schema_class(schema_cls: type[Any]) -> None:
    """Require a Pydantic v2 schema class."""

    if not isinstance(schema_cls, type) or not issubclass(schema_cls, BaseModel):
        raise SchemaMappingError(
            f"Unsupported schema class '{getattr(schema_cls, '__name__', type(schema_cls).__name__)}'. "
            "Duo-ORM schema mapping supports Pydantic v2+ schema classes only."
        )

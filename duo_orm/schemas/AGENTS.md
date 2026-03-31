# Schemas Guide

## Mission

`duo_orm/schemas/` owns the optional schema bridge beside core and migrations.
Its job is narrow: convert validated Pydantic v2 data to and from Duo-ORM model instances without taking over persistence or querying.


## Scope

This package exists for opt-in schema integration only.
It should stay:

- small
- explicit
- instance-focused
- pure Python
- separate from database IO and query semantics

Pydantic v2+ is the supported schema runtime.
Do not carry compatibility branches for Pydantic v1 or parallel schema systems.
When this package is enabled, keep the dependency expectation aligned with `pydanticV2 (>=2.0)`.


## Change Workflow

1. Start from the mapping boundary: validated data in, validated data out, no hidden IO.
2. Keep the API obvious enough that callers know when persistence is still their responsibility.
3. Prefer shallow name-based mapping rules over clever recursive behavior.
4. Preserve compatibility with normal API-framework flows such as FastAPI request and response handling.
5. Reject feature growth that turns this package into a serializer framework or query DSL.


## Area Contracts

Public API surface:

- `Model.from_schema(schema_obj)`
- `instance.apply_schema(schema_obj)`
- `instance.to_schema(SchemaClass)`

Behavioral contracts:

- `from_schema(...)` creates a new unsaved model instance.
- `apply_schema(...)` mutates an existing model instance in memory.
- `to_schema(...)` constructs the requested schema object from model attributes.
- These methods stay synchronous because they do not perform IO.
- Partial update behavior should follow the schema object's own semantics, especially Pydantic v2 unset-field behavior.
- The mapping layer may live in a single `mapping.py` module until responsibilities genuinely diverge; do not split it prematurely.

Hard boundaries:

- no database access
- no session creation
- no save, flush, or commit side effects
- no relationship loading
- no recursive graph orchestration by default
- no schema-driven filtering, ordering, pagination, or join DSLs

Documentation convention:

- grouped schema namespaces such as `User.Create`, `User.Update`, and `User.Read` are a recommended user pattern
- importing that wrapper as `UserSchemas` to avoid clashing with a Duo-ORM model class is a recommended calling convention
- that wrapper style is a convention, not a runtime requirement


## Validation Standard

Changes in `schemas/` should usually update and run:

- `tests/test_schemas.py`
- `tests/integration/test_app_flow.py` when schema mapping participates in a persisted app flow

Minimum verification expectations:

- pure-Python tests for field mapping, partial updates, and output shaping
- explicit tests proving schema methods do not persist on their own
- integration coverage for create-from-schema, patch-then-save, and model-to-schema response flows


## Out of Scope

These remain outside the schema package unless the product contract changes intentionally:

- schema-driven query generation
- relationship-aware nested writes
- automatic preloading or serialization of related graphs
- persistence wrappers around `save()` / `asave()`
- support for multiple schema runtimes at once

# Core Guide

## Mission

`duo_orm/core/` owns the runtime contract of Duo-ORM.
This is where the library must feel small, opinionated, and reliable.

Core owns:

- `Database`
- engine construction and driver derivation
- session factories and transaction helpers
- isolated `db.Model` bases
- instance and class-level CRUD
- `QueryBuilder`, query shaping, and terminal execution
- JSON and ARRAY filter helpers
- raw SQL and SQLAlchemy escape hatches
- core exceptions and validation rules


## Scope

The core package should provide a lean ActiveRecord-style surface over SQLAlchemy 2.x Core.
It is not meant to wrap every SQLAlchemy concept.

The intended ladder is:

1. Duo-ORM model and query methods for normal CRUD and filtering
2. `.alchemize()` for SQLAlchemy `Select` composition
3. `text()`, `db.execute(...)`, or standalone sessions for full control

Complexity belongs in filtering, joins, JSON and ARRAY querying, and validation.
Complexity does not belong in relationship loading, hidden cascades, or implicit data-shape magic.


## Change Workflow

1. Start from the public contract, not the current implementation accident.
2. Keep sync and async behavior symmetrical whenever database IO is involved.
3. Prefer extending `QueryBuilder` and validation rules over adding large model power methods.
4. Add explicit failures for unsupported combinations instead of hidden fallback behavior.
5. Preserve the escape hatch story whenever a higher-level API grows more opinionated.

Module shape should stay responsibility-based:

- `database.py`
- `engines.py`
- `sessions.py`
- `model.py`
- `query_builder.py`
- `query_shapers.py`
- `query_terminals.py`
- `query_validation.py`
- `expressions.py`
- `exceptions.py`


## Area Contracts

Non-negotiable runtime contracts:

- Users should normally import from `duo_orm`, not SQLAlchemy directly.
- Re-export only the SQLAlchemy pieces that belong in the public Duo-ORM story.
- Model declarations should prefer plain Python annotations and use `mapped_column(...)` only when explicit SQL details are needed.
- `Database(...)` accepts a driver-free PostgreSQL URL and injects the correct sync and async `psycopg` drivers internally.
- `engine_kwargs` must be applied consistently to both engines. Do not rewrite kwargs per engine behind the scenes.
- `derive_async=False` means no async engine, no async session factory, and clear Duo-ORM errors from async APIs.
- Each `Database` instance creates its own isolated `db.Model` base.
- The isolated model base should carry only minimal internal binding state such as `__bound_database__`; avoid extra hidden magic.
- Reserved SQLAlchemy declarative names such as `metadata` must fail fast with a targeted Duo-ORM error.

Model and query contracts:

- Keep the class-level model surface intentionally small: `create`, `acreate`, `get`, `aget`, `where`, `bulk_insert`, `abulk_insert`.
- `get()` and `aget()` are primary-key lookups only.
- `where(...)` is the query entry point.
- `join(...)` should stay explicit and support only the core join kinds the product documents.
- Do not introduce `.related()` or relationship-loading semantics in core v1.
- Do not allow joined-query pagination shortcuts in core where the semantics are ambiguous.
- `.paginate(...)` is query shaping only, not execution and not metadata generation.
- `.alchemize()` is the handoff point from Duo-ORM to SQLAlchemy `Select` composition.
- `group_by(...)`, `having(...)`, and aggregate/report-style query DSLs should stay on the SQLAlchemy side of the `.alchemize()` handoff.

Persistence and execution boundaries:

- `transaction()` / `atransaction()` are the high-level transaction helpers.
- `standalone_session()` / `astandalone_session()` are the full-control session escape hatches.
- `text` and `db.execute(...)` are the raw SQL path; do not invent a second wrapper abstraction.
- Automatic timestamp hooks may support instance-oriented create and save flows, but bulk inserts and set-based query updates must not silently mutate timestamp columns.
- Query-builder `update()` and `delete()` are plain root-table set operations. They must not imply ORM cascade behavior, relationship orchestration, or hidden timestamp updates.

Schema bridge touchpoints that core must preserve:

- `Model.from_schema(...)` creates an unsaved instance only
- `instance.apply_schema(...)` mutates in memory only
- `instance.to_schema(...)` performs no IO


## Validation Standard

Changes in `core/` should usually update and run:

- `tests/test_core.py`
- `tests/integration/test_app_flow.py` when real database behavior changes

Minimum verification expectations:

- sync and async coverage for any API that performs IO
- exact exception behavior when rejecting unsupported states
- SQL and query-shaping assertions for compile-time semantics
- integration coverage for joins, JSON filters, ARRAY filters, timestamps, `.alchemize()`, or raw SQL flows


## Out of Scope

These remain out of scope unless the product contract is explicitly widened:

- non-PostgreSQL runtime support
- automatic relationship loading
- hidden aliasing for reserved attribute names
- silent fallback from async APIs to sync execution
- broad top-level model convenience methods that duplicate query-builder responsibilities
- advanced join types, joined-query pagination, or joined-table ordering in core where the semantics stop being obvious

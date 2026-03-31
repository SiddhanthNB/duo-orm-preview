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
Complexity does not belong in hidden session spawning, implicit data-shape magic, or a second relationship-query DSL layered on top of SQLAlchemy.


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
- The curated re-export surface should cover the common public building blocks users are expected to need in normal Duo-ORM usage, including:
  - model-definition primitives such as `mapped_column`, `ForeignKey`, and `relationship`
  - SQL expression helpers such as `func`, `text`, and `table`
  - SQLAlchemy-side escape-hatch builders such as `select`
- Prefer explicit PostgreSQL aliasing for dialect-specific types so the public API stays honest about backend specificity. If the project re-exports PostgreSQL-only types from `sqlalchemy.dialects.postgresql`, use names such as:
  - `PG_ARRAY`
  - `PG_JSON`
  - `PG_JSONB`
  - `PG_UUID`
- Keep the re-export story curated rather than mirroring SQLAlchemy wholesale.
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
- `transaction()` / `atransaction()` are also the shared-session boundary for high-level Duo-ORM terminal methods.
- Terminal methods executed inside an active Duo-ORM transaction must reuse that ambient session instead of opening a fresh standalone session.
- Terminal methods executed outside a transaction may still use short-lived standalone sessions and therefore return detached instances afterward.
- Ambient transaction/session state must be context-scoped, not process-global. Use task/thread-safe context storage such as `ContextVar`, not module-level globals.
- Nested `transaction()` / `atransaction()` calls in the same context are not supported and should raise a targeted Duo-ORM error instead of pretending to support nested transactions or savepoints.
- `standalone_session()` / `astandalone_session()` are the full-control session escape hatches.
- `transaction()` / `atransaction()` and `standalone_session()` / `astandalone_session()` are not interchangeable:
  - `transaction()` / `atransaction()` are the high-level Duo-ORM runtime boundary where terminal methods, instance methods, and relationship lazy loading should share one ambient session
  - `standalone_session()` / `astandalone_session()` are direct SQLAlchemy access points for users who want full control and are willing to manage session lifecycle and transaction semantics themselves
- `standalone_session()` / `astandalone_session()` should be treated as naked session gateways rather than managed Duo-ORM context helpers.
- If the runtime exposes them as plain session factories/getters, the user is responsible for closing them.
- Do not hide that low-level ownership model behind a second managed wrapper abstraction.
- `text` and `db.execute(...)` are the raw SQL path; do not invent a second wrapper abstraction.
- Automatic timestamp hooks may support instance-oriented create and save flows, but bulk inserts and set-based query updates must not silently mutate timestamp columns.
- Query-builder `update()` and `delete()` are plain root-table set operations. They must not imply ORM cascade behavior, relationship orchestration, or hidden timestamp updates.

The transaction contract should be explicit enough to explain the intended difference:

```python
with db.transaction():
    user = User.get(1)
    posts = user.posts
```

This should work because `User.get(1)` reuses the ambient transaction session and `user` remains session-bound for the scope of that transaction.

By contrast:

```python
user = User.get(1)
posts = user.posts
```

must not be promised to work, because outside an ambient transaction the short-lived session may already be closed and `user` may be detached.

Relationship boundaries:

- Re-export SQLAlchemy primitives that belong in the public model-definition story, including `ForeignKey` and `relationship`, but keep them as thin re-exports rather than custom Duo-ORM wrappers.
- Re-export the SQLAlchemy helpers users commonly need around relationship-backed models and SQLAlchemy escape hatches, including `func` and `table`, so normal usage still feels like it stays inside `duo_orm`.
- Model-level SQLAlchemy relationships such as `user.posts` or `post.user` are acceptable as a SQLAlchemy-backed feature on Duo-ORM models.
- Do not add a separate Duo-ORM relationship-query API on top of those attributes. Filtering still belongs on model-rooted query builders such as `Post.where(...)`, not on `user.posts.where(...)`.
- Normal relationship lazy loading is only reliable when the instance is bound to a live session, such as inside `db.transaction()`, `db.atransaction()`, or direct standalone-session usage.
- Detached instances returned from short-lived terminal methods outside a transaction must not promise transparent relationship lazy loading.
- Do not auto-open a new session when a relationship attribute is accessed on a detached instance.
- If detached relationship access fails, prefer catching SQLAlchemy's `DetachedInstanceError` and surfacing a Duo-ORM-specific error message that tells the user to use `db.transaction()` / `db.atransaction()` or direct standalone-session usage.
- Direct standalone-session usage means direct SQLAlchemy ownership, for example:

```python
session = db.standalone_session()
try:
    user = session.get(User, 1)
    posts = user.posts
finally:
    session.close()
```

- The async equivalent should follow the same ownership model:

```python
session = db.astandalone_session()
try:
    user = await session.get(User, 1)
    posts = user.posts
finally:
    await session.close()
```

- The public error should be Duo-ORM-native rather than a raw SQLAlchemy exception. It should preserve the cause internally but guide the caller clearly. A good message shape is:

```text
Relationship 'posts' cannot be loaded because this User instance is detached.
Load the model inside `db.transaction()` / `db.atransaction()`, or use a direct standalone session.
```

Recommended model-definition style:

```python
from duo_orm import ForeignKey, relationship, mapped_column
from db.database import db


class User(db.Model):
    id: int = mapped_column(primary_key=True)
    email: str

    posts = relationship("Post", back_populates="user")


class Post(db.Model):
    id: int = mapped_column(primary_key=True)
    user_id: int = mapped_column(ForeignKey("user.id"))
    title: str

    user = relationship("User", back_populates="posts")
```

The public story should encourage users to import those primitives from `duo_orm`, even though the behavior is SQLAlchemy-backed.

Recommended public imports should stay coherent. For example:

```python
from duo_orm import (
    ForeignKey,
    PG_JSON,
    PG_JSONB,
    PG_UUID,
    func,
    relationship,
    table,
    mapped_column,
)
```

Use these as thin Duo-ORM re-exports, not as the start of a separate wrapper API.

Loading/read behavior should be described with equal precision:

```python
with db.transaction():
    user = User.get(1)
    posts = user.posts
```

works through normal SQLAlchemy lazy loading because the object is session-bound.

```python
session = db.standalone_session()
try:
    user = session.get(User, 1)
    posts = user.posts
finally:
    session.close()
```

is the direct SQLAlchemy escape hatch for code that wants live-session relationship access without using Duo-ORM's high-level transaction helper.

Eager-loading configuration should remain a SQLAlchemy-owned concern:

- if a user configures eager relationship loading through SQLAlchemy `relationship(...)` options, Duo-ORM should not interfere
- collection relationships should generally behave more predictably with `selectin` than with `joined`
- scalar relationships such as one-to-one or many-to-one are less problematic with `joined`
- Duo-ORM should document that these semantics belong to SQLAlchemy, not to a Duo-ORM-specific abstraction layer

Cascade boundaries:

- Database-level cascades remain valid and should be allowed to work normally.
- SQLAlchemy ORM cascades configured through `relationship(..., cascade=...)` may participate in instance-oriented persistence and deletion when those operations run inside a live session.
- Query-builder `update()` and `delete()` remain plain SQL set operations and must not trigger ORM cascade semantics.
- Instance `save()` / `update()` / `delete()` may benefit from SQLAlchemy unit-of-work behavior because they merge into a live session for the duration of that operation, but Duo-ORM should not advertise a second cascade/callback abstraction of its own.
- Instance-oriented writes should be described as the SQLAlchemy bridge point:
  - `create()` / `acreate()`
  - `save()` / `asave()`
  - `update()` / `aupdate()`
  - `delete()` / `adelete()`
- Those methods may participate in SQLAlchemy relationship and cascade behavior without requiring the caller to wrap them in an outer transaction block.
- Read-side relationship loading is the part that requires either a live transaction scope or direct standalone-session usage.
- Bulk and set-based operations remain intentionally lean even after relationship support is widened:
  - `bulk_insert()` / `abulk_insert()` stay table-oriented
  - query-builder `update()` / `aupdate()` stay plain set-based updates
  - query-builder `delete()` / `adelete()` stay plain set-based deletes

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
- exact exception behavior when translating low-level SQLAlchemy relationship errors into Duo-ORM-native guidance
- SQL and query-shaping assertions for compile-time semantics
- integration coverage for joins, JSON filters, ARRAY filters, timestamps, `.alchemize()`, or raw SQL flows
- integration coverage for ambient transaction reuse when high-level terminal methods are executed inside `db.transaction()` / `db.atransaction()`
- targeted tests for the nested-transaction error contract
- relationship tests that distinguish live-session behavior from detached-instance behavior
- relationship tests that prove:
  - `user.posts` works inside `db.transaction()`
  - detached `user.posts` fails with the documented Duo-ORM guidance
  - direct standalone-session usage works for relationship access without a Duo-ORM transaction helper
  - instance-oriented writes can participate in SQLAlchemy cascade behavior
  - bulk and set-based operations remain free of ORM cascade side effects
- re-export tests that prove the intended public surface includes the curated SQLAlchemy helpers and PostgreSQL aliases the docs promise


## Out of Scope

These remain out of scope unless the product contract is explicitly widened:

- non-PostgreSQL runtime support
- hidden aliasing for reserved attribute names
- silent fallback from async APIs to sync execution
- broad top-level model convenience methods that duplicate query-builder responsibilities
- advanced join types, joined-query pagination, or joined-table ordering in core where the semantics stop being obvious
- hidden session creation on relationship attribute access
- query-builder methods hanging off relationship attributes

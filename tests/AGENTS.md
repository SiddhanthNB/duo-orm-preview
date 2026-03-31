# Tests Guide

## Mission

`tests/` owns the verification story for Duo-ORM.
The suite should prove both the sharp local contracts and the real application workflow.


## Scope

The test strategy is intentionally split into two layers:

1. fast deterministic tests at the top level
2. slower real-PostgreSQL integration tests under `tests/integration/`

Do not collapse those layers into one style.
They serve different purposes and should stay optimized for those purposes.


## Change Workflow

1. Decide whether the behavior is best proven as a fast contract test, a real integration test, or both.
2. Keep compile-time and scaffold assertions cheap and deterministic.
3. Use the integration suite for real database behavior, CLI flows, and cross-module interactions.
4. Isolate every integration run so cleanup is explicit and repeatable.
5. When behavior changes, update tests first-class rather than relying on manual verification.


## Area Contracts

Top-level fast tests:

- `tests/test_core.py`
- `tests/test_migrations.py`
- `tests/test_schemas.py`

These should cover:

- model mapping rules
- curated public re-exports from `duo_orm`, including SQLAlchemy helper re-exports and PostgreSQL alias names promised by the docs
- query-builder compilation and SQL shaping
- validation and guardrail errors
- generated scaffold contents
- migration configuration rules
- pure-Python schema mapping behavior

Integration tests:

- live under `tests/integration/`
- use a real PostgreSQL database
- require `DUO_ORM_TEST_DATABASE_URL`
- create a unique schema per run
- end with explicit cleanup such as `DROP SCHEMA ... CASCADE`
- scaffold a temporary application workspace through `duo-orm init`
- do not manually construct the `db/` package tree when the scaffold contract itself is what is being tested

The integration layer should prove the full product story across core, migrations, and schemas, including:

- sync and async CRUD
- `migration.create`, `migration.upgrade`, `migration.history`, and `migration.downgrade` flows through the shipped CLI
- joins, JSON filters, ARRAY filters, and `.alchemize()` handoff
- raw SQL escape hatches
- schema mapping in a PATCH-style application flow
- timestamp behavior where the runtime contract defines it
- ambient transaction reuse so high-level terminal methods share one session inside `db.transaction()` / `db.atransaction()`
- relationship behavior in the two supported modes:
  - SQLAlchemy relationship access on live session-bound instances
  - explicit failure or non-support expectations for detached-instance lazy loading outside transaction scope
- direct standalone-session access as the lower-level escape hatch for relationship-backed reads
- multiple models, not a single trivial table, so joins and cross-table filtering are exercised realistically

The relationship/session story should be proven with concrete flows, not inferred indirectly. For example:

```python
with db.transaction():
    user = User.get(1)
    posts = user.posts
```

should succeed when the relationship is configured correctly because the model was loaded through the ambient transaction session.

```python
user = User.get(1)
_ = user.posts
```

should either fail with the documented Duo-ORM detached-instance guidance or behave exactly as the core contract documents. Do not leave this ambiguous in tests.

The direct SQLAlchemy escape hatch should be proven too:

```python
session = db.standalone_session()
try:
    user = session.get(User, 1)
    posts = user.posts
finally:
    session.close()
```

Relationship-aware write behavior also needs explicit coverage:

- instance `create/save/update/delete` should be tested with SQLAlchemy relationships and cascades where the runtime intends to allow that bridge
- query-builder `update/delete` and `bulk_insert` should be tested separately to prove they remain table-oriented and lean rather than ORM-graph-aware

Guardrail placement:

- keep reserved-name failures, invalid joins, and similar compile-time validation cases in the fast layer
- keep nested transaction rejection in the fast layer unless a real-database path is specifically under test
- keep real persistence, schema isolation, and scaffolded app workflows in the integration layer
- keep relationship lazy-loading semantics and ambient-session reuse in the integration layer, because mocks do not prove the real SQLAlchemy/session behavior


## Validation Standard

Default test runner:

```bash
python -m unittest discover tests
```

Minimum expectations:

- run the relevant fast test module for area-local changes
- run the integration flow when real database behavior, migrations, or schema-persistence boundaries change
- avoid introducing tests that depend on shared mutable state or hardcoded secrets
- prefer schema-per-run cleanup over table-by-table cleanup in integration tests
- when relationship support is involved, prove both the session-bound success path and the detached-instance boundary explicitly
- if the runtime wraps `DetachedInstanceError`, assert the exact public Duo-ORM error and guidance rather than the raw SQLAlchemy exception alone
- if the runtime re-exports PostgreSQL dialect types and SQLAlchemy helper functions, assert those names directly from `duo_orm` instead of relying only on internal imports
- if `standalone_session()` / `astandalone_session()` are naked session gateways, test them as explicit user-managed SQLAlchemy sessions rather than assuming context-manager cleanup


## Out of Scope

These remain anti-goals for the test suite:

- hardcoded live database credentials in committed test docs
- integration tests that reuse a shared schema without cleanup
- mocking away behavior that the product explicitly needs to prove against PostgreSQL
- moving fast contract coverage into slow integration tests without a clear reason

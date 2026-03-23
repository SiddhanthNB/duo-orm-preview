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
- migration create, upgrade, history, and downgrade flows
- joins, JSON filters, ARRAY filters, and `.alchemize()` handoff
- raw SQL escape hatches
- schema mapping in a PATCH-style application flow
- timestamp behavior where the runtime contract defines it
- multiple models, not a single trivial table, so joins and cross-table filtering are exercised realistically

Guardrail placement:

- keep reserved-name failures, invalid joins, and similar compile-time validation cases in the fast layer
- keep real persistence, schema isolation, and scaffolded app workflows in the integration layer


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


## Out of Scope

These remain anti-goals for the test suite:

- hardcoded live database credentials in committed test docs
- integration tests that reuse a shared schema without cleanup
- mocking away behavior that the product explicitly needs to prove against PostgreSQL
- moving fast contract coverage into slow integration tests without a clear reason

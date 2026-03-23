# Migrations Guide

## Mission

`duo_orm/migrations/` owns the migration and scaffolding contract for Duo-ORM projects.
This layer should feel conventional, explicit, and easy to debug.

It is a thin, opinionated Alembic bridge, not a second migration framework.


## Scope

The migration system is for Duo-ORM scaffolded projects.
It may enforce a narrow project layout in exchange for predictable behavior.

The supported story is:

- one project-level `db/database.py`
- one shared `db.Model` base
- one explicit `db.models` import point
- one Alembic environment per project
- one version table derived from project configuration

Adapting arbitrary existing Alembic repositories is out of scope for this layer.


## Change Workflow

1. Start from the scaffold and CLI contract, not from Alembic internals.
2. Keep generated projects predictable enough that support and debugging stay simple.
3. Prefer explicit imports and targeted failure messages over discovery heuristics.
4. When generated files change, update the exact-content tests in the same change.
5. Preserve a clean escape hatch to direct Alembic commands.


## Area Contracts

Scaffold and configuration rules:

- `duo-orm init` must create `pyproject.toml` when needed and populate `[tool.duo-orm]`.
- `[tool.duo-orm]` must remain the source of project migration settings such as `project_name` and `db_dir`.
- `project_name` is used to derive a stable project-specific Alembic version table name.
- The scaffolded `db/` tree should be a real Python package layout with `__init__.py` files.
- `db/database.py` is mandatory and defines the authoritative shared `Database` instance.
- `db/models/__init__.py` is the explicit model import point for migration discovery.
- `db/schemas/__init__.py` should also be scaffolded so the generated app layout remains a complete importable package tree.

Alembic environment rules:

- `env.py` should put the scaffold root on `sys.path` if needed, import `db.database`, then import `db.models`.
- `target_metadata` must resolve from `db.Model.metadata`.
- Do not scan model files heuristically when `db.models` can be the explicit contract.
- Generated failure messages should explain Duo-ORM conventions when required files or imports are missing.
- Migration autogenerate should fail clearly if no models were imported into the authoritative metadata.
- Failures caused by reserved model attribute names or models bound to the wrong `db.Model` base should surface as Duo-ORM-guided errors, not generic metadata confusion.

CLI rules:

- Keep the surface intentionally small:
  - `duo-orm init`
  - `duo-orm migration create "message"`
  - `duo-orm migration upgrade`
  - `duo-orm migration downgrade`
  - `duo-orm migration history`
- The CLI should derive `alembic.ini` from `db_dir` and fail clearly when the project is not initialized.
- Advanced workflows should remain possible through direct Alembic usage against the generated `alembic.ini`.


## Validation Standard

Changes in `migrations/` should usually update and run:

- `tests/test_migrations.py`
- `tests/integration/test_app_flow.py` when scaffolded projects or live migration flows change

Minimum verification expectations:

- exact file-content assertions for generated `database.py`, `env.py`, and package scaffolding
- CLI argument normalization and config loading tests
- integration coverage for init, create, upgrade, history, and downgrade when migration behavior changes
- explicit failure coverage for missing scaffold pieces or broken imports
- verification that the scaffolded package layout is importable without manual patch-up in tests


## Out of Scope

These remain out of scope unless the migration product is intentionally redesigned:

- multi-database migration orchestration
- heuristic scanning of arbitrary project layouts
- treating multiple `Database(...)` instances as one migration unit
- hiding Alembic behind a larger custom abstraction
- generic error messages when a Duo-ORM-specific message can explain the failure clearly

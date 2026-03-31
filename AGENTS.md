# Duo-ORM Repository Guide

## Mission

Treat `duo-orm-preview` like a production-grade preview of Duo-ORM, not a scratchpad.
Every change should reinforce the same product story:

- PostgreSQL-only ORM layer on top of SQLAlchemy 2.x Core
- explicit sync and async runtime APIs
- explicit Alembic-backed project scaffolding and migration workflow
- optional Pydantic v2 schema mapping that stays separate from persistence

The repository should feel small, coherent, and easy to debug.


## Scope

This root guide defines the workflow and standards that apply everywhere.
Area-specific rules live in the nearest `AGENTS.md`:

- `duo_orm/core/AGENTS.md`
- `duo_orm/migrations/AGENTS.md`
- `duo_orm/schemas/AGENTS.md`
- `tests/AGENTS.md`

Primary repository layout:

- `duo_orm/core/`
  - runtime surface: `Database`, engines, sessions, models, query builder, expressions, exceptions
- `duo_orm/migrations/`
  - CLI entry points, config loading, project scaffolding, Alembic runner and templates
- `duo_orm/schemas/`
  - opt-in Pydantic v2 mapping helpers
- `tests/`
  - fast contract tests plus real PostgreSQL integration tests
- `pyproject.toml`
  - package metadata, dependencies, script entry points, and tool configuration

Only `AGENTS.md` is canonical. Do not introduce new `Agents.md` files.

The root file should stay brief and cross-cutting. Deeper behavioral detail belongs in:

- `duo_orm/core/AGENTS.md` for runtime semantics
- `duo_orm/migrations/AGENTS.md` for scaffold and Alembic conventions
- `duo_orm/schemas/AGENTS.md` for Pydantic mapping boundaries
- `tests/AGENTS.md` for verification strategy


## Change Workflow

1. Read this file and the closest area `AGENTS.md` before editing.
2. Define the exact contract being changed, including sync, async, CLI, schema, and test implications.
3. Make the smallest coherent change that preserves the product boundaries.
4. Update tests in the same change whenever behavior, scaffolding, or public errors move.
5. Verify with the narrowest useful command set, then broaden if the change crosses module boundaries.
6. Update docs and generated expectations when user-facing behavior or repository conventions change.

Default engineering posture:

- prefer explicit behavior over hidden magic
- fail loudly on unsupported states
- preserve good escape hatches instead of over-expanding the core abstraction
- keep modules focused by responsibility, not by sync vs async duplication


## Area Contracts

Repository-wide rules:

- Python 3.12+ only
- 4-space indentation, `snake_case` for functions/modules, `PascalCase` for classes
- explicit type hints on public APIs
- PostgreSQL is the only supported database backend
- `psycopg` v3 is the driver story for both sync and async execution
- the public surface should stay curated and teachable, not a mirror of SQLAlchemy
- sync and async database APIs should remain symmetrical unless the operation is pure Python
- schema mapping stays opt-in and must not perform persistence or query work
- raw SQL, standalone sessions, `.alchemize()`, and direct Alembic usage remain first-class escape hatches
- secrets and live database URLs belong in environment variables, never in committed docs or source
- project metadata should follow normal PEP 621 `[project]` conventions when Duo-ORM scaffolds a fresh `pyproject.toml`
- Duo-ORM-specific persistent config belongs under `[tool.duo-orm]`, with narrower nested sections such as `[tool.duo-orm.migration]` when a subsystem needs its own namespace

Repository-wide design posture:

- keep the public API smaller than the implementation
- let tests carry precise behavioral truth where possible
- document boundaries and invariants here, not every single example

Development commands:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover tests
```

Integration tests require `DUO_ORM_TEST_DATABASE_URL` to be set.


## Validation Standard

Expected verification level depends on the change:

- runtime behavior:
  - update the relevant fast tests and run the affected module tests
- scaffolded files or CLI behavior:
  - update exact-content assertions in migration tests
- schema mapping behavior:
  - update both pure-Python schema tests and any affected integration flow
- cross-cutting behavior:
  - run `python -m unittest discover tests`

When real database behavior matters, prefer the integration suite over mocks.
When compile-time behavior matters, prefer fast deterministic tests at the top level.
When CLI structure changes, update both the exact scaffold/config assertions and the real CLI integration flow.


## Out of Scope

These repository standards are deliberate:

- no non-PostgreSQL support
- no broad compatibility shims for alternate ORM or schema runtimes
- no duplicate documentation trees under mixed filename casing
- no silent fallback from async APIs to sync behavior
- no undocumented changes to scaffold shape, environment variables, or public error contracts

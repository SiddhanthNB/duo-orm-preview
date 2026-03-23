"""Alembic command runners for duo-orm migrations."""

from __future__ import annotations

import shlex

from .config import get_alembic_ini_path


def run_alembic(c, command_name: str) -> None:
    alembic_ini = get_alembic_ini_path()
    if not alembic_ini.exists():
        raise FileNotFoundError(
            f"alembic.ini not found at {alembic_ini}. Run 'duo-orm init' first."
        )

    command_text = f"alembic -c {shlex.quote(str(alembic_ini))} {command_name}"
    c.run(command_text)


def create_migration(c, message: str) -> None:
    run_alembic(c, f"revision --autogenerate -m {shlex.quote(message)}")


def upgrade_migrations(c) -> None:
    run_alembic(c, "upgrade head")


def downgrade_migrations(c) -> None:
    run_alembic(c, "downgrade -1")


def migration_history(c) -> None:
    run_alembic(c, "history")

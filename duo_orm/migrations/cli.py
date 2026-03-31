"""Invoke-powered migration commands for duo-orm."""

from __future__ import annotations

import sys
from pathlib import Path

from invoke import Collection, Program, task

from .config import (
    DEFAULT_DB_DIR,
    default_project_name,
    ensure_pyproject,
    slugify_project_name,
)
from .runner import create_migration, downgrade_migrations, migration_history, upgrade_migrations
from .scaffold import customize_alembic_ini, customize_env_py, initialize_alembic_environment, scaffold_layout


@task(positional=["message"])
def create(c, message: str) -> None:
    """Create a new migration."""

    create_migration(c, message)


@task
def upgrade(c) -> None:
    """Upgrade to the latest migration."""

    upgrade_migrations(c)


@task
def downgrade(c) -> None:
    """Downgrade one migration."""

    downgrade_migrations(c)


@task(name="history")
def history_(c) -> None:
    """Show migration history."""

    migration_history(c)


@task(
    help={
        "db_dir": "The base directory where the 'db/' folder will be scaffolded (default: '.').",
        "name": "The project name for fresh scaffolds (default: current directory name).",
    }
)
def init(c, db_dir: str = DEFAULT_DB_DIR, name: str | None = None) -> None:
    """Scaffold the db/ directory and configure migrations."""
    del c
    resolved_project_name = slugify_project_name(name or default_project_name())
    resolved_db_dir = db_dir or DEFAULT_DB_DIR
    db_dir_path = Path(resolved_db_dir)

    ensure_pyproject(
        project_name=resolved_project_name,
        db_dir=resolved_db_dir,
        force_project_name=name is not None,
    )
    scaffold_layout(db_dir_path)

    migrations_dir = db_dir_path / "db" / "migrations"
    initialize_alembic_environment(migrations_dir)
    customize_alembic_ini(migrations_dir / "alembic.ini")
    customize_env_py(
        migrations_dir / "env.py",
        db_dir=resolved_db_dir,
    )


migration = Collection("migration")
migration.add_task(create)
migration.add_task(upgrade)
migration.add_task(downgrade)
migration.add_task(history_)

ns = Collection()
ns.add_task(init)
ns.add_collection(migration)
program = Program(namespace=ns, binary="duo-orm")


def main(argv: list[str] | None = None) -> None:
    """Run the Duo-ORM CLI via invoke."""

    cli_argv = argv if argv is not None else sys.argv[1:]
    program.run(argv=["duo-orm", *cli_argv])

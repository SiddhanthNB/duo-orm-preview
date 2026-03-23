"""Template source for scaffolded Alembic env.py files."""

ENV_TEMPLATE = """from __future__ import annotations

import os
import sys
import tomllib
from logging.config import fileConfig
from pathlib import Path

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_DB_DIR_ROOT = Path(__file__).resolve().parents[2]
_PROJECT_ROOT = (
    _DB_DIR_ROOT
    if {db_dir_depth} == 0
    else _DB_DIR_ROOT.parents[{db_dir_depth} - 1]
)
_PYPROJECT_PATH = _PROJECT_ROOT / "pyproject.toml"

if str(_DB_DIR_ROOT) not in sys.path:
    sys.path.insert(0, str(_DB_DIR_ROOT))

VERSION_TABLE = {version_table!r}
EXPECTED_DB_DIR = {db_dir!r}


def _load_duo_orm_config() -> dict:
    if not _PYPROJECT_PATH.exists():
        raise RuntimeError(
            "Duo-ORM migrations require pyproject.toml at "
            f"{{_PYPROJECT_PATH}}. Run 'duo-orm init' first."
        )

    with _PYPROJECT_PATH.open("rb") as handle:
        config_data = tomllib.load(handle)

    try:
        return config_data["tool"]["duo-orm"]
    except KeyError as exc:
        raise RuntimeError(
            "Missing [tool.duo-orm] configuration in pyproject.toml. "
            "Run 'duo-orm init' first."
        ) from exc


DUO_ORM_CONFIG = _load_duo_orm_config()

if DUO_ORM_CONFIG.get("db_dir", ".") != EXPECTED_DB_DIR:
    raise RuntimeError(
        "The generated Alembic environment is out of sync with [tool.duo-orm]. "
        f"Expected db_dir={{EXPECTED_DB_DIR!r}} but found "
        f"{{DUO_ORM_CONFIG.get('db_dir', '.')}}."
    )


def _load_database():
    try:
        from db.database import db
    except Exception as exc:
        raise RuntimeError(
            "Could not import db.database. Duo-ORM migrations require the "
            "scaffolded db/database.py module."
        ) from exc

    return db


db = _load_database()


def _import_models() -> None:
    try:
        import db.models  # noqa: F401
    except Exception as exc:
        raise RuntimeError(
            "Could not import db.models. Import your project model modules from "
            "db/models/__init__.py so Alembic autogenerate can see them."
        ) from exc


_import_models()

target_metadata = getattr(getattr(db, "Model", None), "metadata", None)
if target_metadata is None:
    raise RuntimeError(
        "Could not resolve metadata from db.Model.metadata. Duo-ORM migrations "
        "require a shared Database instance in db/database.py."
    )

if not target_metadata.tables:
    raise RuntimeError(
        "No models were imported into db.Model.metadata. Import your model modules "
        "from db/models/__init__.py before running autogenerate."
    )


def _database_url() -> str:
    return os.getenv(
        "DATABASE_URL",
        db.sync_engine.url.render_as_string(hide_password=False),
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={{"paramstyle": "named"}},
        version_table=VERSION_TABLE,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with db.sync_engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table=VERSION_TABLE,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
"""

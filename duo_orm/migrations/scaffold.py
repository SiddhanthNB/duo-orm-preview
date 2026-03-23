"""Filesystem scaffolding for duo-orm migrations."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from .env_template import ENV_TEMPLATE

DATABASE_TEMPLATE = """import os

from duo_orm import Database


URL = os.getenv("DATABASE_URL", "postgresql://user:pass@host/db")
db = Database(URL)
"""

DB_PACKAGE_INIT = '"""Duo-ORM database package."""\n'
MODELS_PACKAGE_INIT = (
    '"""Import project model modules here so Alembic autogenerate can see them."""\n'
)
SCHEMAS_PACKAGE_INIT = '"""Project schema modules live here."""\n'


def scaffold_layout(db_dir: Path) -> None:
    db_package_dir = db_dir / "db"
    models_dir = db_package_dir / "models"
    schemas_dir = db_package_dir / "schemas"

    models_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir.mkdir(parents=True, exist_ok=True)

    _write_if_missing(db_package_dir / "__init__.py", DB_PACKAGE_INIT)
    _write_if_missing(db_package_dir / "database.py", DATABASE_TEMPLATE)
    _write_if_missing(models_dir / "__init__.py", MODELS_PACKAGE_INIT)
    _write_if_missing(schemas_dir / "__init__.py", SCHEMAS_PACKAGE_INIT)


def customize_alembic_ini(alembic_ini_path: Path) -> None:
    content = alembic_ini_path.read_text(encoding="utf-8")
    content = content.replace(
        "sqlalchemy.url = driver://user:pass@localhost/dbname",
        "sqlalchemy.url = postgresql://user:pass@localhost/dbname",
    )
    alembic_ini_path.write_text(content, encoding="utf-8")


def customize_env_py(
    env_py_path: Path,
    *,
    project_name: str,
    db_dir: str,
) -> None:
    version_table = f"{project_name}_migrations"
    env_py_path.write_text(
        ENV_TEMPLATE.format(
            version_table=version_table,
            db_dir=db_dir,
            db_dir_depth=len(Path(db_dir).parts),
        ),
        encoding="utf-8",
    )


def initialize_alembic_environment(migrations_dir: Path) -> None:
    if migrations_dir.exists() and any(migrations_dir.iterdir()):
        raise FileExistsError(
            f"{migrations_dir} already exists and is not empty. "
            "This initializer is for new projects only."
        )

    migrations_dir.mkdir(parents=True, exist_ok=True)
    alembic_ini_path = migrations_dir / "alembic.ini"
    config = Config(str(alembic_ini_path))
    command.init(config, str(migrations_dir), template="generic", package=False)


def _write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")

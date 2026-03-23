from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url


INTEGRATION_DATABASE_URL = os.environ.get("DUO_ORM_TEST_DATABASE_URL")
if not INTEGRATION_DATABASE_URL:
    raise RuntimeError(
        "Integration tests require DUO_ORM_TEST_DATABASE_URL to be set."
    )

REPO_ROOT = Path(__file__).resolve().parents[2]
INTEGRATION_BASE_URL = make_url(INTEGRATION_DATABASE_URL).set(drivername="postgresql")
INTEGRATION_ADMIN_URL = INTEGRATION_BASE_URL.set(drivername="postgresql+psycopg")

MODELS_INIT_TEMPLATE = """from .post import Post\nfrom .user import User\n"""
SCHEMAS_INIT_TEMPLATE = """from .user import User\n"""

USER_MODEL_TEMPLATE = """from datetime import datetime

from duo_orm import DateTime, JSON, mapped_column
from db.database import db


class User(db.Model):
    __tablename__ = "users"
    id: int = mapped_column(primary_key=True)
    email: str
    active: bool
    details: dict = mapped_column(JSON, nullable=False)
    created_at: datetime = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        info={"set_on": "create"},
    )
    updated_at: datetime = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        info={"set_on": {"create", "update"}},
    )
"""

POST_MODEL_TEMPLATE = """from datetime import datetime

from duo_orm import DateTime, PG_ARRAY, String, mapped_column
from db.database import db


class Post(db.Model):
    __tablename__ = "posts"
    id: int = mapped_column(primary_key=True)
    user_id: int
    title: str
    published: bool
    tags: list[str] = mapped_column(PG_ARRAY(String), nullable=False)
    created_at: datetime = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        info={"set_on": "create"},
    )
"""

USER_SCHEMAS_TEMPLATE = """from pydantic import BaseModel


class User:
    class Create(BaseModel):
        email: str
        active: bool
        details: dict

    class Update(BaseModel):
        email: str | None = None
        active: bool | None = None
        details: dict | None = None

    class Read(BaseModel):
        id: int
        email: str
        active: bool
        details: dict
"""


@dataclass
class IntegrationApp:
    workspace: Path
    schema_name: str
    schema_url: str
    cleanup_attempted: bool = False
    cleanup_schema_removed: bool | None = None

    @property
    def app_root(self) -> Path:
        return self.workspace / "src"

    @property
    def env(self) -> dict[str, str]:
        env = os.environ.copy()
        path_parts = [str(REPO_ROOT), str(self.app_root)]
        existing = env.get("PYTHONPATH")
        if existing:
            path_parts.append(existing)
        env["PYTHONPATH"] = os.pathsep.join(path_parts)
        env["DATABASE_URL"] = self.schema_url
        return env


@contextmanager
def integration_app() -> Iterator[IntegrationApp]:
    schema_name = f"duo_it_{uuid.uuid4().hex[:12]}"
    schema_url = url_with_search_path(INTEGRATION_BASE_URL, schema_name).render_as_string(
        hide_password=False
    )
    admin_engine = create_engine(INTEGRATION_ADMIN_URL)
    temp_dir = tempfile.TemporaryDirectory()
    workspace = Path(temp_dir.name)
    app = IntegrationApp(workspace=workspace, schema_name=schema_name, schema_url=schema_url)

    try:
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
        run_cli(app, "init", "--db-dir", "src", "--project-name", schema_name)
        write_integration_app_files(app)
        run_cli(app, "migration", "create", "initial_schema")
        run_cli(app, "migration", "upgrade")
        yield app
    finally:
        app.cleanup_attempted = True
        with admin_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        app.cleanup_schema_removed = not schema_exists(schema_name)
        admin_engine.dispose()
        temp_dir.cleanup()


def write_integration_app_files(app: IntegrationApp) -> None:
    db_dir = app.app_root / "db"
    models_dir = db_dir / "models"
    schemas_dir = db_dir / "schemas"
    (models_dir / "__init__.py").write_text(MODELS_INIT_TEMPLATE, encoding="utf-8")
    (models_dir / "user.py").write_text(USER_MODEL_TEMPLATE, encoding="utf-8")
    (models_dir / "post.py").write_text(POST_MODEL_TEMPLATE, encoding="utf-8")
    (schemas_dir / "__init__.py").write_text(SCHEMAS_INIT_TEMPLATE, encoding="utf-8")
    (schemas_dir / "user.py").write_text(USER_SCHEMAS_TEMPLATE, encoding="utf-8")


def run_cli(app: IntegrationApp, *args: str) -> subprocess.CompletedProcess[str]:
    return run_python_process(app, "-m", "duo_orm", *args)


def run_python(app: IntegrationApp, code: str) -> subprocess.CompletedProcess[str]:
    return run_python_process(app, "-c", textwrap.dedent(code))


def run_python_json(app: IntegrationApp, code: str) -> dict:
    return json.loads(run_python(app, code).stdout.strip())


def run_python_process(app: IntegrationApp, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=app.workspace,
        env=app.env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        command = " ".join([sys.executable, *args])
        raise RuntimeError(
            f"Subprocess failed: {command}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def url_with_search_path(url: URL, schema_name: str) -> URL:
    options = f"-csearch_path={schema_name}"
    return url.update_query_dict({"options": options})


def list_schema_tables(app: IntegrationApp) -> list[str]:
    query = text(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = :schema_name AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    engine = create_engine(INTEGRATION_ADMIN_URL)
    try:
        with engine.begin() as connection:
            rows = connection.execute(query, {"schema_name": app.schema_name}).scalars()
            return list(rows)
    finally:
        engine.dispose()


def schema_exists(schema_name: str) -> bool:
    query = text(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.schemata
            WHERE schema_name = :schema_name
        )
        """
    )
    engine = create_engine(INTEGRATION_ADMIN_URL)
    try:
        with engine.begin() as connection:
            return bool(connection.execute(query, {"schema_name": schema_name}).scalar_one())
    finally:
        engine.dispose()

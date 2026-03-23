from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from duo_orm.migrations.cli import init, normalize_cli_argv
from duo_orm.migrations.config import (
    default_project_name,
    get_alembic_ini_path,
    slugify_project_name,
    write_duo_orm_config,
)
from duo_orm.migrations.runner import run_alembic


class DummyContext:
    def run(self, command: str) -> None:
        self.command = command


class MigrationCliTests(unittest.TestCase):
    def test_normalize_cli_argv_rewrites_migration_subcommands(self) -> None:
        self.assertEqual(
            normalize_cli_argv(["migration", "create", "initial_schema"]),
            ["migration.create", "initial_schema"],
        )
        self.assertEqual(
            normalize_cli_argv(["migration", "upgrade"]),
            ["migration.upgrade"],
        )
        self.assertEqual(
            normalize_cli_argv(["init", "--db-dir", "src"]),
            ["init", "--db-dir", "src"],
        )

    def test_slugify_project_name(self) -> None:
        self.assertEqual(slugify_project_name("My Cool-App"), "my_cool_app")
        self.assertEqual(slugify_project_name("!!!"), "duo_orm_app")

    def test_default_project_name_uses_directory_name(self) -> None:
        with tempfile.TemporaryDirectory(prefix="duo-service-") as tmp:
            self.assertEqual(
                default_project_name(Path(tmp)),
                slugify_project_name(Path(tmp).name),
            )

    def test_write_duo_orm_config_creates_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pyproject_path = Path(tmp) / "pyproject.toml"
            pyproject_path.write_text("[project]\nname = \"demo\"\n", encoding="utf-8")

            write_duo_orm_config(
                db_dir="src",
                project_name="demo_service",
                pyproject_path=pyproject_path,
            )

            content = pyproject_path.read_text(encoding="utf-8")
            self.assertIn("[tool.duo-orm]", content)
            self.assertIn('project_name = "demo_service"', content)
            self.assertIn('db_dir = "src"', content)

    def test_get_alembic_ini_path_uses_tool_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pyproject_path = Path(tmp) / "pyproject.toml"
            pyproject_path.write_text(
                "[tool.duo-orm]\nproject_name = \"demo\"\ndb_dir = \"src\"\n",
                encoding="utf-8",
            )

            self.assertEqual(
                get_alembic_ini_path(pyproject_path),
                Path("src") / "db" / "migrations" / "alembic.ini",
            )

    def test_run_alembic_builds_expected_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            pyproject_path = workspace / "pyproject.toml"
            pyproject_path.write_text(
                "[tool.duo-orm]\nproject_name = \"demo\"\ndb_dir = \"src\"\n",
                encoding="utf-8",
            )

            migrations_dir = workspace / "src" / "db" / "migrations"
            migrations_dir.mkdir(parents=True)
            (migrations_dir / "alembic.ini").write_text("", encoding="utf-8")

            cwd = Path.cwd()
            try:
                os.chdir(workspace)
                ctx = DummyContext()
                run_alembic(ctx, "history")
            finally:
                os.chdir(cwd)

            self.assertEqual(ctx.command, "alembic -c src/db/migrations/alembic.ini history")

    def test_init_scaffolds_expected_layout_and_env_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            try:
                workspace = Path(tmp)
                pyproject_path = workspace / "pyproject.toml"
                pyproject_path.write_text(
                    "[project]\nname = \"demo\"\nversion = \"0.1.0\"\n",
                    encoding="utf-8",
                )

                os.chdir(workspace)
                init.body(DummyContext(), db_dir="src", project_name="Demo Service")
            finally:
                os.chdir(cwd)

            db_dir = workspace / "src" / "db"
            migrations_dir = db_dir / "migrations"
            self.assertTrue((db_dir / "__init__.py").is_file())
            self.assertTrue((db_dir / "database.py").is_file())
            self.assertTrue((db_dir / "models").is_dir())
            self.assertTrue((db_dir / "models" / "__init__.py").is_file())
            self.assertTrue((db_dir / "schemas").is_dir())
            self.assertTrue((db_dir / "schemas" / "__init__.py").is_file())
            self.assertTrue((migrations_dir / "alembic.ini").is_file())
            self.assertTrue((migrations_dir / "env.py").is_file())
            self.assertTrue((migrations_dir / "script.py.mako").is_file())
            self.assertTrue((migrations_dir / "versions").is_dir())

            database_py = (db_dir / "database.py").read_text(encoding="utf-8")
            self.assertIn("from duo_orm import Database", database_py)
            self.assertIn('URL = os.getenv("DATABASE_URL", "postgresql://user:pass@host/db")', database_py)
            self.assertIn("db = Database(URL)", database_py)

            schemas_init = (db_dir / "schemas" / "__init__.py").read_text(encoding="utf-8")
            self.assertEqual(schemas_init, '"""Project schema modules live here."""\n')

            env_py = (migrations_dir / "env.py").read_text(encoding="utf-8")
            self.assertIn("demo_service_migrations", env_py)
            self.assertIn("from db.database import db", env_py)
            self.assertIn("import db.models", env_py)
            self.assertIn("target_metadata = getattr(getattr(db, \"Model\", None), \"metadata\", None)", env_py)
            self.assertIn("No models were imported into db.Model.metadata", env_py)
            self.assertIn("if str(_DB_DIR_ROOT) not in sys.path:", env_py)
            self.assertNotIn("_iter_model_modules", env_py)


if __name__ == "__main__":
    unittest.main()

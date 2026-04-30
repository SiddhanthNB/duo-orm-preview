from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from duo_orm.migrations.cli import init, main
from duo_orm.migrations.config import (
    derive_version_table_name,
    default_project_name,
    get_alembic_ini_path,
    get_version_table,
    slugify_project_name,
    ensure_pyproject,
)
from duo_orm.migrations.runner import run_alembic


class DummyContext:
    def run(self, command: str) -> None:
        self.command = command


class CaptureProgram:
    def __init__(self) -> None:
        self.argv: list[str] | None = None

    def run(self, argv: list[str]) -> None:
        self.argv = argv


class MigrationCliTests(unittest.TestCase):
    def test_main_passes_through_canonical_dotted_cli_shape(self) -> None:
        import duo_orm.migrations.cli as migration_cli

        capture = CaptureProgram()
        original = migration_cli.program
        try:
            migration_cli.program = capture
            main(["migration.current"])
        finally:
            migration_cli.program = original

        self.assertEqual(capture.argv, ["duo-orm", "migration.current"])

    def test_slugify_project_name(self) -> None:
        self.assertEqual(slugify_project_name("My Cool-App"), "my-cool-app")
        self.assertEqual(slugify_project_name("MyCoolProject"), "my-cool-project")
        self.assertEqual(slugify_project_name("!!!"), "duo-orm-app")

    def test_derive_version_table_name(self) -> None:
        self.assertEqual(
            derive_version_table_name("my-cool-project"),
            "my_cool_project_migrations",
        )
        self.assertEqual(
            derive_version_table_name("CamelCase"),
            "camel_case_migrations",
        )

    def test_default_project_name_uses_directory_name(self) -> None:
        with tempfile.TemporaryDirectory(prefix="duo-service-") as tmp:
            self.assertEqual(
                default_project_name(Path(tmp)),
                slugify_project_name(Path(tmp).name),
            )

    def test_ensure_pyproject_creates_pep621_project_and_tool_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pyproject_path = Path(tmp) / "pyproject.toml"

            ensure_pyproject(
                project_name="my-cool-project",
                db_dir="src",
                pyproject_path=pyproject_path,
            )

            content = pyproject_path.read_text(encoding="utf-8")
            self.assertIn("[project]", content)
            self.assertIn('name = "my-cool-project"', content)
            self.assertIn('version = "0.1.0"', content)
            self.assertIn('requires-python = ">=3.12"', content)
            self.assertIn('readme = "README.md"', content)
            self.assertIn("dependencies = []", content)
            self.assertIn("[tool.duo-orm]", content)
            self.assertIn('db_dir = "src"', content)
            self.assertNotIn("project_name =", content)

    def test_get_version_table_prefers_nested_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pyproject_path = Path(tmp) / "pyproject.toml"
            pyproject_path.write_text(
                "[project]\n"
                'name = "demo-service"\n'
                "\n"
                "[tool.duo-orm]\n"
                'db_dir = "src"\n'
                "\n"
                "[tool.duo-orm.migration]\n"
                'version_table = "custom_version_table"\n',
                encoding="utf-8",
            )

            self.assertEqual(get_version_table(pyproject_path), "custom_version_table")

    def test_get_alembic_ini_path_uses_tool_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pyproject_path = Path(tmp) / "pyproject.toml"
            pyproject_path.write_text(
                "[project]\nname = \"demo-service\"\n\n[tool.duo-orm]\ndb_dir = \"src\"\n",
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
                "[project]\nname = \"demo-service\"\n\n[tool.duo-orm]\ndb_dir = \"src\"\n",
                encoding="utf-8",
            )

            migrations_dir = workspace / "src" / "db" / "migrations"
            migrations_dir.mkdir(parents=True)
            (migrations_dir / "alembic.ini").write_text("", encoding="utf-8")

            cwd = Path.cwd()
            try:
                os.chdir(workspace)
                commands = {
                    "history": "alembic -c src/db/migrations/alembic.ini history",
                    "current": "alembic -c src/db/migrations/alembic.ini current",
                    "check": "alembic -c src/db/migrations/alembic.ini check",
                }
                for command_name, expected_command in commands.items():
                    ctx = DummyContext()
                    run_alembic(ctx, command_name)
                    self.assertEqual(ctx.command, expected_command)
            finally:
                os.chdir(cwd)

    def test_init_scaffolds_expected_layout_and_env_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path.cwd()
            try:
                workspace = Path(tmp)
                pyproject_path = workspace / "pyproject.toml"
                pyproject_path.write_text(
                    "[project]\nname = \"demo-service\"\nversion = \"0.1.0\"\n",
                    encoding="utf-8",
                )

                os.chdir(workspace)
                init.body(DummyContext(), db_dir="src", name="MyCoolProject")
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

            pyproject_content = (workspace / "pyproject.toml").read_text(encoding="utf-8")
            self.assertIn('name = "my-cool-project"', pyproject_content)
            self.assertIn("[tool.duo-orm]", pyproject_content)
            self.assertIn('db_dir = "src"', pyproject_content)
            self.assertNotIn("project_name =", pyproject_content)

            env_py = (migrations_dir / "env.py").read_text(encoding="utf-8")
            self.assertIn("from db.database import db", env_py)
            self.assertIn("import db.models", env_py)
            self.assertIn("import re", env_py)
            self.assertIn("target_metadata = getattr(getattr(db, \"Model\", None), \"metadata\", None)", env_py)
            self.assertIn("No models were imported into db.Model.metadata", env_py)
            self.assertIn("PYPROJECT_CONFIG[\"tool\"][\"duo-orm\"]", env_py)
            self.assertIn("PYPROJECT_CONFIG[\"project\"][\"name\"]", env_py)
            self.assertIn("migration_config = DUO_ORM_CONFIG.get(\"migration\", {})", env_py)
            self.assertIn("version_table=_version_table()", env_py)
            self.assertIn("if str(_DB_DIR_ROOT) not in sys.path:", env_py)
            self.assertNotIn("_iter_model_modules", env_py)


if __name__ == "__main__":
    unittest.main()

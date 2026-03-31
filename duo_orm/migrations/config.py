"""Configuration helpers for duo-orm migrations."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

DEFAULT_DB_DIR = "."
TOOL_SECTION_HEADER = "[tool.duo-orm]"
MIGRATION_SECTION_HEADER = "[tool.duo-orm.migration]"
PROJECT_SECTION_HEADER = "[project]"


def slugify_project_name(value: str) -> str:
    """Normalize project names to packaging-friendly kebab-case."""

    separated = re.sub(r"(?<!^)(?=[A-Z])", "-", value.strip())
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", separated).strip("-").lower()
    return slug or "duo-orm-app"


def derive_version_table_name(project_name: str) -> str:
    """Derive the default Alembic version table from [project].name."""

    snake_source = re.sub(r"(?<!^)(?=[A-Z])", "_", project_name.strip())
    snake = re.sub(r"[^a-zA-Z0-9]+", "_", snake_source).strip("_").lower()
    return f"{snake or 'duo_orm_app'}_migrations"


def default_project_name(cwd: Path | None = None) -> str:
    base_dir = cwd or Path.cwd()
    return slugify_project_name(base_dir.name)


def read_pyproject(pyproject_path: Path | None = None) -> dict:
    path = pyproject_path or Path("pyproject.toml")
    if not path.exists():
        raise FileNotFoundError("pyproject.toml not found. Run 'duo-orm init' first.")

    with path.open("rb") as handle:
        return tomllib.load(handle)


def get_config(pyproject_path: Path | None = None) -> dict:
    config = read_pyproject(pyproject_path)
    return config.get("tool", {}).get("duo-orm", {})


def get_project_name(pyproject_path: Path | None = None) -> str:
    config = read_pyproject(pyproject_path)
    try:
        return str(config["project"]["name"])
    except KeyError as exc:
        raise RuntimeError(
            "Missing [project].name in pyproject.toml. Run 'duo-orm init' first "
            "or add a project name."
        ) from exc


def get_version_table(pyproject_path: Path | None = None) -> str:
    config = read_pyproject(pyproject_path)
    override = (
        config.get("tool", {})
        .get("duo-orm", {})
        .get("migration", {})
        .get("version_table")
    )
    if override:
        return str(override)
    return derive_version_table_name(get_project_name(pyproject_path))


def get_alembic_ini_path(pyproject_path: Path | None = None) -> Path:
    config = get_config(pyproject_path)
    db_dir = config.get("db_dir", DEFAULT_DB_DIR)
    return Path(db_dir) / "db" / "migrations" / "alembic.ini"


def ensure_pyproject(
    *,
    project_name: str,
    db_dir: str,
    pyproject_path: Path | None = None,
    force_project_name: bool = False,
) -> None:
    """Create or update pyproject.toml for Duo-ORM init."""

    path = pyproject_path or Path("pyproject.toml")
    if path.exists():
        content = path.read_text(encoding="utf-8")
    else:
        content = _fresh_pyproject_content(project_name, db_dir)
        path.write_text(content, encoding="utf-8")
        return

    content = _ensure_project_section(
        content,
        project_name=project_name,
        force_project_name=force_project_name,
    )
    content = _upsert_tool_duo_orm_section(content, db_dir=db_dir)
    path.write_text(content, encoding="utf-8")


def _fresh_pyproject_content(project_name: str, db_dir: str) -> str:
    return (
        f"{PROJECT_SECTION_HEADER}\n"
        f'name = "{project_name}"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.12"\n'
        'readme = "README.md"\n'
        "dependencies = []\n\n"
        f"{TOOL_SECTION_HEADER}\n"
        f'db_dir = "{db_dir}"\n'
    )


def _ensure_project_section(
    content: str,
    *,
    project_name: str,
    force_project_name: bool,
) -> str:
    section_pattern = re.compile(
        rf"(?ms)^{re.escape(PROJECT_SECTION_HEADER)}\n.*?(?=^\[|\Z)"
    )
    match = section_pattern.search(content)
    if match is None:
        separator = "\n" if content.strip() else ""
        return f"{content.rstrip()}{separator}\n{_project_section(project_name)}"

    project_section = match.group(0)
    if force_project_name or not re.search(r"(?m)^name\s*=", project_section):
        if re.search(r"(?m)^name\s*=", project_section):
            project_section = re.sub(
                r'(?m)^name\s*=.*$',
                f'name = "{project_name}"',
                project_section,
            )
        else:
            lines = project_section.splitlines()
            lines.insert(1, f'name = "{project_name}"')
            project_section = "\n".join(lines) + "\n"

    if not re.search(r"(?m)^version\s*=", project_section):
        project_section += 'version = "0.1.0"\n'
    if not re.search(r"(?m)^requires-python\s*=", project_section):
        project_section += 'requires-python = ">=3.12"\n'
    if not re.search(r"(?m)^readme\s*=", project_section):
        project_section += 'readme = "README.md"\n'
    if not re.search(r"(?m)^dependencies\s*=", project_section):
        project_section += "dependencies = []\n"

    return section_pattern.sub(project_section, content).rstrip() + "\n"


def _project_section(project_name: str) -> str:
    return (
        f"{PROJECT_SECTION_HEADER}\n"
        f'name = "{project_name}"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.12"\n'
        'readme = "README.md"\n'
        "dependencies = []\n"
    )


def _upsert_tool_duo_orm_section(content: str, *, db_dir: str) -> str:
    section = (
        f"{TOOL_SECTION_HEADER}\n"
        f'db_dir = "{db_dir}"\n'
    )
    section_pattern = re.compile(
        rf"(?ms)^{re.escape(TOOL_SECTION_HEADER)}\n.*?(?=^\[|\Z)"
    )

    if section_pattern.search(content):
        updated = section_pattern.sub(section, content)
    else:
        separator = "\n" if content.strip() else ""
        updated = f"{content.rstrip()}{separator}\n{section}"

    return updated.rstrip() + "\n"

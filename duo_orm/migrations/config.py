"""Configuration helpers for duo-orm migrations."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

DEFAULT_DB_DIR = "."
TOOL_SECTION_HEADER = "[tool.duo-orm]"


def slugify_project_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "duo_orm_app"


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


def get_alembic_ini_path(pyproject_path: Path | None = None) -> Path:
    config = get_config(pyproject_path)
    db_dir = config.get("db_dir", DEFAULT_DB_DIR)
    return Path(db_dir) / "db" / "migrations" / "alembic.ini"


def write_duo_orm_config(
    *,
    db_dir: str,
    project_name: str,
    pyproject_path: Path | None = None,
) -> None:
    path = pyproject_path or Path("pyproject.toml")
    if path.exists():
        content = path.read_text(encoding="utf-8")
    else:
        content = ""

    section = (
        f"{TOOL_SECTION_HEADER}\n"
        f'project_name = "{project_name}"\n'
        f'db_dir = "{db_dir}"\n'
    )

    section_pattern = re.compile(
        rf"(?ms)^{re.escape(TOOL_SECTION_HEADER)}\n.*?(?=^\[|\Z)"
    )

    if section_pattern.search(content):
        updated = section_pattern.sub(section, content).rstrip() + "\n"
    else:
        if content and not content.endswith("\n"):
            content += "\n"
        separator = "\n" if content.strip() else ""
        updated = f"{content}{separator}{section}"

    path.write_text(updated, encoding="utf-8")

# Duo-ORM Preview

Duo-ORM is a lean PostgreSQL-only ORM layer built on top of SQLAlchemy 2.x Core.

It is designed for:

- small, explicit CRUD
- a strong `where()`-driven query builder
- native sync and async support
- explicit Alembic-backed scaffolding and migrations
- optional Pydantic v2 schema mapping

The boundary is intentional:

- use Duo-ORM for normal app queries and persistence
- use SQLAlchemy for power moves


## Install

Use Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```


## Initialize a Project

Scaffold the database package and migration environment:

```bash
duo-orm init
```

If you want the scaffold under a different base directory:

```bash
duo-orm init --db-dir src
```

If you want to override the generated project name used in `pyproject.toml`:

```bash
duo-orm init --name MyCoolProject
```

`duo-orm init` should create a normal PEP 621-style `pyproject.toml` when one does not already exist. A fresh scaffold should look like:

```toml
[project]
name = "my-cool-project"
version = "0.1.0"
requires-python = ">=3.12"
readme = "README.md"
dependencies = []

[tool.duo-orm]
db_dir = "."
```

Notes:

- `[project].name` is the authoritative project identity
- Duo-ORM derives the default Alembic version table from `[project].name`
- the default derivation is snake-cased and suffixed with `_migrations`
- if you need to override the Alembic version table, do it in `pyproject.toml`, not with another CLI flag

Example override:

```toml
[tool.duo-orm.migration]
version_table = "custom_version_table"
```

This produces a package layout like:

```text
.
├── db/
│   ├── __init__.py
│   ├── database.py
│   ├── models/
│   │   └── __init__.py
│   ├── schemas/
│   │   └── __init__.py
│   └── migrations/
│       ├── alembic.ini
│       ├── env.py
│       └── versions/
└── pyproject.toml
```

Set the database URL before running migrations or application code:

```bash
export DATABASE_URL='postgresql://user:pass@host/dbname'
```

The generated `db/database.py` looks like:

```python
import os

from duo_orm import Database


URL = os.getenv("DATABASE_URL", "postgresql://user:pass@host/db")
db = Database(URL)
```


## Define Models

Define models against the shared `db` from `db.database`:

```python
from datetime import datetime

from duo_orm import DateTime, JSON, PG_ARRAY, String, mapped_column
from db.database import db


class User(db.Model):
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


class Post(db.Model):
    id: int = mapped_column(primary_key=True)
    user_id: int
    title: str
    published: bool
    tags: list[str] = mapped_column(PG_ARRAY(String), nullable=False)
```

Then import your model modules from `db/models/__init__.py` so Alembic autogenerate can see them:

```python
from .post import Post
from .user import User
```

Notes:

- plain Python annotations are the default
- use `mapped_column(...)` when you need explicit SQL details
- reserved SQLAlchemy declarative names such as `metadata` are rejected on purpose


## Run Migrations

Migration commands use the Invoke-style dotted namespace:

```bash
duo-orm migration.create "initial_schema"
duo-orm migration.upgrade
duo-orm migration.history
duo-orm migration.downgrade
```

Create a migration revision:

```bash
duo-orm migration.create "initial_schema"
```

Apply the latest revision:

```bash
duo-orm migration.upgrade
```

Inspect history:

```bash
duo-orm migration.history
```

Roll back one migration:

```bash
duo-orm migration.downgrade
```

The version table name follows this precedence:

1. `[tool.duo-orm.migration].version_table` if present
2. otherwise a derived default from `[project].name`

Examples:

- `[project].name = "my-cool-project"` -> `my_cool_project_migrations`
- `[project].name = "CamelCase"` -> `camel_case_migrations`

If you need full Alembic control, use the generated config directly:

```bash
alembic -c <path to alembic.ini> history --verbose
```


## CRUD

Create:

```python
user = User.create(
    email="alice@example.com",
    active=True,
    details={"status": "active"},
)

user = await User.acreate(
    email="alice@example.com",
    active=True,
    details={"status": "active"},
)
```

Get by primary key:

```python
user = User.get(1)
user = await User.aget(1)
```

Update one instance:

```python
user.update(email="alice.smith@example.com")
await user.aupdate(active=False)
```

Or mutate and save explicitly:

```python
user.active = False
user.save()

user.details = {"status": "inactive"}
await user.asave()
```

Delete one instance:

```python
user.delete()
await user.adelete()
```

Bulk insert:

```python
User.bulk_insert([
    {
        "email": "alice@example.com",
        "active": True,
        "details": {"status": "active"},
    },
    {
        "email": "bob@example.com",
        "active": False,
        "details": {"status": "inactive"},
    },
])
```

`bulk_insert()` is intentionally narrow:

- root table only
- list of dictionaries only
- no relationship orchestration
- no implicit timestamp hooks


## Query Builder

`where(...)` is the query entry point.

Simple filtering:

```python
users = User.where(User.active == True).exec()
users = await User.where(User.email.ilike("%@example.com")).aexec()
```

Count:

```python
count = User.where(User.active == True).count()
count = await User.where(User.active == True).acount()
```

Full-table query builder:

```python
users = User.where().exec()
total = User.where().count()
```

Set-based update and delete:

```python
updated = User.where(User.active == False).update(active=True)
deleted = User.where(User.active == False).delete()
```

These are plain SQL set operations on the root table. They do not imply ORM cascade behavior.


## Joins

Use explicit joins only:

```python
users = (
    User.where(User.active == True)
    .join(Post, on=Post.user_id == User.id, kind="inner")
    .where(Post.published == True)
    .exec()
)
```

Async:

```python
users = await (
    User.where(User.active == True)
    .join(Post, on=Post.user_id == User.id, kind="inner")
    .where(Post.published == True)
    .aexec()
)
```

Core supports only:

- `inner`
- `left`

Joined queries still return root-model instances only. If you need richer row shapes, aliases, advanced join types, or joined pagination, use SQLAlchemy through `.alchemize()`.


## Ordering and Pagination

Ordering stays rooted on the base model:

```python
users = (
    User.where(User.active == True)
    .order_by("-created_at")
    .limit(10)
    .offset(20)
    .exec()
)
```

Or:

```python
users = await (
    User.where(User.active == True)
    .paginate(limit=10, offset=20)
    .aexec()
)
```

Once `join()` is used, `limit()`, `offset()`, and `paginate()` are intentionally blocked. Use SQLAlchemy for that power move.


## JSON and ARRAY Filters

Use `json(...)` and `array(...)` inside `where(...)`.

JSON:

```python
from duo_orm import json

beta_users = User.where(
    json(User.details)["flags"]["is_beta"].is_true()
).exec()
```

Typed cast:

```python
users = User.where(
    json(User.details)["telemetry"]["retries"].as_integer() > 5
).exec()
```

ARRAY:

```python
from duo_orm import array

posts = Post.where(
    array(Post.tags).includes("python")
).exec()

posts = Post.where(
    array(Post.tags).includes_all(["python", "async"])
).exec()
```

If you need more advanced SQL than the provided JSON/ARRAY helpers, drop to SQLAlchemy.


## Use SQLAlchemy for Power Moves

Duo-ORM is meant to hand off cleanly when a query stops being simple.

`.alchemize()` returns the SQLAlchemy `Select` for the current Duo-ORM query state:

```python
from sqlalchemy import func

base_query = (
    User.where(User.active == True)
    .join(Post, on=Post.user_id == User.id, kind="inner")
    .where(Post.published == True)
)

stmt = (
    base_query.alchemize()
    .with_only_columns(
        User.id,
        User.email,
        func.count(Post.id).label("post_count"),
    )
    .group_by(User.id, User.email)
    .having(func.count(Post.id) >= 2)
)
```

Run that through a standalone session:

```python
from db.database import db

with db.standalone_session() as session:
    rows = session.execute(stmt).all()
```

This is the recommended pattern for:

- aggregates
- `group_by`
- `having`
- alias-heavy SQL
- advanced joined pagination
- any query that outgrows the lean core DSL


## Raw SQL and Standalone Sessions

For raw SQL:

```python
from duo_orm import text
from db.database import db

rows = db.execute(
    text("SELECT id, email FROM users WHERE active = true")
)
```

Parameterized:

```python
rows = db.execute(
    text("SELECT id, email FROM users WHERE email = :email"),
    {"email": "alice@example.com"},
)
```

For direct SQLAlchemy session control:

```python
from duo_orm import select
from db.database import db

with db.standalone_session() as session:
    stmt = select(User).where(User.active == True)
    users = session.execute(stmt).scalars().all()
```

Async:

```python
async with db.astandalone_session() as session:
    stmt = select(User).where(User.active == True)
    users = (await session.execute(stmt)).scalars().all()
```


## Optional Pydantic v2 Schema Mapping

The schema bridge is opt-in and intentionally small.

Recommended user convention:

```python
from pydantic import BaseModel


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
```

Import-alias it to avoid clashing with the Duo-ORM model class:

```python
from app.schemas.user import User as UserSchemas
from db.models.user import User
```

Create from schema:

```python
user = User.from_schema(
    UserSchemas.Create(
        email="alice@example.com",
        active=True,
        details={"status": "active"},
    )
)
user.save()
```

Patch an existing instance:

```python
user = User.get(1)
user.apply_schema(
    UserSchemas.Update(
        email="alice.smith@example.com",
        details={"status": "patched"},
    )
)
user.save()
```

Convert to schema:

```python
payload = user.to_schema(UserSchemas.Read)
```

Schema mapping does not:

- save
- flush
- commit
- load relationships
- define query/filter semantics


## FastAPI Example

Create:

```python
from fastapi import APIRouter

from app.schemas.user import User as UserSchemas
from db.models.user import User

router = APIRouter()


@router.post("/users", response_model=UserSchemas.Read)
async def create_user(payload: UserSchemas.Create):
    user = User.from_schema(payload)
    await user.asave()
    return user.to_schema(UserSchemas.Read)
```

PATCH:

```python
from fastapi import APIRouter, HTTPException

from app.schemas.user import User as UserSchemas
from db.models.user import User

router = APIRouter()


@router.patch("/users/{user_id}", response_model=UserSchemas.Read)
async def patch_user(user_id: int, payload: UserSchemas.Update):
    user = await User.aget(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.apply_schema(payload)
    await user.asave()
    return user.to_schema(UserSchemas.Read)
```

That is the intended schema flow:

1. FastAPI validates input with Pydantic
2. Duo-ORM loads or creates the model instance
3. `apply_schema(...)` mutates in memory only
4. `save()` / `asave()` persists explicitly
5. `to_schema(...)` shapes the response


## Design Boundaries

Use Duo-ORM for:

- normal CRUD
- filtering
- explicit joins
- JSON and ARRAY predicates
- simple pagination on non-joined queries
- explicit schema mapping for request/response objects

Use SQLAlchemy for power moves:

- aggregates and report-style queries
- `group_by` / `having`
- advanced joins
- alias-heavy SQL
- complex update/delete workflows
- any query whose semantics stop being obvious in the lean ORM surface


## Tests

Run the full suite with:

```bash
python -m unittest discover tests
```

Integration tests require:

```bash
export DUO_ORM_TEST_DATABASE_URL='postgresql://user:pass@host/dbname'
```

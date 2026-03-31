from __future__ import annotations

import unittest

from tests.integration.helpers import (
    integration_app,
    list_schema_tables,
    run_cli,
    run_python_json,
)


SYNC_APP_FLOW_SCRIPT = """
import json
from sqlalchemy import func

from db.database import db
from db.models import Post, User
from db.schemas.user import User as UserSchemas
from duo_orm import array, json as json_filter, text
from duo_orm.core.exceptions import DetachedRelationshipError

user = User.create(
    email="sync@example.com",
    active=True,
    details={"status": "active", "flags": {"is_beta": True}},
)
created_at = user.created_at.isoformat()
updated_at_initial = user.updated_at.isoformat()

User.bulk_insert([
    {
        "email": "bulk@example.com",
        "active": False,
        "details": {"status": "bulk"},
    }
])

post = Post.create(
    user_id=user.id,
    title="First Post",
    published=True,
    tags=["python", "guide"],
)
Post.bulk_insert([
    {
        "user_id": user.id,
        "title": "Second Post",
        "published": True,
        "tags": ["python", "async"],
    }
])

with db.transaction() as session:
    staged = User(
        email="ambient@example.com",
        active=True,
        details={"status": "ambient"},
    )
    session.add(staged)
    session.flush()
    ambient_count = User.where(User.email == "ambient@example.com").count()

with db.transaction():
    tx_user = User.get(user.id)
    live_transaction_post_titles = [post.title for post in tx_user.posts]

detached_user = User.get(user.id)
try:
    _ = detached_user.posts
except DetachedRelationshipError as exc:
    detached_error_type = type(exc).__name__
    detached_error_message = str(exc)
else:
    detached_error_type = None
    detached_error_message = None

session = db.standalone_session()
try:
    standalone_user = session.get(User, user.id)
    standalone_post_titles = [post.title for post in standalone_user.posts]
finally:
    session.close()

cascade_user = User(
    email="cascade@example.com",
    active=True,
    details={"status": "cascade"},
)
cascade_user.posts = [
    Post(
        title="Cascade Post",
        published=False,
        tags=["cascade"],
    )
]
cascade_user.save()
cascade_created_posts = Post.where(Post.title == "Cascade Post").count()
cascade_user.delete()
cascade_deleted_posts = Post.where(Post.title == "Cascade Post").count()

fetched = User.get(user.id)
fetched.active = False
fetched.save()
updated_after_save = fetched.updated_at.isoformat()

schema_created = User.from_schema(
    UserSchemas.Create(
        email="schema@example.com",
        active=True,
        details={"status": "schema"},
    )
)
schema_created.save()

fetched.apply_schema(
    UserSchemas.Update(
        email="patched@example.com",
        details={"status": "patched", "flags": {"is_beta": True}},
    )
)
after_apply_before_save = fetched.updated_at.isoformat()
fetched.save()
updated_after_apply_save = fetched.updated_at.isoformat()
response_schema = fetched.to_schema(UserSchemas.Read)

joined = (
    User.where(User.active == False)
    .join(Post, on=Post.user_id == User.id, kind="inner")
    .where(Post.published == True)
    .exec()
)

json_matches = User.where(
    json_filter(User.details)["flags"]["is_beta"].is_true()
).count()
array_matches = Post.where(array(Post.tags).includes("async")).count()

base_query = (
    User.where(User.active == False)
    .join(Post, on=Post.user_id == User.id, kind="inner")
    .where(Post.published == True)
)
ranked_stmt = (
    base_query.alchemize()
    .with_only_columns(
        User.id,
        func.count(Post.id).label("post_count"),
    )
    .group_by(User.id)
    .having(func.count(Post.id) >= 2)
)

session = db.standalone_session()
try:
    ranked_rows = session.execute(ranked_stmt).all()
    direct_count = session.execute(text("SELECT count(*) FROM posts")).scalar_one()
finally:
    session.close()

bulk_user_before_set_update = User.where(User.email == "bulk@example.com").exec()[0]
schema_user_before_delete = User.get(schema_created.id)
count_before_set_update = User.where(User.active == False).count()
updated_rows = User.where(User.email == "bulk@example.com").update(active=True)
deleted_rows = User.where(User.email == "schema@example.com").delete()
count_after_delete = User.where().count()

payload = {
    "created_at_was_set": created_at is not None,
    "updated_at_was_set": updated_at_initial is not None,
    "updated_changed_on_save": updated_after_save != updated_at_initial,
    "apply_schema_did_not_persist": after_apply_before_save == updated_after_save,
    "updated_changed_on_apply_save": updated_after_apply_save != updated_after_save,
    "bulk_insert_left_timestamps_null": schema_user_before_delete.created_at is not None
        and bulk_user_before_set_update.created_at is None,
    "ambient_count": ambient_count,
    "live_transaction_post_titles": live_transaction_post_titles,
    "detached_error_type": detached_error_type,
    "detached_error_message": detached_error_message,
    "standalone_post_titles": standalone_post_titles,
    "cascade_created_posts": cascade_created_posts,
    "cascade_deleted_posts": cascade_deleted_posts,
    "joined_count": len(joined),
    "json_matches": json_matches,
    "array_matches": array_matches,
    "ranked_rows": [tuple(row) for row in ranked_rows],
    "response_email": response_schema.email,
    "response_active": response_schema.active,
    "post_count_via_sql": direct_count,
    "count_before_set_update": count_before_set_update,
    "updated_rows": updated_rows,
    "deleted_rows": deleted_rows,
    "count_after_delete": count_after_delete,
    "query_update_did_not_touch_updated_at": User.where(User.email == "bulk@example.com").exec()[0].updated_at is None,
    "post_created_at_set": post.created_at is not None,
}
print(json.dumps(payload))
"""


ASYNC_APP_FLOW_SCRIPT = """
import asyncio
import json

from db.database import db
from db.models import Post, User
from db.schemas.user import User as UserSchemas
from duo_orm import array, json as json_filter
from duo_orm.core.exceptions import DetachedRelationshipError


async def main() -> None:
    user = await User.acreate(
        email="async@example.com",
        active=True,
        details={"status": "async", "flags": {"is_beta": True}},
    )
    deletable = await User.acreate(
        email="async-delete@example.com",
        active=True,
        details={"status": "delete"},
    )
    await Post.abulk_insert([
        {
            "user_id": user.id,
            "title": "Async Post",
            "published": True,
            "tags": ["async", "python"],
        }
    ])

    async with db.atransaction() as session:
        staged = User(
            email="async-ambient@example.com",
            active=True,
            details={"status": "async-ambient"},
        )
        session.add(staged)
        await session.flush()
        ambient_count = await User.where(
            User.email == "async-ambient@example.com"
        ).acount()

    fetched = await User.aget(user.id)
    fetched.apply_schema(UserSchemas.Update(active=False))
    before_save = fetched.updated_at.isoformat()
    await fetched.asave()
    after_save = fetched.updated_at.isoformat()

    detached = await User.aget(user.id)
    try:
        _ = detached.posts
    except DetachedRelationshipError as exc:
        detached_error_type = type(exc).__name__
        detached_error_message = str(exc)
    else:
        detached_error_type = None
        detached_error_message = None

    session = db.astandalone_session()
    try:
        standalone_user = await session.get(User, user.id)
        standalone_posts = await session.run_sync(lambda _: list(standalone_user.posts))
    finally:
        await session.close()

    rows = await (
        User.where(User.active == False)
        .join(Post, on=Post.user_id == User.id, kind="inner")
        .where(array(Post.tags).includes("async"))
        .aexec()
    )
    count = await User.where(
        json_filter(User.details)["flags"]["is_beta"].is_true()
    ).acount()
    deleted = await User.where(User.email == "async-delete@example.com").adelete()
    remaining = await User.where().acount()

    session = db.astandalone_session()
    try:
        titles = (await session.execute(Post.__table__.select())).all()
    finally:
        await session.close()

    print(json.dumps({
        "rows": len(rows),
        "count": count,
        "ambient_count": ambient_count,
        "updated_changed": after_save != before_save,
        "detached_error_type": detached_error_type,
        "detached_error_message": detached_error_message,
        "deleted": deleted,
        "standalone_posts": len(standalone_posts),
        "remaining": remaining,
        "titles": len(titles),
    }))


asyncio.run(main())
"""


class IntegrationAppFlowTests(unittest.TestCase):
    def test_real_app_flow_sync(self) -> None:
        app_ref = None
        with integration_app() as app:
            app_ref = app
            history = run_cli(app, "migration.history")
            self.assertIn("initial_schema", history.stdout + history.stderr)

            self.assertTrue({"users", "posts"}.issubset(set(list_schema_tables(app))))

            run_cli(app, "migration.downgrade")
            downgraded_tables = set(list_schema_tables(app))
            self.assertNotIn("users", downgraded_tables)
            self.assertNotIn("posts", downgraded_tables)

            run_cli(app, "migration.upgrade")
            self.assertTrue({"users", "posts"}.issubset(set(list_schema_tables(app))))

            payload = run_python_json(app, SYNC_APP_FLOW_SCRIPT)
            self.assertTrue(payload["created_at_was_set"])
            self.assertTrue(payload["updated_at_was_set"])
            self.assertTrue(payload["updated_changed_on_save"])
            self.assertTrue(payload["apply_schema_did_not_persist"])
            self.assertTrue(payload["updated_changed_on_apply_save"])
            self.assertTrue(payload["bulk_insert_left_timestamps_null"])
            self.assertEqual(payload["ambient_count"], 1)
            self.assertEqual(payload["live_transaction_post_titles"], ["First Post", "Second Post"])
            self.assertEqual(payload["detached_error_type"], "DetachedRelationshipError")
            self.assertIn("Relationship 'posts' cannot be loaded", payload["detached_error_message"])
            self.assertIn("direct standalone session", payload["detached_error_message"])
            self.assertEqual(payload["standalone_post_titles"], ["First Post", "Second Post"])
            self.assertEqual(payload["cascade_created_posts"], 1)
            self.assertEqual(payload["cascade_deleted_posts"], 0)
            self.assertEqual(payload["joined_count"], 1)
            self.assertEqual(payload["json_matches"], 1)
            self.assertEqual(payload["array_matches"], 1)
            self.assertEqual(payload["ranked_rows"][0][1], 2)
            self.assertEqual(payload["response_email"], "patched@example.com")
            self.assertFalse(payload["response_active"])
            self.assertEqual(payload["post_count_via_sql"], 2)
            self.assertEqual(payload["count_before_set_update"], 2)
            self.assertEqual(payload["updated_rows"], 1)
            self.assertEqual(payload["deleted_rows"], 1)
            self.assertEqual(payload["count_after_delete"], 3)
            self.assertTrue(payload["query_update_did_not_touch_updated_at"])
            self.assertTrue(payload["post_created_at_set"])

        self.assertIsNotNone(app_ref)
        self.assertTrue(app_ref.cleanup_attempted)
        self.assertTrue(app_ref.cleanup_schema_removed)


class IntegrationAsyncFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_app_flow_async(self) -> None:
        with integration_app() as app:
            payload = run_python_json(app, ASYNC_APP_FLOW_SCRIPT)
            self.assertEqual(payload["rows"], 1)
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["ambient_count"], 1)
            self.assertTrue(payload["updated_changed"])
            self.assertEqual(payload["detached_error_type"], "DetachedRelationshipError")
            self.assertIn("Relationship 'posts' cannot be loaded", payload["detached_error_message"])
            self.assertIn("direct standalone session", payload["detached_error_message"])
            self.assertEqual(payload["deleted"], 1)
            self.assertEqual(payload["standalone_posts"], 1)
            self.assertEqual(payload["remaining"], 2)
            self.assertEqual(payload["titles"], 1)

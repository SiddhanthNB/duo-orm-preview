from __future__ import annotations

import unittest

from sqlalchemy import func, update
from sqlalchemy.dialects import postgresql

from duo_orm import Database, JSON, PG_ARRAY, String, array, json, mapped_column
from duo_orm.core.exceptions import (
    AsyncNotConfiguredError,
    InvalidJoinError,
    PaginationJoinError,
    QueryScopeError,
    ReservedModelAttributeError,
)
from duo_orm.core.query_terminals import (
    build_count_statement,
    build_delete_statement,
    build_update_statement,
)


def compile_sql(statement: object) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


class DatabaseTests(unittest.TestCase):
    def test_database_derives_psycopg_engines_and_isolated_model_bases(self) -> None:
        primary = Database(
            "postgresql://user:pass@localhost/primary",
            engine_kwargs={"echo": True},
        )
        analytics = Database("postgresql://user:pass@localhost/analytics")

        class User(primary.Model):
            __tablename__ = "users"
            id: int = mapped_column(primary_key=True)
            name: str

        class AnalyticsUser(analytics.Model):
            __tablename__ = "users"
            id: int = mapped_column(primary_key=True)
            name: str

        self.assertEqual(primary.sync_engine.url.drivername, "postgresql+psycopg")
        self.assertIsNotNone(primary.async_engine)
        self.assertEqual(primary.async_engine.url.drivername, "postgresql+psycopg")
        self.assertTrue(primary.sync_engine.echo)
        self.assertTrue(primary.async_engine.echo)
        self.assertIsNot(primary.Model, analytics.Model)
        self.assertIsNot(User.__table__.metadata, AnalyticsUser.__table__.metadata)
        self.assertIs(User.__bound_database__, primary)
        self.assertIs(AnalyticsUser.__bound_database__, analytics)


class ModelMappingTests(unittest.TestCase):
    def test_reserved_metadata_field_fails_fast(self) -> None:
        db = Database("postgresql://user:pass@localhost/test", derive_async=False)

        with self.assertRaises(ReservedModelAttributeError):
            class Device(db.Model):
                __tablename__ = "devices"
                id: int = mapped_column(primary_key=True)
                metadata: dict = mapped_column(JSON, nullable=False)
                active: bool

    def test_plain_annotations_are_supported(self) -> None:
        db = Database("postgresql://user:pass@localhost/test", derive_async=False)

        class Device(db.Model):
            __tablename__ = "devices"
            id: int = mapped_column(primary_key=True)
            payload: dict = mapped_column(JSON, nullable=False)
            active: bool

        device = Device(payload={"status": "active"}, active=True)
        sql = compile_sql(Device.where(json(Device.payload)["status"] == "active").alchemize())

        self.assertEqual(device.payload, {"status": "active"})
        self.assertEqual(list(Device.__table__.c.keys()), ["id", "payload", "active"])
        self.assertIn("devices.payload", sql)
        self.assertIn("->> 'status'", sql)


class QueryBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = Database("postgresql://user:pass@localhost/test", derive_async=False)

        class User(self.db.Model):
            __tablename__ = "users"
            id: int = mapped_column(primary_key=True)
            active: bool
            created_at: str

        class Post(self.db.Model):
            __tablename__ = "posts"
            id: int = mapped_column(primary_key=True)
            user_id: int
            published: bool

        self.User = User
        self.Post = Post

    def test_joined_query_builds_select_count_update_and_delete_statements(self) -> None:
        query = (
            self.User.where(self.User.active == True)
            .join(self.Post, on=self.Post.user_id == self.User.id, kind="inner")
            .where(self.Post.published == True)
        )

        select_sql = compile_sql(query.alchemize())
        count_sql = compile_sql(build_count_statement(query))
        update_sql = compile_sql(build_update_statement(query, active=False))
        delete_sql = compile_sql(build_delete_statement(query))

        self.assertIn("FROM users JOIN posts ON posts.user_id = users.id", select_sql)
        self.assertIn("WHERE users.active = true AND posts.published = true", select_sql)
        self.assertIn("SELECT count(*) AS count_1", count_sql)
        self.assertIn("SELECT DISTINCT users.id AS id", count_sql)
        self.assertIn("UPDATE users SET active=false", update_sql)
        self.assertIn("users.id IN", update_sql)
        self.assertIn("DELETE FROM users", delete_sql)
        self.assertIn("users.id IN", delete_sql)

    def test_alchemize_handoff_supports_sqlalchemy_composition(self) -> None:
        base_query = (
            self.User.where(self.User.active == True)
            .join(self.Post, on=self.Post.user_id == self.User.id, kind="inner")
            .where(self.Post.published == True)
        )

        base_stmt = base_query.alchemize()
        ranked_stmt = (
            base_stmt.with_only_columns(
                self.User.id,
                func.count(self.Post.id).label("post_count"),
            )
            .group_by(self.User.id)
            .having(func.count(self.Post.id) >= 3)
        )
        deactivate_stmt = (
            update(self.User.__table__)
            .where(self.User.__table__.c.id.in_(ranked_stmt.with_only_columns(self.User.id)))
            .values(active=False)
        )

        ranked_sql = compile_sql(ranked_stmt)
        deactivate_sql = compile_sql(deactivate_stmt)

        self.assertIn("count(posts.id) AS post_count", ranked_sql)
        self.assertIn("GROUP BY users.id", ranked_sql)
        self.assertIn("HAVING count(posts.id) >= 3", ranked_sql)
        self.assertIn("UPDATE users SET active=false", deactivate_sql)
        self.assertIn("IN (SELECT users.id", deactivate_sql)

    def test_query_guardrails_raise_clear_exceptions(self) -> None:
        with self.assertRaises(PaginationJoinError):
            self.User.where().join(self.Post, on=self.Post.user_id == self.User.id).limit(10)

        with self.assertRaises(InvalidJoinError):
            self.User.where().join(self.Post, on=self.Post.user_id == self.User.id, kind="right")

        with self.assertRaises(QueryScopeError):
            self.User.where(self.Post.published == True).alchemize()

        with self.assertRaises(QueryScopeError):
            (
                self.User.where(self.User.active == True)
                .join(self.Post, on=self.Post.user_id == self.User.id)
                .order_by("published")
                .alchemize()
            )


class ExpressionTests(unittest.TestCase):
    def test_json_and_array_helpers_compile_to_postgresql_expressions(self) -> None:
        db = Database("postgresql://user:pass@localhost/test", derive_async=False)

        class Device(db.Model):
            __tablename__ = "devices"
            id: int = mapped_column(primary_key=True)
            payload: dict = mapped_column(JSON, nullable=False)

        class Article(db.Model):
            __tablename__ = "articles"
            id: int = mapped_column(primary_key=True)
            tags: list[str] = mapped_column(PG_ARRAY(String), nullable=False)

        json_sql = compile_sql(
            Device.where(
                json(Device.payload)["telemetry"]["retries"].as_integer() > 5,
                json(Device.payload)["flags"]["is_beta"].is_true(),
            ).alchemize()
        )
        array_sql = compile_sql(
            Article.where(
                array(Article.tags).includes("python"),
                array(Article.tags).includes_all(["python", "async"]),
                array(Article.tags).includes_any(["guide", "tutorial"]),
            ).alchemize()
        )

        self.assertIn("devices.payload", json_sql)
        self.assertIn("CAST", json_sql)
        self.assertIn("ANY (articles.tags)", array_sql)
        self.assertIn("@>", array_sql)
        self.assertIn("&&", array_sql)


class AsyncGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_apis_raise_when_async_engine_is_disabled(self) -> None:
        db = Database("postgresql://user:pass@localhost/test", derive_async=False)

        class User(db.Model):
            __tablename__ = "users"
            id: int = mapped_column(primary_key=True)
            name: str

        with self.assertRaises(AsyncNotConfiguredError):
            async with db.atransaction():
                pass

        with self.assertRaises(AsyncNotConfiguredError):
            await User.acreate(name="Alice")


if __name__ == "__main__":
    unittest.main()

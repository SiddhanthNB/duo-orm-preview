from __future__ import annotations

import unittest

from duo_orm import Database, JSON, mapped_column
from duo_orm.schemas import SchemaMappingError
from pydantic import BaseModel


class UserCreateSchema(BaseModel):
    name: str
    email: str
    active: bool


class UserUpdateSchema(BaseModel):
    name: str | None = None
    email: str | None = None


class UserReadSchema(BaseModel):
    id: int
    name: str
    email: str
    active: bool


class InvalidUserSchema(BaseModel):
    id: int
    name: str
    email: str
    active: bool
    profile: dict


class UserCreateWithUnknownSchema(BaseModel):
    name: str
    email: str
    active: bool
    unknown: str


class SchemaBridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db = Database("postgresql://user:pass@localhost/test", derive_async=False)

        class User(self.db.Model):
            __tablename__ = "users"
            id: int = mapped_column(primary_key=True)
            name: str
            email: str
            active: bool
            payload: dict = mapped_column(JSON, nullable=False, default=dict)

        self.User = User

    def test_from_schema_creates_unsaved_model_instance(self) -> None:
        payload = UserCreateSchema(name="Alice", email="alice@example.com", active=True)

        user = self.User.from_schema(payload)

        self.assertIsInstance(user, self.User)
        self.assertEqual(user.name, "Alice")
        self.assertEqual(user.email, "alice@example.com")
        self.assertTrue(user.active)

    def test_apply_schema_uses_partial_payload_semantics(self) -> None:
        user = self.User(name="Alice", email="alice@example.com", active=True, payload={})

        returned = user.apply_schema(UserUpdateSchema(email="alice.smith@example.com"))

        self.assertIs(returned, user)
        self.assertEqual(user.name, "Alice")
        self.assertEqual(user.email, "alice.smith@example.com")
        self.assertTrue(user.active)

    def test_to_schema_constructs_requested_schema(self) -> None:
        user = self.User(id=1, name="Alice", email="alice@example.com", active=True, payload={})

        schema_obj = user.to_schema(UserReadSchema)

        self.assertIsInstance(schema_obj, UserReadSchema)
        self.assertEqual(schema_obj.id, 1)
        self.assertEqual(schema_obj.email, "alice@example.com")

    def test_schema_fields_not_on_model_raise_clear_error(self) -> None:
        with self.assertRaises(SchemaMappingError):
            self.User.from_schema(
                UserCreateWithUnknownSchema(
                    name="Alice",
                    email="alice@example.com",
                    active=True,
                    unknown="value",
                )
            )

    def test_to_schema_rejects_fields_not_present_on_model(self) -> None:
        user = self.User(id=1, name="Alice", email="alice@example.com", active=True, payload={})

        with self.assertRaises(SchemaMappingError):
            user.to_schema(InvalidUserSchema)

    def test_non_pydantic_schema_objects_are_rejected(self) -> None:
        with self.assertRaises(SchemaMappingError):
            self.User.from_schema({"name": "Alice"})


if __name__ == "__main__":
    unittest.main()

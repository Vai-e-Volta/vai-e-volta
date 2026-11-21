# ruff: noqa: E402, I001
"""Shared fixtures for schema tests: one connection per test, always rolled back."""

from __future__ import annotations

import os

# Precisa rodar antes de qualquer import de app.* (pydantic-settings lê env em import time)
os.environ.setdefault("JWT_SECRET", "test-secret-com-pelo-menos-32-caracteres")
os.environ.setdefault("POSTGRES_PASSWORD", "fake")
os.environ.setdefault("APP_ENV", "test")

import uuid
from collections.abc import Callable, Generator
from datetime import date
from typing import Any

import pytest
from sqlalchemy import Connection, create_engine, text

from app.migrations import upgrade_database

InsertRow = Callable[..., Any]


@pytest.fixture
def db() -> Generator[Connection, None, None]:
    """Connection to a migrated database inside a transaction that is rolled back at the end."""
    upgrade_database()
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                yield connection
            finally:
                transaction.rollback()
    finally:
        engine.dispose()


@pytest.fixture
def insert_user(db: Connection) -> InsertRow:
    """Insert a fictitious user and return its id."""

    def _insert(**overrides: Any) -> uuid.UUID:
        suffix = uuid.uuid4().int % 10**11
        values: dict[str, Any] = {
            "full_name": "Pessoa Ficticia",
            "username": f"u{suffix:011d}",
            "email": f"u{suffix:011d}@example.invalid",
            "cpf": f"{suffix:011d}",
            "phone": "00000000000",
            "password_hash": "$argon2id$fake-test-hash",
            "cep": "00000000",
            "street": "Rua Ficticia",
            "number": "0",
            "neighborhood": "Bairro Ficticio",
            "city": "Cidade Ficticia",
            "state": "RS",
        } | overrides
        columns = ", ".join(values)
        params = ", ".join(f":{column}" for column in values)
        return db.scalar(
            text(f"INSERT INTO users ({columns}) VALUES ({params}) RETURNING id"), values
        )

    return _insert


@pytest.fixture
def insert_listing(db: Connection, insert_user: InsertRow) -> InsertRow:
    """Insert a valid listing (creating its owner if needed) and return its id."""

    def _insert(**overrides: Any) -> int:
        values: dict[str, Any] = {
            "owner_id": overrides.pop("owner_id") if "owner_id" in overrides else insert_user(),
            "category_id": db.scalar(text("SELECT min(id) FROM categories")),
            "title": "Furadeira de impacto",
            "description": "Item fictício para testes.",
            "daily_price": "25.00",
            "max_days": 7,
            "available_from": date(2026, 11, 1),
            "available_until": date(2026, 12, 31),
            "pickup_cep": "00000000",
            "pickup_street": "Rua Ficticia",
            "pickup_number": "0",
            "pickup_neighborhood": "Bairro Ficticio",
            "pickup_city": "Cidade Ficticia",
            "pickup_state": "RS",
        } | overrides
        columns = ", ".join(values)
        params = ", ".join(f":{column}" for column in values)
        return db.scalar(
            text(f"INSERT INTO listings ({columns}) VALUES ({params}) RETURNING id"), values
        )

    return _insert


@pytest.fixture
def insert_rental(db: Connection, insert_user: InsertRow, insert_listing: InsertRow) -> InsertRow:
    """Insert a rental (pending by default) and return its id."""

    def _insert(**overrides: Any) -> int:
        values: dict[str, Any] = {
            "listing_id": overrides.pop("listing_id", None) or insert_listing(),
            "renter_id": overrides.pop("renter_id", None) or insert_user(),
            "start_date": date(2026, 12, 10),
            "end_date": date(2026, 12, 14),
            "status": "pending",
            "daily_price_snapshot": "25.00",
            "estimated_total": "125.00",
            "listing_snapshot": '{"title": "Furadeira de impacto"}',
        } | overrides
        columns = ", ".join([*values, "expires_at"])
        params = ", ".join([*(f":{column}" for column in values), "now() + interval '48 hours'"])
        return db.scalar(
            text(f"INSERT INTO rentals ({columns}) VALUES ({params}) RETURNING id"), values
        )

    return _insert

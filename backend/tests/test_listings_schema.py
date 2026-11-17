"""H006-1: categories, listings, listing_photos, tags and listing_tags."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from sqlalchemy import Connection, create_engine, inspect, text
from sqlalchemy.exc import DataError, IntegrityError

from alembic import command
from app.migrations import upgrade_database

InsertRow = Callable[..., Any]
TABLES = {"categories", "listings", "listing_photos", "tags", "listing_tags"}
EXPECTED_CATEGORIES = [
    "Ferramentas",
    "Eletrônicos",
    "Esportes e lazer",
    "Casa e jardim",
    "Equipamentos",
    "Veículos",
    "Livros",
    "Festas e jogos",
]


def _alembic_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


def _rejects(db: Connection, statement: str, params: dict | None = None) -> None:
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text(statement), params or {})


def test_h006_1_migration_downgrade_and_upgrade() -> None:
    upgrade_database()
    command.downgrade(_alembic_config(), "20261117_0001")
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        assert TABLES.isdisjoint(inspect(engine).get_table_names())
        upgrade_database()
        inspector = inspect(engine)
        assert TABLES <= set(inspector.get_table_names())
        indexes = {
            index["name"]: index["column_names"] for index in inspector.get_indexes("listings")
        }
        assert indexes["ix_listings_status_available_until"] == ["status", "available_until"]
        assert indexes["ix_listings_created_at_id"] == ["created_at", "id"]
        assert indexes["ix_listings_daily_price_id"] == ["daily_price", "id"]
    finally:
        engine.dispose()


def test_DB_ADS_02_fixed_categories_and_required_fk(
    db: Connection, insert_listing: InsertRow
) -> None:
    names = list(db.scalars(text("SELECT name FROM categories ORDER BY id")))
    assert names == EXPECTED_CATEGORIES

    with pytest.raises(IntegrityError), db.begin_nested():
        insert_listing(category_id=None)
    with pytest.raises(IntegrityError), db.begin_nested():
        insert_listing(category_id=9999)
    _rejects(db, "INSERT INTO categories (name) VALUES ('Ferramentas')")


def test_DB_ITM_01_daily_price_between_1_and_5000(
    db: Connection, insert_listing: InsertRow
) -> None:
    for price in ("1.00", "5000.00"):
        assert insert_listing(daily_price=price)
    for price in ("0.99", "5000.01", "0", "-1"):
        with pytest.raises(IntegrityError), db.begin_nested():
            insert_listing(daily_price=price)


def test_DB_ADS_01_max_days_within_availability_window(
    db: Connection, insert_listing: InsertRow
) -> None:
    window = {"available_from": date(2026, 12, 1), "available_until": date(2026, 12, 10)}
    assert insert_listing(max_days=10, **window)
    for max_days in (11, 0):
        with pytest.raises(IntegrityError), db.begin_nested():
            insert_listing(max_days=max_days, **window)
    assert insert_listing(
        max_days=1, available_from=date(2026, 12, 5), available_until=date(2026, 12, 5)
    )
    with pytest.raises(IntegrityError), db.begin_nested():
        insert_listing(
            max_days=1, available_from=date(2026, 12, 6), available_until=date(2026, 12, 5)
        )


def test_h006_1_listing_fields_status_and_defaults(
    db: Connection, insert_listing: InsertRow
) -> None:
    listing_id = insert_listing()
    row = db.execute(
        text(
            "SELECT status, created_at IS NOT NULL, updated_at IS NOT NULL "
            "FROM listings WHERE id = :id"
        ),
        {"id": listing_id},
    ).one()
    assert row == ("active", True, True)

    for status in ("paused", "deleted"):
        db.execute(
            text("UPDATE listings SET status = :s WHERE id = :id"), {"s": status, "id": listing_id}
        )
    _rejects(db, "UPDATE listings SET status = 'removed' WHERE id = :id", {"id": listing_id})

    for field, value in (
        ("title", ""),
        ("title", "x" * 81),
        ("description", "x" * 1001),
        ("pickup_cep", "123"),
        ("pickup_state", "rs"),
        ("owner_id", None),
    ):
        with pytest.raises((IntegrityError, DataError)), db.begin_nested():
            insert_listing(**{field: value})


def test_h006_1_photos_positions_and_tags(db: Connection, insert_listing: InsertRow) -> None:
    listing_id = insert_listing()
    insert_photo = "INSERT INTO listing_photos (listing_id, position, filename) VALUES (:l, :p, :f)"
    for position in range(1, 6):
        db.execute(text(insert_photo), {"l": listing_id, "p": position, "f": f"{position}.jpg"})
    _rejects(db, insert_photo, {"l": listing_id, "p": 1, "f": "dup.jpg"})
    for position in (0, 6):
        _rejects(db, insert_photo, {"l": insert_listing(), "p": position, "f": "x.jpg"})

    insert_tag = "INSERT INTO tags (name, normalized_name) VALUES (:n, :nn) RETURNING id"
    tag_id = db.scalar(text(insert_tag), {"n": "Elétrica", "nn": "eletrica"})
    _rejects(db, insert_tag, {"n": "ELETRICA", "nn": "eletrica"})
    _rejects(db, insert_tag, {"n": "Pintura", "nn": "Pintura"})
    _rejects(db, insert_tag, {"n": "Pintura", "nn": "pintúra"})
    with pytest.raises(DataError), db.begin_nested():
        db.execute(text(insert_tag), {"n": "x" * 31, "nn": "x" * 31})

    insert_link = "INSERT INTO listing_tags (listing_id, tag_id) VALUES (:l, :t)"
    db.execute(text(insert_link), {"l": listing_id, "t": tag_id})
    _rejects(db, insert_link, {"l": listing_id, "t": tag_id})

    db.execute(text("DELETE FROM listings WHERE id = :id"), {"id": listing_id})
    assert (
        db.scalar(
            text("SELECT count(*) FROM listing_photos WHERE listing_id = :id"), {"id": listing_id}
        )
        == 0
    )
    assert (
        db.scalar(
            text("SELECT count(*) FROM listing_tags WHERE listing_id = :id"), {"id": listing_id}
        )
        == 0
    )
    assert db.scalar(text("SELECT count(*) FROM tags WHERE id = :id"), {"id": tag_id}) == 1

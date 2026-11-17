"""H013-1: favorites table (RN-31)."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from sqlalchemy import Connection, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.migrations import upgrade_database

InsertRow = Callable[..., Any]
INSERT_FAVORITE = "INSERT INTO favorites (user_id, listing_id) VALUES (:u, :l)"


def test_h013_1_migration_downgrade_and_upgrade() -> None:
    upgrade_database()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.downgrade(config, "20261117_0002")
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        assert "favorites" not in inspect(engine).get_table_names()
        upgrade_database()
        primary_key = inspect(engine).get_pk_constraint("favorites")
        assert primary_key["constrained_columns"] == ["user_id", "listing_id"]
    finally:
        engine.dispose()


def test_h013_1_unique_favorite_with_foreign_keys(
    db: Connection, insert_user: InsertRow, insert_listing: InsertRow
) -> None:
    user_id = insert_user()
    listing_id = insert_listing()
    db.execute(text(INSERT_FAVORITE), {"u": user_id, "l": listing_id})

    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text(INSERT_FAVORITE), {"u": user_id, "l": listing_id})
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text(INSERT_FAVORITE), {"u": user_id, "l": -1})
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text(INSERT_FAVORITE),
            {"u": "00000000-0000-0000-0000-000000000000", "l": listing_id},
        )


def test_h013_1_favorite_is_kept_when_listing_is_paused_or_deleted(
    db: Connection, insert_user: InsertRow, insert_listing: InsertRow
) -> None:
    user_id = insert_user()
    listing_id = insert_listing()
    db.execute(text(INSERT_FAVORITE), {"u": user_id, "l": listing_id})

    for status in ("paused", "deleted"):
        db.execute(
            text("UPDATE listings SET status = :s WHERE id = :id"),
            {"s": status, "id": listing_id},
        )
        count = db.scalar(
            text("SELECT count(*) FROM favorites WHERE user_id = :u AND listing_id = :l"),
            {"u": user_id, "l": listing_id},
        )
        assert count == 1

    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("DELETE FROM listings WHERE id = :id"), {"id": listing_id})

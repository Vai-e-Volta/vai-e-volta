"""H016-1: rentals table, no-overlap constraint (RN-42) and inclusive periods (RN-36)."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from sqlalchemy import Connection, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.migrations import upgrade_database
from app.services.rental_period import rental_days

InsertRow = Callable[..., Any]


def _period(start: tuple[int, int], end: tuple[int, int]) -> dict[str, date]:
    return {"start_date": date(2026, *start), "end_date": date(2026, *end)}


def test_h016_1_migration_downgrade_and_upgrade() -> None:
    upgrade_database()
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.downgrade(config, "20261117_0003")
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        assert "rentals" not in inspect(engine).get_table_names()
        upgrade_database()
        indexes = {
            index["name"]: index["column_names"] for index in inspect(engine).get_indexes("rentals")
        }
        assert indexes["ix_rentals_listing_id_status"] == ["listing_id", "status"]
        assert indexes["ix_rentals_renter_id_status"] == ["renter_id", "status"]
    finally:
        engine.dispose()


def test_UT_RNT_01_duration_is_inclusive() -> None:
    assert rental_days(date(2026, 10, 10), date(2026, 10, 10)) == 1
    assert rental_days(date(2026, 10, 10), date(2026, 10, 14)) == 5
    assert rental_days(date(2026, 12, 31), date(2027, 1, 1)) == 2
    with pytest.raises(ValueError):
        rental_days(date(2026, 10, 15), date(2026, 10, 14))


def test_DB_RNT_01_accepted_rentals_do_not_overlap(
    db: Connection, insert_listing: InsertRow, insert_rental: InsertRow
) -> None:
    listing_id = insert_listing()
    insert_rental(listing_id=listing_id, status="accepted", **_period((10, 10), (10, 14)))

    # Same last day / first day overlaps: intervals are inclusive on both ends.
    for status in ("accepted", "completed"):
        with pytest.raises(IntegrityError), db.begin_nested():
            insert_rental(listing_id=listing_id, status=status, **_period((10, 14), (10, 16)))
        with pytest.raises(IntegrityError), db.begin_nested():
            insert_rental(listing_id=listing_id, status=status, **_period((10, 8), (10, 20)))

    # Return on the 14th frees a new pickup on the 15th.
    insert_rental(listing_id=listing_id, status="accepted", **_period((10, 15), (10, 16)))

    # Pending, rejected, expired and canceled rows do not block the period (RN-44).
    for status in ("pending", "rejected", "expired", "canceled"):
        insert_rental(listing_id=listing_id, status=status, **_period((10, 12), (10, 13)))

    # Other listings are independent.
    insert_rental(status="accepted", **_period((10, 10), (10, 14)))

    # Accepting an overlapping pending proposal is rejected by the database too.
    pending_id = insert_rental(listing_id=listing_id, **_period((10, 13), (10, 15)))
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text("UPDATE rentals SET status = 'accepted' WHERE id = :id"), {"id": pending_id}
        )


def test_h016_1_rental_checks_and_defaults(db: Connection, insert_rental: InsertRow) -> None:
    rental_id = insert_rental()
    row = db.execute(
        text(
            "SELECT status, expires_at - created_at, listing_snapshot ->> 'title' "
            "FROM rentals WHERE id = :id"
        ),
        {"id": rental_id},
    ).one()
    assert row[0] == "pending"
    assert row[1].total_seconds() == 48 * 3600
    assert row[2] == "Furadeira de impacto"

    for overrides in (
        _period((10, 15), (10, 14)),
        {"status": "active"},
        {"daily_price_snapshot": "0"},
        {"estimated_total": "0"},
        {"listing_snapshot": "[]"},
        {"listing_id": -1},
    ):
        with pytest.raises(IntegrityError), db.begin_nested():
            insert_rental(**overrides)

    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text("UPDATE rentals SET expires_at = created_at WHERE id = :id"), {"id": rental_id}
        )

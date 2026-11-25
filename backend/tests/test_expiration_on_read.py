"""H018-3: overdue pending proposals read as expired even when the worker has not run."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.models import User
from app.services.account import delete_account
from app.services.authentication import hash_password
from app.services.listing_lifecycle import change_listing_status
from app.services.proposal_expiry import effective_status, proposal_has_expired
from app.services.rental_situation import rental_situation, today_br
from app.services.rentals import list_rentals

InsertRow = Callable[..., Any]


def _make_overdue(db: Connection, rental_id: int) -> None:
    """Deadline already passed, status still pending: the worker is stopped."""
    db.execute(
        text(
            "UPDATE rentals SET created_at = now() - interval '50 hours', "
            "expires_at = now() - interval '2 hours' WHERE id = :id"
        ),
        {"id": rental_id},
    )


def _future_period() -> dict[str, date]:
    today = today_br()
    return {"start_date": today + timedelta(days=5), "end_date": today + timedelta(days=6)}


def _status(db: Connection, rental_id: int) -> str:
    return db.scalar(text("SELECT status FROM rentals WHERE id = :id"), {"id": rental_id})


@pytest.mark.parametrize(
    ("expires_in", "start_in_days", "expected"),
    [
        (timedelta(hours=1), 3, "pending"),
        (timedelta(0), 3, "expired"),
        (timedelta(hours=-1), 3, "expired"),
        (timedelta(hours=1), 0, "pending"),
        (timedelta(hours=1), -1, "expired"),
    ],
)
def test_API_RNT_10_effective_status_matches_rental_situation(
    expires_in: timedelta, start_in_days: int, expected: str
) -> None:
    now = datetime(2026, 11, 22, 15, 0, tzinfo=UTC)
    start = today_br(now) + timedelta(days=start_in_days)
    expires_at = now + expires_in

    assert effective_status("pending", expires_at, start, now) == expected
    assert proposal_has_expired(expires_at, start, now) is (expected == "expired")
    situation = rental_situation("pending", start, start + timedelta(days=1), expires_at, now=now)
    assert situation == ("Expirado" if expected == "expired" else "Aguardando")
    # Other statuses are never changed.
    for status in ("accepted", "rejected", "canceled", "completed", "expired"):
        assert effective_status(status, now - timedelta(days=9), start, now) == status


def test_API_RNT_10_list_shows_overdue_pending_as_expired_in_history(
    db: Connection, insert_user: InsertRow, insert_listing: InsertRow, insert_rental: InsertRow
) -> None:
    renter_id = insert_user()
    owner_id = insert_user()
    listing_id = insert_listing(owner_id=owner_id)
    overdue = insert_rental(listing_id=listing_id, renter_id=renter_id, **_future_period())
    _make_overdue(db, overdue)
    open_one = insert_rental(listing_id=listing_id, renter_id=renter_id, **_future_period())

    session = Session(bind=db)
    renter = session.get(User, renter_id)
    owner = session.get(User, owner_id)
    for user, role in ((renter, "renter"), (owner, "owner")):
        active = list_rentals(session, user, role, "active", 20, None)
        history = list_rentals(session, user, role, "history", 20, None)

        assert [item.id for item in active["items"]] == [open_one]
        assert active["items"][0].status == "pending"
        assert active["items"][0].situation == "Aguardando"

        assert [item.id for item in history["items"]] == [overdue]
        assert history["items"][0].status == "expired"
        assert history["items"][0].situation == "Expirado"

    # Nothing was written: the database still says pending until the worker runs.
    assert _status(db, overdue) == "pending"


def test_API_RNT_10_pausing_listing_expires_overdue_pending_without_rejection_notice(
    db: Connection, insert_user: InsertRow, insert_listing: InsertRow, insert_rental: InsertRow
) -> None:
    owner_id = insert_user()
    listing_id = insert_listing(owner_id=owner_id)
    overdue = insert_rental(listing_id=listing_id, **_future_period())
    _make_overdue(db, overdue)
    open_one = insert_rental(listing_id=listing_id, **_future_period())

    session = Session(bind=db)
    change_listing_status(session, session.get(User, owner_id), listing_id, "pause")

    assert _status(db, overdue) == "expired"
    assert _status(db, open_one) == "rejected"
    notified = list(
        db.scalars(
            text(
                "SELECT rental_id FROM notifications WHERE type = 'proposal_rejected' "
                "AND rental_id = ANY(:ids)"
            ),
            {"ids": [overdue, open_one]},
        )
    )
    assert notified == [open_one]


def test_API_RNT_10_deleting_account_expires_overdue_pending_instead_of_canceling(
    db: Connection, insert_user: InsertRow, insert_listing: InsertRow, insert_rental: InsertRow
) -> None:
    renter_id = insert_user(password_hash=hash_password("Senha-de-teste-123"))
    overdue = insert_rental(renter_id=renter_id, **_future_period())
    _make_overdue(db, overdue)
    open_one = insert_rental(renter_id=renter_id, **_future_period())
    other_user_overdue = insert_rental(**_future_period())
    _make_overdue(db, other_user_overdue)

    session = Session(bind=db)
    delete_account(session, session.get(User, renter_id), "Senha-de-teste-123")

    assert _status(db, overdue) == "expired"
    assert _status(db, open_one) == "canceled"
    # Rows of other users are left to the worker.
    assert _status(db, other_user_overdue) == "pending"

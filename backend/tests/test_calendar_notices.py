"""H023-3: calendar notices for both parties of accepted rentals (F-50)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.services.rental_situation import today_br
from app.worker.calendar_notices import calendar_notices, send_calendar_notices
from app.worker.registry import registry

InsertRow = Callable[..., Any]

# Frozen clock: 23:30 in São Paulo on Nov 22 is already Nov 23 in UTC.
NOW = datetime(2026, 11, 23, 2, 30, tzinfo=UTC)
TODAY = today_br(NOW)
TOMORROW = TODAY + timedelta(days=1)


def _notices(db: Connection, rental_ids: list[int]) -> list[tuple]:
    return [
        tuple(row)
        for row in db.execute(
            text(
                "SELECT rental_id, user_id, type, payload FROM notifications "
                "WHERE rental_id = ANY(:ids) ORDER BY rental_id, type, payload ->> 'role'"
            ),
            {"ids": rental_ids},
        ).all()
    ]


def _owner(db: Connection, rental_id: int):
    return db.scalar(
        text(
            "SELECT l.owner_id FROM rentals r JOIN listings l ON l.id = r.listing_id "
            "WHERE r.id = :id"
        ),
        {"id": rental_id},
    )


def test_JOB_calendar_notices_is_registered_every_15_minutes() -> None:
    import app.worker.__main__  # noqa: F401

    job = registry.get("calendar_notices")
    assert job.function is calendar_notices
    assert job.interval_seconds == 15 * 60


def test_JOB_one_notice_per_party_and_event_even_when_run_twice(
    db: Connection, insert_user: InsertRow, insert_rental: InsertRow
) -> None:
    assert str(TODAY) == "2026-11-22"
    renter = insert_user()
    starting = insert_rental(
        renter_id=renter,
        status="accepted",
        start_date=TOMORROW,
        end_date=TOMORROW + timedelta(days=3),
    )
    one_day = insert_rental(
        renter_id=renter, status="accepted", start_date=TOMORROW, end_date=TOMORROW
    )
    due = insert_rental(
        renter_id=renter,
        status="accepted",
        start_date=TODAY - timedelta(days=2),
        end_date=TOMORROW,
    )
    overdue = insert_rental(
        renter_id=renter,
        status="accepted",
        start_date=TODAY - timedelta(days=5),
        end_date=TODAY - timedelta(days=1),
    )
    in_progress = insert_rental(
        renter_id=renter,
        status="accepted",
        start_date=TODAY - timedelta(days=1),
        end_date=TODAY + timedelta(days=4),
    )
    ends_today = insert_rental(
        renter_id=renter,
        status="accepted",
        start_date=TODAY - timedelta(days=1),
        end_date=TODAY,
    )
    ignored = [
        insert_rental(renter_id=renter, status=status, start_date=TOMORROW, end_date=TOMORROW)
        for status in ("pending", "rejected", "expired", "canceled")
    ]
    ignored.append(
        insert_rental(
            renter_id=renter,
            status="completed",
            start_date=TODAY - timedelta(days=9),
            end_date=TODAY - timedelta(days=3),
        )
    )
    all_ids = [starting, one_day, due, overdue, in_progress, ends_today, *ignored]

    session = Session(bind=db)
    first = send_calendar_notices(session, NOW)
    session.flush()
    notices = _notices(db, all_ids)

    expected_events = {
        (starting, "rental_starting"),
        (one_day, "rental_starting"),
        (one_day, "return_due"),
        (due, "return_due"),
        (overdue, "rental_overdue"),
    }
    assert first == len(expected_events) * 2
    assert {(rental_id, kind) for rental_id, _, kind, _ in notices} == expected_events
    for rental_id, kind in expected_events:
        rows = [row for row in notices if row[0] == rental_id and row[2] == kind]
        assert {row[1] for row in rows} == {renter, _owner(db, rental_id)}
        assert sorted(row[3]["role"] for row in rows) == ["owner", "renter"]

    # Second and third runs (same instant and 15 minutes later) add nothing.
    assert send_calendar_notices(session, NOW) == 0
    assert send_calendar_notices(session, NOW + timedelta(minutes=15)) == 0
    session.flush()
    assert _notices(db, all_ids) == notices


def test_JOB_payload_has_no_personal_data_and_uses_snapshot_title(
    db: Connection, insert_rental: InsertRow
) -> None:
    rental_id = insert_rental(
        status="accepted",
        start_date=TOMORROW,
        end_date=TOMORROW + timedelta(days=2),
        listing_snapshot='{"title": "Furadeira (cópia)"}',
    )
    send_calendar_notices(Session(bind=db), NOW)
    payloads = [row[3] for row in _notices(db, [rental_id])]

    listing_id = db.scalar(text("SELECT listing_id FROM rentals WHERE id = :id"), {"id": rental_id})
    assert payloads == [
        {
            "rental_id": rental_id,
            "listing_id": listing_id,
            "listing_title": "Furadeira (cópia)",
            "start_date": str(TOMORROW),
            "role": role,
        }
        for role in ("owner", "renter")
    ]


def test_JOB_overdue_notice_is_sent_once_and_deleted_accounts_are_skipped(
    db: Connection, insert_user: InsertRow, insert_rental: InsertRow
) -> None:
    renter = insert_user()
    rental_id = insert_rental(
        renter_id=renter,
        status="accepted",
        start_date=TODAY - timedelta(days=4),
        end_date=TODAY - timedelta(days=1),
    )
    db.execute(text("UPDATE users SET deleted_at = now() WHERE id = :id"), {"id": renter})

    session = Session(bind=db)
    assert send_calendar_notices(session, NOW) == 1
    # Still overdue on the following days: no new notice.
    assert send_calendar_notices(session, NOW + timedelta(days=1)) == 0
    assert send_calendar_notices(session, NOW + timedelta(days=5)) == 0
    session.flush()
    notices = _notices(db, [rental_id])
    assert [(row[1], row[2], row[3]["role"]) for row in notices] == [
        (_owner(db, rental_id), "rental_overdue", "owner")
    ]

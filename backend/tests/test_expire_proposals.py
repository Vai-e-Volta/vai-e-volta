"""H018-2: worker job that expires pending proposals (RN-47)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.services.rental_situation import today_br
from app.worker.expire_proposals import expire_proposals
from app.worker.registry import registry

InsertRow = Callable[..., Any]


def _set_times(db: Connection, rental_id: int, created_at: datetime, expires_at: datetime) -> None:
    db.execute(
        text("UPDATE rentals SET created_at = :c, expires_at = :e WHERE id = :id"),
        {"c": created_at, "e": expires_at, "id": rental_id},
    )


def _statuses(db: Connection, ids: list[int]) -> list[str]:
    rows = dict(
        db.execute(text("SELECT id, status FROM rentals WHERE id = ANY(:ids)"), {"ids": ids}).all()
    )
    return [rows[rental_id] for rental_id in ids]


def test_JOB_expire_proposals_is_registered_every_minute() -> None:
    import app.worker.__main__  # noqa: F401

    job = registry.get("expire_proposals")
    assert job.function is expire_proposals
    assert job.interval_seconds == 60


def test_API_RNT_10_job_expires_by_deadline_or_start_date_and_is_idempotent(
    db: Connection, insert_rental: InsertRow
) -> None:
    # Frozen clock: 60 hours after the proposals were created.
    created = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=60)
    now = created + timedelta(hours=60)
    today = today_br(now)
    future = {"start_date": today + timedelta(days=5), "end_date": today + timedelta(days=7)}

    past_deadline = insert_rental(**future)
    _set_times(db, past_deadline, created, created + timedelta(hours=48))

    on_deadline = insert_rental(**future)
    _set_times(db, on_deadline, created, now)

    still_open = insert_rental(**future)
    _set_times(db, still_open, created, now + timedelta(minutes=1))

    start_passed = insert_rental(start_date=today - timedelta(days=1), end_date=today)
    _set_times(db, start_passed, created, now + timedelta(hours=10))

    starts_today = insert_rental(start_date=today, end_date=today + timedelta(days=1))
    _set_times(db, starts_today, created, now + timedelta(hours=10))

    others = []
    for status in ("accepted", "rejected", "canceled", "completed", "expired"):
        rental_id = insert_rental(
            status=status,
            start_date=today - timedelta(days=30 + len(others) * 5),
            end_date=today - timedelta(days=28 + len(others) * 5),
        )
        _set_times(db, rental_id, created, created + timedelta(hours=48))
        others.append(rental_id)

    ids = [past_deadline, on_deadline, still_open, start_passed, starts_today, *others]
    expected = [
        "expired",
        "expired",
        "pending",
        "expired",
        "pending",
        "accepted",
        "rejected",
        "canceled",
        "completed",
        "expired",
    ]

    session = Session(bind=db)
    expire_proposals(session, now)
    session.flush()
    assert _statuses(db, ids) == expected

    # Running again at the same instant changes nothing.
    expire_proposals(session, now)
    session.flush()
    assert _statuses(db, ids) == expected

    # Later, the remaining proposals reach their deadlines too.
    expire_proposals(session, now + timedelta(days=2))
    session.flush()
    assert _statuses(db, [still_open, starts_today]) == ["expired", "expired"]


def test_JOB_expire_uses_brazilian_calendar_day(db: Connection, insert_rental: InsertRow) -> None:
    # 01:30 UTC on Nov 23 is still Nov 22 in São Paulo (UTC-3): a proposal starting on
    # Nov 22 has not started "before today" yet.
    now = datetime(2026, 11, 23, 1, 30, tzinfo=UTC)
    rental_id = insert_rental(start_date=today_br(now), end_date=today_br(now))
    _set_times(db, rental_id, now - timedelta(hours=1), now + timedelta(hours=47))

    session = Session(bind=db)
    expire_proposals(session, now)
    session.flush()
    assert _statuses(db, [rental_id]) == ["pending"]

    expire_proposals(session, now + timedelta(hours=3))
    session.flush()
    assert _statuses(db, [rental_id]) == ["expired"]

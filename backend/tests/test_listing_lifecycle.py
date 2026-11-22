from __future__ import annotations

import json
from collections.abc import Generator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import app
from app.security.session import create_session_token
from app.services.rental_situation import today_br


@pytest.fixture
def owner_client(db: Connection, insert_user) -> Generator[tuple[TestClient, object], None, None]:
    owner_id = insert_user()

    def override_db() -> Generator[Session, None, None]:
        with Session(
            bind=db, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            client.cookies.set("vv_session", create_session_token(owner_id, 0))
            yield client, owner_id
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_pause_rejects_pending_and_notifies_once(
    db: Connection, insert_listing, insert_user, insert_rental, owner_client
) -> None:
    client, owner_id = owner_client
    renter_ids = [insert_user(), insert_user()]
    listing_id = insert_listing(owner_id=owner_id, available_until=today_br() + timedelta(days=30))
    rental_ids = [
        insert_rental(
            listing_id=listing_id,
            renter_id=renter_id,
            listing_snapshot=json.dumps({"title": "Título da proposta"}),
        )
        for renter_id in renter_ids
    ]
    assert client.post(f"/api/listings/{listing_id}/pause").status_code == 204
    assert client.post(f"/api/listings/{listing_id}/pause").status_code == 204
    assert (
        db.scalar(text("SELECT status FROM listings WHERE id=:id"), {"id": listing_id}) == "paused"
    )
    assert list(
        db.scalars(text("SELECT status FROM rentals WHERE id = ANY(:ids)"), {"ids": rental_ids})
    ) == ["rejected", "rejected"]
    notices = db.execute(
        text(
            "SELECT user_id, rental_id, payload FROM notifications "
            "WHERE rental_id = ANY(:ids) ORDER BY rental_id"
        ),
        {"ids": rental_ids},
    ).all()
    assert len(notices) == 2
    assert {row.user_id for row in notices} == set(renter_ids)
    assert all(
        row.payload
        == {
            "listing_id": listing_id,
            "listing_title": "Título da proposta",
            "reason": "listing_unavailable",
        }
        for row in notices
    )
    assert listing_id not in [item["id"] for item in client.get("/api/listings").json()["items"]]
    assert client.post(f"/api/listings/{listing_id}/resume").status_code == 204
    assert (
        db.scalar(text("SELECT status FROM listings WHERE id=:id"), {"id": listing_id}) == "active"
    )


@pytest.mark.parametrize("action", ["pause", "delete"])
@pytest.mark.parametrize("start_offset,end_offset", [(-1, 1), (1, 2), (-1, 0)])
def test_pause_and_delete_block_current_or_future_accepted_rentals(
    db: Connection, insert_listing, insert_rental, owner_client, action, start_offset, end_offset
) -> None:
    client, owner_id = owner_client
    today = today_br()
    listing_id = insert_listing(owner_id=owner_id, available_until=today + timedelta(days=30))
    insert_rental(
        listing_id=listing_id,
        status="accepted",
        start_date=today + timedelta(days=start_offset),
        end_date=today + timedelta(days=end_offset),
    )
    response = (
        client.post(f"/api/listings/{listing_id}/pause")
        if action == "pause"
        else client.delete(f"/api/listings/{listing_id}")
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LISTING_HAS_ACTIVE_RENTAL"
    assert (
        db.scalar(text("SELECT status FROM listings WHERE id=:id"), {"id": listing_id}) == "active"
    )


def test_delete_is_private_soft_and_preserves_history(
    db: Connection, insert_listing, insert_user, insert_rental, owner_client
) -> None:
    client, owner_id = owner_client
    listing_id = insert_listing(owner_id=owner_id, available_until=today_br() + timedelta(days=30))
    renter_id = insert_user()
    rental_id = insert_rental(listing_id=listing_id, renter_id=renter_id)
    db.execute(
        text("INSERT INTO favorites (user_id, listing_id) VALUES (:user, :listing)"),
        {"user": renter_id, "listing": listing_id},
    )
    client.cookies.set("vv_session", create_session_token(renter_id, 0))
    before = client.get("/api/listings", params={"favorites": True}).json()
    assert listing_id in [item["id"] for item in before["items"]]
    client.cookies.set("vv_session", create_session_token(owner_id, 0))
    assert client.delete(f"/api/listings/{listing_id}").status_code == 204
    assert client.delete(f"/api/listings/{listing_id}").status_code == 204
    assert (
        db.scalar(text("SELECT status FROM listings WHERE id=:id"), {"id": listing_id}) == "deleted"
    )
    assert (
        db.scalar(text("SELECT status FROM rentals WHERE id=:id"), {"id": rental_id}) == "rejected"
    )
    assert (
        db.scalar(text("SELECT count(*) FROM notifications WHERE rental_id=:id"), {"id": rental_id})
        == 1
    )
    client.cookies.set("vv_session", create_session_token(renter_id, 0))
    assert listing_id not in [
        item["id"]
        for item in client.get("/api/listings", params={"favorites": True}).json()["items"]
    ]
    owner_username = db.scalar(text("SELECT username FROM users WHERE id=:id"), {"id": owner_id})
    profile = client.get(f"/api/users/{owner_username}")
    assert profile.status_code == 200
    assert listing_id not in [item["id"] for item in profile.json()["listings"]]
    assert client.put(f"/api/listings/{listing_id}/favorite").status_code == 404
    client.cookies.set("vv_session", create_session_token(owner_id, 0))
    assert client.post(f"/api/listings/{listing_id}/resume").status_code == 409


def test_lifecycle_authorization_and_expired_window(
    db: Connection, insert_listing, insert_user, owner_client
) -> None:
    client, owner_id = owner_client
    other_id = insert_user()
    other_listing = insert_listing(owner_id=other_id)
    assert client.post(f"/api/listings/{other_listing}/pause").status_code == 403
    assert client.post(f"/api/listings/{other_listing}/resume").status_code == 403
    assert client.delete(f"/api/listings/{other_listing}").status_code == 403
    assert client.delete("/api/listings/999999999").status_code == 404
    expired = insert_listing(
        owner_id=owner_id,
        status="paused",
        available_from=today_br() - timedelta(days=10),
        available_until=today_br() - timedelta(days=1),
    )
    assert client.post(f"/api/listings/{expired}/resume").status_code == 409
    anonymous = TestClient(app)
    assert anonymous.delete(f"/api/listings/{expired}").status_code == 401


def test_rejection_and_notifications_roll_back_if_commit_fails(
    db: Connection, insert_listing, insert_user, insert_rental, owner_client, monkeypatch
) -> None:
    client, owner_id = owner_client
    listing_id = insert_listing(owner_id=owner_id)
    rental_id = insert_rental(listing_id=listing_id, renter_id=insert_user())

    def fail_commit(_session: Session) -> None:
        raise RuntimeError("simulated database failure")

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="simulated database failure"):
            client.post(f"/api/listings/{listing_id}/pause")
    assert (
        db.scalar(text("SELECT status FROM listings WHERE id=:id"), {"id": listing_id}) == "active"
    )
    assert (
        db.scalar(text("SELECT status FROM rentals WHERE id=:id"), {"id": rental_id}) == "pending"
    )
    assert (
        db.scalar(text("SELECT count(*) FROM notifications WHERE rental_id=:id"), {"id": rental_id})
        == 0
    )

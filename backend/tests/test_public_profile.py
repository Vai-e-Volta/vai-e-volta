from __future__ import annotations

from collections.abc import Callable, Generator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import app
from app.security.session import SESSION_COOKIE, create_session_token
from app.worker.tasks import anonymize_accounts


@pytest.fixture
def public_profile_client(
    db: Connection,
    insert_user: Callable[..., UUID],
) -> Generator[TestClient, None, None]:
    """Client authenticated as a fictitious user, using the test transaction."""
    viewer_id = insert_user()
    token_version = db.scalar(
        text("SELECT token_version FROM users WHERE id = :user_id"),
        {"user_id": viewer_id},
    )
    token = create_session_token(viewer_id, token_version)

    def override_db() -> Generator[Session, None, None]:
        with Session(
            bind=db,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            client.cookies.set(SESSION_COOKIE, token)
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_public_profile_requires_authentication(
    public_profile_client: TestClient,
    insert_user: Callable[..., UUID],
    db: Connection,
) -> None:
    user_id = insert_user()
    username = db.scalar(
        text("SELECT username FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    )
    public_profile_client.cookies.clear()

    response = public_profile_client.get(f"/api/users/{username}")

    assert response.status_code == 401


def test_public_profile_returns_404_for_unknown_username(
    public_profile_client: TestClient,
) -> None:
    response = public_profile_client.get("/api/users/usuario_inexistente")

    assert response.status_code == 404


@pytest.mark.parametrize("excluded_field", ["deleted_at", "anonymized_at"])
def test_public_profile_does_not_expose_excluded_users(
    public_profile_client: TestClient,
    insert_user: Callable[..., UUID],
    db: Connection,
    excluded_field: str,
) -> None:
    now = datetime.now(UTC)
    if excluded_field == "anonymized_at":
        user_id = insert_user(
            deleted_at=now - timedelta(days=366), purge_after=now - timedelta(days=1)
        )
        with Session(bind=db, join_transaction_mode="create_savepoint") as session:
            anonymize_accounts(session, now)
            session.commit()
    else:
        user_id = insert_user(deleted_at=now)
    username = db.scalar(
        text("SELECT username FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    )

    response = public_profile_client.get(f"/api/users/{username}")

    assert response.status_code == 404


def test_public_profile_returns_only_public_data_and_active_listings(
    public_profile_client: TestClient,
    insert_user: Callable[..., UUID],
    insert_listing: Callable[..., int],
    db: Connection,
) -> None:
    user_id = insert_user()
    username = db.scalar(
        text("SELECT username FROM users WHERE id = :user_id"),
        {"user_id": user_id},
    )
    today = db.scalar(text("SELECT CURRENT_DATE"))

    insert_listing(
        owner_id=user_id,
        title="Anúncio disponível até hoje",
        available_until=today,
    )
    insert_listing(
        owner_id=user_id,
        title="Anúncio com início futuro",
        available_from=today + timedelta(days=30),
        available_until=today + timedelta(days=60),
    )
    insert_listing(
        owner_id=user_id,
        title="Anúncio pausado",
        status="paused",
        available_until=today + timedelta(days=10),
    )
    insert_listing(
        owner_id=user_id,
        title="Anúncio excluído",
        status="deleted",
        available_until=today + timedelta(days=10),
    )
    insert_listing(
        owner_id=user_id,
        title="Anúncio vencido",
        status="active",
        available_until=today - timedelta(days=1),
    )

    response = public_profile_client.get(f"/api/users/{username}")

    assert response.status_code == 200
    data = response.json()

    assert set(data) == {
        "username",
        "neighborhood",
        "city",
        "created_at",
        "listings",
    }
    assert data["username"] == username
    assert data["neighborhood"] == "Bairro Ficticio"
    assert data["city"] == "Cidade Ficticia"

    assert all(set(listing) == {"id", "title", "daily_price"} for listing in data["listings"])
    assert {listing["title"] for listing in data["listings"]} == {
        "Anúncio disponível até hoje",
        "Anúncio com início futuro",
    }

    private_fields = {
        "full_name",
        "email",
        "cpf",
        "phone",
        "cep",
        "street",
        "number",
        "complement",
        "state",
        "password_hash",
        "token_version",
        "deleted_at",
        "anonymized_at",
    }
    assert private_fields.isdisjoint(data)
    assert all(private_fields.isdisjoint(listing) for listing in data["listings"])

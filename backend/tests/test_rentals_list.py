from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_db
from app.db import get_engine
from app.main import app
from app.migrations import upgrade_database
from app.models import Category, Listing, ListingPhoto, Rental, User
from app.security.session import create_session_token


@pytest.fixture
def rentals_context() -> Generator[tuple[TestClient, uuid.UUID, uuid.UUID, uuid.UUID], None, None]:
    upgrade_database()
    engine = get_engine()
    user_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]

    def override_db() -> Generator[Session, None, None]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with Session(engine) as session:
            users = []
            for index, user_id in enumerate(user_ids):
                suffix = f"{user_id.int % 10**11:011d}"
                users.append(
                    User(
                        id=user_id,
                        full_name=f"Pessoa {index}",
                        username=f"rental_{suffix}",
                        email=f"rental-{suffix}@example.invalid",
                        cpf=suffix,
                        phone=f"5199999{index:04d}",
                        password_hash="test-only-hash",
                        cep="96200000",
                        street="Rua Teste",
                        number="1",
                        neighborhood="Centro",
                        city="Rio Grande",
                        state="RS",
                    )
                )
            session.add_all(users)
            session.flush()
            category_id = session.scalar(select(Category.id).order_by(Category.id).limit(1))
            listing = Listing(
                owner_id=user_ids[1],
                category_id=category_id,
                title="Anúncio atual",
                description="Descrição",
                daily_price=Decimal("50.00"),
                max_days=10,
                available_from=date.today(),
                available_until=date.today() + timedelta(days=40),
                pickup_cep="96200000",
                pickup_street="Rua Teste",
                pickup_number="1",
                pickup_neighborhood="Centro",
                pickup_city="Rio Grande",
                pickup_state="RS",
            )
            session.add(listing)
            session.flush()
            session.add(ListingPhoto(listing_id=listing.id, position=1, filename="capa.jpg"))
            session.add_all(
                [
                    Rental(
                        listing_id=listing.id,
                        renter_id=user_ids[0],
                        start_date=date.today() + timedelta(days=2),
                        end_date=date.today() + timedelta(days=4),
                        status="pending",
                        daily_price_snapshot=Decimal("25.00"),
                        estimated_total=Decimal("75.00"),
                        listing_snapshot={"title": "Título congelado"},
                        expires_at=datetime.now(UTC) + timedelta(days=2),
                    ),
                    Rental(
                        listing_id=listing.id,
                        renter_id=user_ids[2],
                        start_date=date.today() - timedelta(days=1),
                        end_date=date.today() + timedelta(days=1),
                        status="accepted",
                        daily_price_snapshot=Decimal("30.00"),
                        estimated_total=Decimal("90.00"),
                        listing_snapshot={"title": "Título aceito"},
                        expires_at=datetime.now(UTC) + timedelta(days=2),
                    ),
                    Rental(
                        listing_id=listing.id,
                        renter_id=user_ids[0],
                        start_date=date.today() - timedelta(days=10),
                        end_date=date.today() - timedelta(days=8),
                        status="completed",
                        daily_price_snapshot=Decimal("20.00"),
                        estimated_total=Decimal("60.00"),
                        listing_snapshot={"title": "Título histórico"},
                        expires_at=datetime.now(UTC) + timedelta(days=2),
                    ),
                ]
            )
            session.commit()
            listing_id = listing.id

        with TestClient(app) as client:
            client.cookies.set("vv_session", create_session_token(user_ids[0], 0))
            yield client, user_ids[0], user_ids[1], user_ids[2]
    finally:
        app.dependency_overrides.pop(get_db, None)
        with Session(engine) as session:
            listing_ids = select(Listing.id).where(Listing.owner_id == user_ids[1])
            session.execute(delete(Rental).where(Rental.listing_id.in_(listing_ids)))
            session.execute(delete(ListingPhoto).where(ListingPhoto.listing_id.in_(listing_ids)))
            session.execute(delete(Listing).where(Listing.id == listing_id))
            session.execute(delete(User).where(User.id.in_(user_ids)))
            session.commit()
        engine.dispose()


def test_rentals_require_auth_and_validate_filters(
    rentals_context: tuple[TestClient, uuid.UUID, uuid.UUID, uuid.UUID],
) -> None:
    client, *_ = rentals_context
    assert (
        TestClient(app)
        .get("/api/me/rentals", params={"role": "renter", "scope": "active"})
        .status_code
        == 401
    )
    assert (
        client.get("/api/me/rentals", params={"role": "invalid", "scope": "active"}).status_code
        == 422
    )
    response = client.get(
        "/api/me/rentals", params={"role": "renter", "scope": "active", "cursor": "!"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


def test_renter_active_and_history_hide_phone_until_accepted(
    rentals_context: tuple[TestClient, uuid.UUID, uuid.UUID, uuid.UUID],
) -> None:
    client, *_ = rentals_context
    active = client.get("/api/me/rentals", params={"role": "renter", "scope": "active"})
    assert active.status_code == 200
    assert active.json()["total"] == 1
    item = active.json()["items"][0]
    assert item["title"] == "Título congelado"
    assert item["situation"] == "Aguardando"
    assert item["other_party_name"] == "Pessoa 1"
    assert item["other_party_phone"] is None

    history = client.get("/api/me/rentals", params={"role": "renter", "scope": "history"})
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["situation"] == "Concluído"


def test_owner_view_reveals_phone_only_for_accepted_and_paginates(
    rentals_context: tuple[TestClient, uuid.UUID, uuid.UUID, uuid.UUID],
) -> None:
    client, _renter_id, owner_id, *_ = rentals_context
    client.cookies.set("vv_session", create_session_token(owner_id, 0))
    active = client.get("/api/me/rentals", params={"role": "owner", "scope": "active", "limit": 1})
    assert active.status_code == 200
    assert active.json()["total"] == 2
    assert len(active.json()["items"]) == 1
    accepted = active.json()["items"][0]
    assert accepted["status"] == "accepted"
    assert accepted["other_party_phone"] == "51999990002"
    assert accepted["cover_photo"] == "capa.jpg"

    next_page = client.get(
        "/api/me/rentals",
        params={
            "role": "owner",
            "scope": "active",
            "limit": 1,
            "cursor": active.json()["next_cursor"],
        },
    )
    assert next_page.status_code == 200
    assert len(next_page.json()["items"]) == 1
    assert next_page.json()["items"][0]["status"] == "pending"
    assert next_page.json()["items"][0]["other_party_phone"] is None


def test_deleted_counterparty_is_anonymized(
    rentals_context: tuple[TestClient, uuid.UUID, uuid.UUID, uuid.UUID],
) -> None:
    client, _renter_id, owner_id, *_ = rentals_context
    engine = get_engine()
    with Session(engine) as session:
        owner = session.get(User, owner_id)
        assert owner is not None
        owner.deleted_at = datetime.now(UTC)
        session.commit()
    response = client.get("/api/me/rentals", params={"role": "renter", "scope": "active"})
    assert response.status_code == 200
    assert response.json()["items"][0]["other_party_name"] == "Usuário excluído"
    assert response.json()["items"][0]["other_party_phone"] is None

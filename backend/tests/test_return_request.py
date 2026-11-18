from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_db
from app.db import get_engine
from app.main import app
from app.migrations import upgrade_database
from app.models import Category, Listing, Rental, User
from app.security.session import create_session_token


@pytest.fixture
def return_context() -> Generator[dict[str, object], None, None]:
    upgrade_database()
    engine = get_engine()
    user_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    rental_ids: list[int] = []
    listing_ids: list[int] = []

    def override_db() -> Generator[Session, None, None]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with Session(engine) as session:
            for user_id in user_ids:
                suffix = f"{user_id.int % 10**11:011d}"
                session.add(
                    User(
                        id=user_id,
                        full_name="Pessoa de Teste",
                        username=f"r{suffix}",
                        email=f"return-{suffix}@example.invalid",
                        cpf=suffix,
                        phone="51999990000",
                        password_hash="test-only-hash",
                        cep="96200000",
                        street="Rua de Teste",
                        number="1",
                        neighborhood="Centro",
                        city="Rio Grande",
                        state="RS",
                    )
                )
            session.commit()

            category_id = session.scalar(select(Category.id).order_by(Category.id).limit(1))
            today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
            listing = Listing(
                owner_id=user_ids[1],
                category_id=category_id,
                title="Item de teste",
                description="Descrição de teste",
                daily_price=Decimal("25.00"),
                max_days=7,
                available_from=today,
                available_until=today + timedelta(days=30),
                pickup_cep="96200000",
                pickup_street="Rua de Teste",
                pickup_number="1",
                pickup_neighborhood="Centro",
                pickup_city="Rio Grande",
                pickup_state="RS",
            )
            session.add(listing)
            session.flush()
            listing_ids.append(listing.id)

            now = datetime.now(UTC)
            rental = Rental(
                listing_id=listing.id,
                renter_id=user_ids[0],
                start_date=today,
                end_date=today + timedelta(days=3),
                status="accepted",
                daily_price_snapshot=Decimal("25.00"),
                estimated_total=Decimal("100.00"),
                listing_snapshot={"title": "Item de teste"},
                created_at=now,
                expires_at=now + timedelta(hours=48),
            )
            session.add(rental)
            session.commit()
            rental_ids.append(rental.id)

        with (
            TestClient(app) as renter_client,
            TestClient(app) as owner_client,
            TestClient(app) as outsider_client,
        ):
            renter_client.cookies.set("vv_session", create_session_token(user_ids[0], 0))
            owner_client.cookies.set("vv_session", create_session_token(user_ids[1], 0))
            outsider_client.cookies.set("vv_session", create_session_token(user_ids[2], 0))
            yield {
                "renter": renter_client,
                "owner": owner_client,
                "outsider": outsider_client,
                "rental_id": rental_ids[0],
                "listing_id": listing_ids[0],
            }
    finally:
        app.dependency_overrides.pop(get_db, None)
        with Session(engine) as session:
            session.execute(delete(Rental).where(Rental.id.in_(rental_ids)))
            session.execute(delete(Listing).where(Listing.id.in_(listing_ids)))
            session.execute(delete(User).where(User.id.in_(user_ids)))
            session.commit()
        engine.dispose()


def test_renter_can_request_return_only_once_and_preserves_accepted_status(
    return_context: dict[str, object],
) -> None:
    client = return_context["renter"]
    rental_id = return_context["rental_id"]

    first = client.post(f"/api/rentals/{rental_id}/return-request")
    second = client.post(f"/api/rentals/{rental_id}/return-request")

    assert first.status_code == second.status_code == 204
    with Session(get_engine()) as session:
        rental = session.get(Rental, rental_id)
        assert rental is not None
        assert rental.return_requested_at is not None
        assert rental.status == "accepted"


@pytest.mark.parametrize("role", ["owner", "outsider"])
def test_only_renter_can_request_return(return_context: dict[str, object], role: str) -> None:
    client = return_context[role]
    rental_id = return_context["rental_id"]

    response = client.post(f"/api/rentals/{rental_id}/return-request")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize(
    ("status", "start_offset"),
    [("pending", 0), ("accepted", 1)],
)
def test_return_request_requires_accepted_rental_that_has_started(
    return_context: dict[str, object], status: str, start_offset: int
) -> None:
    rental_id = return_context["rental_id"]
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    with Session(get_engine()) as session:
        rental = session.get(Rental, rental_id)
        assert rental is not None
        rental.status = status
        rental.start_date = today + timedelta(days=start_offset)
        session.commit()

    response = return_context["renter"].post(f"/api/rentals/{rental_id}/return-request")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"


def test_return_request_returns_not_found_for_unknown_rental(
    return_context: dict[str, object],
) -> None:
    response = return_context["renter"].post("/api/rentals/999999999/return-request")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RENTAL_NOT_FOUND"

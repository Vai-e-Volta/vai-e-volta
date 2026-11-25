"""H020-1: dono marca o aluguel como devolvido (F-40, RN-64) · API-ADS-10.

O relógio é congelado em 10/06/2099, 12:00 em Brasília. Os dados são criados fora do freeze_time
(o banco usa now() real) e só a chamada à API é congelada.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from freezegun import freeze_time
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_db
from app.db import get_engine
from app.main import app
from app.migrations import upgrade_database
from app.models import Category, Listing, Rental, User
from app.security.session import create_session_token

FROZEN = "2099-06-10T15:00:00+00:00"
TODAY = date(2099, 6, 10)


def _d(day: int) -> date:
    return date(2099, 6, day)


@dataclass
class CompleteWorld:
    client: TestClient
    owner_id: uuid.UUID
    renter_id: uuid.UUID
    outsider_id: uuid.UUID
    listing_id: int

    def rental(self, start: date, end: date, status: str = "accepted") -> int:
        with Session(get_engine()) as session:
            rental = Rental(
                listing_id=self.listing_id,
                renter_id=self.renter_id,
                start_date=start,
                end_date=end,
                status=status,
                daily_price_snapshot=Decimal("25.00"),
                estimated_total=Decimal("125.00"),
                listing_snapshot={"title": "Cópia de teste"},
                expires_at=datetime.now(UTC) + timedelta(days=2),
            )
            session.add(rental)
            session.commit()
            return rental.id

    def complete(self, user_id: uuid.UUID, rental_id: int, at: str = FROZEN) -> Any:
        with freeze_time(at):
            # O token precisa nascer dentro do freeze, senão já estaria expirado em 2099.
            self.client.cookies.set("vv_session", create_session_token(user_id, 0))
            return self.client.post(f"/api/rentals/{rental_id}/complete")

    def listed_ids(self, user_id: uuid.UUID, role: str, scope: str) -> set[int]:
        with freeze_time(FROZEN):
            self.client.cookies.set("vv_session", create_session_token(user_id, 0))
            response = self.client.get("/api/me/rentals", params={"role": role, "scope": scope})
        assert response.status_code == 200, response.text
        return {item["id"] for item in response.json()["items"]}

    def state(self, rental_id: int) -> tuple[str, date | None]:
        with Session(get_engine()) as session:
            rental = session.get(Rental, rental_id)
            assert rental is not None
            return rental.status, rental.returned_on


def _make_user(user_id: uuid.UUID, prefix: str) -> User:
    suffix = f"{user_id.int % 10**11:011d}"
    return User(
        id=user_id,
        full_name="Pessoa de Teste",
        username=f"{prefix}_{suffix}",
        email=f"{prefix}-{suffix}@example.invalid",
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


@pytest.fixture
def world() -> Generator[CompleteWorld, None, None]:
    upgrade_database()
    engine = get_engine()
    owner_id, renter_id, outsider_id = (uuid.uuid4() for _ in range(3))

    def override_db() -> Generator[Session, None, None]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with Session(engine) as session:
            session.add_all(
                [
                    _make_user(owner_id, "dono"),
                    _make_user(renter_id, "loc"),
                    _make_user(outsider_id, "outro"),
                ]
            )
            session.flush()
            category_id = session.scalar(select(Category.id).order_by(Category.id).limit(1))
            listing = Listing(
                owner_id=owner_id,
                category_id=category_id,
                title="Item de teste",
                description="Item fictício para testes.",
                daily_price=Decimal("25.00"),
                max_days=14,
                available_from=_d(1),
                available_until=_d(30),
                pickup_cep="96200000",
                pickup_street="Rua da Retirada",
                pickup_number="123",
                pickup_neighborhood="Centro",
                pickup_city="Rio Grande",
                pickup_state="RS",
            )
            session.add(listing)
            session.commit()
            listing_id = listing.id

        with TestClient(app) as client:
            yield CompleteWorld(client, owner_id, renter_id, outsider_id, listing_id)
    finally:
        app.dependency_overrides.pop(get_db, None)
        with Session(engine) as session:
            session.execute(delete(Rental).where(Rental.listing_id == listing_id))
            session.execute(delete(Listing).where(Listing.id == listing_id))
            session.execute(delete(User).where(User.id.in_((owner_id, renter_id, outsider_id))))
            session.commit()
        engine.dispose()


def test_API_ADS_10_owner_marks_an_ongoing_rental_as_returned(world: CompleteWorld) -> None:
    ongoing = world.rental(_d(6), _d(12))
    future = world.rental(_d(20), _d(22))

    response = world.complete(world.owner_id, ongoing)

    assert response.status_code == 204
    assert response.content == b""
    assert world.state(ongoing) == ("completed", TODAY)
    # Outros aluguéis do mesmo anúncio não são tocados.
    assert world.state(future) == ("accepted", None)


@pytest.mark.parametrize(
    ("start", "end", "completed"),
    [
        pytest.param(_d(10), _d(14), True, id="comeca-hoje"),
        pytest.param(_d(8), _d(10), True, id="ultimo-dia"),
        pytest.param(_d(1), _d(5), True, id="atrasado-sem-multa-nem-bloqueio"),
        pytest.param(_d(11), _d(14), False, id="comeca-amanha"),
        pytest.param(_d(20), _d(22), False, id="comeca-so-depois"),
    ],
)
def test_API_ADS_10_requires_a_rental_that_has_already_started(
    world: CompleteWorld, start: date, end: date, completed: bool
) -> None:
    rental_id = world.rental(start, end)

    response = world.complete(world.owner_id, rental_id)

    if completed:
        assert response.status_code == 204
        assert world.state(rental_id) == ("completed", TODAY)
    else:
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_STATE"
        assert world.state(rental_id) == ("accepted", None)


@pytest.mark.parametrize(
    ("frozen_at", "completed"),
    [
        pytest.param("2099-06-11T02:59:59+00:00", False, id="23h59-em-brasilia"),
        pytest.param("2099-06-11T03:00:00+00:00", True, id="meia-noite-em-brasilia"),
    ],
)
def test_API_ADS_10_today_is_the_day_in_brasilia(
    world: CompleteWorld, frozen_at: str, completed: bool
) -> None:
    """RN-69: 02:59:59Z de 11/06 ainda é dia 10 em Brasília; 03:00:00Z já é dia 11."""
    rental_id = world.rental(_d(11), _d(14))

    response = world.complete(world.owner_id, rental_id, at=frozen_at)

    assert response.status_code == (204 if completed else 409)
    assert world.state(rental_id)[0] == ("completed" if completed else "accepted")


@pytest.mark.parametrize("role", ["renter_id", "outsider_id"])
def test_API_ADS_10_only_the_owner_may_mark_the_return(world: CompleteWorld, role: str) -> None:
    rental_id = world.rental(_d(6), _d(12))

    response = world.complete(getattr(world, role), rental_id)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert world.state(rental_id) == ("accepted", None)


def test_API_ADS_10_unknown_rental_invalid_id_and_anonymous_session(
    world: CompleteWorld,
) -> None:
    rental_id = world.rental(_d(6), _d(12))

    missing = world.complete(world.owner_id, 999999999)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RENTAL_NOT_FOUND"
    assert world.complete(world.owner_id, 0).status_code == 422
    with TestClient(app) as anonymous:
        assert anonymous.post(f"/api/rentals/{rental_id}/complete").status_code == 401
    assert world.state(rental_id) == ("accepted", None)


@pytest.mark.parametrize("status", ["pending", "rejected", "expired", "canceled", "completed"])
def test_API_ADS_10_requires_an_accepted_rental(world: CompleteWorld, status: str) -> None:
    rental_id = world.rental(_d(6), _d(12), status=status)

    response = world.complete(world.owner_id, rental_id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"
    assert world.state(rental_id) == (status, None)


def test_API_ADS_10_completing_twice_is_refused_and_keeps_the_first_return_date(
    world: CompleteWorld,
) -> None:
    rental_id = world.rental(_d(6), _d(12))
    assert world.complete(world.owner_id, rental_id).status_code == 204

    again = world.complete(world.owner_id, rental_id, at="2099-06-11T15:00:00+00:00")

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "INVALID_STATE"
    assert world.state(rental_id) == ("completed", TODAY)


def test_API_ADS_10_completed_rental_moves_to_the_history_of_both_parties(
    world: CompleteWorld,
) -> None:
    rental_id = world.rental(_d(6), _d(12))
    assert rental_id in world.listed_ids(world.owner_id, "owner", "active")
    assert rental_id in world.listed_ids(world.renter_id, "renter", "active")

    assert world.complete(world.owner_id, rental_id).status_code == 204

    assert rental_id in world.listed_ids(world.owner_id, "owner", "history")
    assert rental_id in world.listed_ids(world.renter_id, "renter", "history")
    assert rental_id not in world.listed_ids(world.owner_id, "owner", "active")
    assert rental_id not in world.listed_ids(world.renter_id, "renter", "active")

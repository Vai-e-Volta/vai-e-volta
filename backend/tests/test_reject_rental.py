"""H017-3: recusa manual da proposta pelo dono (F-39, RN-63) · API-ADS-09.

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
NOW = datetime(2099, 6, 10, 15, 0, tzinfo=UTC)


def _d(day: int) -> date:
    return date(2099, 6, day)


@dataclass
class RejectWorld:
    client: TestClient
    owner_id: uuid.UUID
    renter_id: uuid.UUID
    other_renter_id: uuid.UUID
    outsider_id: uuid.UUID
    listing_id: int

    def proposal(
        self,
        renter_id: uuid.UUID | None = None,
        start: date | None = None,
        end: date | None = None,
        status: str = "pending",
        expires_at: datetime | None = None,
    ) -> int:
        with Session(get_engine()) as session:
            rental = Rental(
                listing_id=self.listing_id,
                renter_id=renter_id or self.renter_id,
                start_date=start or _d(10),
                end_date=end or _d(14),
                status=status,
                daily_price_snapshot=Decimal("25.00"),
                estimated_total=Decimal("125.00"),
                listing_snapshot={"title": "Cópia de teste"},
                expires_at=expires_at or NOW + timedelta(hours=48),
            )
            session.add(rental)
            session.commit()
            return rental.id

    def reject(self, user_id: uuid.UUID, rental_id: int, at: str = FROZEN) -> Any:
        with freeze_time(at):
            # O token precisa nascer dentro do freeze, senão já estaria expirado em 2099.
            self.client.cookies.set("vv_session", create_session_token(user_id, 0))
            return self.client.post(f"/api/rentals/{rental_id}/reject")

    def listed_ids(self, user_id: uuid.UUID, role: str, scope: str) -> set[int]:
        with freeze_time(FROZEN):
            self.client.cookies.set("vv_session", create_session_token(user_id, 0))
            response = self.client.get("/api/me/rentals", params={"role": role, "scope": scope})
        assert response.status_code == 200, response.text
        return {item["id"] for item in response.json()["items"]}

    def state(self, rental_id: int) -> tuple[str, datetime | None]:
        with Session(get_engine()) as session:
            rental = session.get(Rental, rental_id)
            assert rental is not None
            return rental.status, rental.responded_at


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
def world() -> Generator[RejectWorld, None, None]:
    upgrade_database()
    engine = get_engine()
    owner_id, renter_id, other_renter_id, outsider_id = (uuid.uuid4() for _ in range(4))

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
                    _make_user(other_renter_id, "loc2"),
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
            yield RejectWorld(client, owner_id, renter_id, other_renter_id, outsider_id, listing_id)
    finally:
        app.dependency_overrides.pop(get_db, None)
        with Session(engine) as session:
            session.execute(delete(Rental).where(Rental.listing_id == listing_id))
            session.execute(delete(Listing).where(Listing.id == listing_id))
            owners = (owner_id, renter_id, other_renter_id, outsider_id)
            session.execute(delete(User).where(User.id.in_(owners)))
            session.commit()
        engine.dispose()


def test_API_ADS_09_owner_rejects_a_pending_proposal_without_a_reason(world: RejectWorld) -> None:
    rental_id = world.proposal()

    response = world.reject(world.owner_id, rental_id)

    assert response.status_code == 204
    assert response.content == b""
    assert world.state(rental_id) == ("rejected", NOW)


@pytest.mark.parametrize("role", ["renter_id", "other_renter_id", "outsider_id"])
def test_API_ADS_09_only_the_owner_may_reject(world: RejectWorld, role: str) -> None:
    rental_id = world.proposal()

    response = world.reject(getattr(world, role), rental_id)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert world.state(rental_id) == ("pending", None)


def test_API_ADS_09_reject_unknown_rental_invalid_id_and_anonymous_session(
    world: RejectWorld,
) -> None:
    rental_id = world.proposal()

    missing = world.reject(world.owner_id, 999999999)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RENTAL_NOT_FOUND"
    assert world.reject(world.owner_id, 0).status_code == 422
    with TestClient(app) as anonymous:
        assert anonymous.post(f"/api/rentals/{rental_id}/reject").status_code == 401
    assert world.state(rental_id) == ("pending", None)


@pytest.mark.parametrize("status", ["accepted", "rejected", "expired", "canceled", "completed"])
def test_API_ADS_09_reject_requires_a_pending_proposal(world: RejectWorld, status: str) -> None:
    rental_id = world.proposal(status=status)

    response = world.reject(world.owner_id, rental_id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"
    assert world.state(rental_id) == (status, None)


def test_API_ADS_09_rejecting_twice_is_refused_and_keeps_the_first_answer_time(
    world: RejectWorld,
) -> None:
    rental_id = world.proposal()
    assert world.reject(world.owner_id, rental_id).status_code == 204

    again = world.reject(world.owner_id, rental_id, at="2099-06-10T18:00:00+00:00")

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "INVALID_STATE"
    assert world.state(rental_id) == ("rejected", NOW)


@pytest.mark.parametrize(
    ("start", "expires_at", "refused"),
    [
        pytest.param(_d(10), NOW + timedelta(hours=1), True, id="comeca-hoje-e-no-prazo"),
        pytest.param(_d(9), NOW + timedelta(hours=1), False, id="comecou-ontem"),
        pytest.param(_d(12), NOW - timedelta(hours=1), False, id="prazo-vencido"),
        pytest.param(_d(12), NOW, False, id="vence-exatamente-agora"),
    ],
)
def test_API_ADS_09_overdue_proposal_is_expired_instead_of_rejected(
    world: RejectWorld, start: date, expires_at: datetime, refused: bool
) -> None:
    rental_id = world.proposal(start=start, end=start + timedelta(days=2), expires_at=expires_at)

    response = world.reject(world.owner_id, rental_id)

    if refused:
        assert response.status_code == 204
        assert world.state(rental_id) == ("rejected", NOW)
    else:
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "PROPOSAL_EXPIRED"
        # O estado expired é gravado mesmo respondendo 409 (RN-47, RN-48).
        assert world.state(rental_id) == ("expired", None)


def test_API_ADS_09_reject_touches_only_the_chosen_proposal(world: RejectWorld) -> None:
    target = world.proposal(start=_d(10), end=_d(14))
    overlapping = world.proposal(world.other_renter_id, _d(12), _d(16))
    accepted = world.proposal(world.outsider_id, _d(20), _d(22), status="accepted")

    assert world.reject(world.owner_id, target).status_code == 204

    assert world.state(target) == ("rejected", NOW)
    # Diferente do aceite (RN-46), a recusa não recusa nenhuma outra proposta.
    assert world.state(overlapping) == ("pending", None)
    assert world.state(accepted) == ("accepted", None)


def test_API_ADS_09_rejected_proposal_moves_to_the_history_of_both_parties(
    world: RejectWorld,
) -> None:
    rental_id = world.proposal()
    assert rental_id in world.listed_ids(world.owner_id, "owner", "active")
    assert rental_id in world.listed_ids(world.renter_id, "renter", "active")

    assert world.reject(world.owner_id, rental_id).status_code == 204

    assert rental_id in world.listed_ids(world.owner_id, "owner", "history")
    assert rental_id in world.listed_ids(world.renter_id, "renter", "history")
    assert rental_id not in world.listed_ids(world.owner_id, "owner", "active")
    assert rental_id not in world.listed_ids(world.renter_id, "renter", "active")

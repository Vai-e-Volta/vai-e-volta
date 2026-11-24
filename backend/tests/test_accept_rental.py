"""H017-1: aceite da proposta pelo dono (F-39; RN-46, RN-48, RN-63).

API-RNT-09 (propostas sobrepostas), API-RNT-10 (vencimento), API-RNT-11 (início passado) e
API-ADS-09 (só o dono). Tudo roda com o relógio congelado em 10/06/2099, 12:00 em Brasília; os dados
são criados fora do freeze_time (o banco usa now() real) e só a chamada à API é congelada.
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
class AcceptWorld:
    client: TestClient
    owner_id: uuid.UUID
    renter_id: uuid.UUID
    other_renter_id: uuid.UUID
    outsider_id: uuid.UUID
    listing_id: int
    other_listing_id: int

    def proposal(
        self,
        renter_id: uuid.UUID | None = None,
        start: date | None = None,
        end: date | None = None,
        status: str = "pending",
        expires_at: datetime | None = None,
        listing_id: int | None = None,
    ) -> int:
        with Session(get_engine()) as session:
            rental = Rental(
                listing_id=listing_id or self.listing_id,
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

    def accept(self, user_id: uuid.UUID, rental_id: int, at: str = FROZEN) -> Any:
        with freeze_time(at):
            # O token precisa nascer dentro do freeze, senão já estaria expirado em 2099.
            self.client.cookies.set("vv_session", create_session_token(user_id, 0))
            return self.client.post(f"/api/rentals/{rental_id}/accept")

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
def world() -> Generator[AcceptWorld, None, None]:
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
            listings = [
                Listing(
                    owner_id=owner_id,
                    category_id=category_id,
                    title=f"Item {number}",
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
                for number in (1, 2)
            ]
            session.add_all(listings)
            session.commit()
            listing_ids = [listing.id for listing in listings]

        with TestClient(app) as client:
            yield AcceptWorld(
                client=client,
                owner_id=owner_id,
                renter_id=renter_id,
                other_renter_id=other_renter_id,
                outsider_id=outsider_id,
                listing_id=listing_ids[0],
                other_listing_id=listing_ids[1],
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        with Session(engine) as session:
            owned = select(Listing.id).where(Listing.owner_id == owner_id)
            session.execute(delete(Rental).where(Rental.listing_id.in_(owned)))
            session.execute(delete(Listing).where(Listing.owner_id == owner_id))
            session.execute(
                delete(User).where(User.id.in_((owner_id, renter_id, other_renter_id, outsider_id)))
            )
            session.commit()
        engine.dispose()


# ---------------------------------------------------------------------------
# RN-63 · API-ADS-09: só o dono aceita
# ---------------------------------------------------------------------------


def test_API_ADS_09_owner_accepts_a_pending_proposal(world: AcceptWorld) -> None:
    rental_id = world.proposal()

    response = world.accept(world.owner_id, rental_id)

    assert response.status_code == 204
    assert response.content == b""
    assert world.state(rental_id) == ("accepted", NOW)


@pytest.mark.parametrize("role", ["renter_id", "other_renter_id", "outsider_id"])
def test_API_ADS_09_only_the_owner_may_accept(world: AcceptWorld, role: str) -> None:
    rental_id = world.proposal()

    response = world.accept(getattr(world, role), rental_id)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert world.state(rental_id) == ("pending", None)


def test_API_ADS_09_unknown_rental_invalid_id_and_anonymous_session(world: AcceptWorld) -> None:
    rental_id = world.proposal()

    missing = world.accept(world.owner_id, 999999999)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "RENTAL_NOT_FOUND"
    assert world.accept(world.owner_id, 0).status_code == 422
    with TestClient(app) as anonymous:
        assert anonymous.post(f"/api/rentals/{rental_id}/accept").status_code == 401
    assert world.state(rental_id) == ("pending", None)


# ---------------------------------------------------------------------------
# RN-47 · API-RNT-10: estado e vencimento
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["accepted", "rejected", "expired", "canceled", "completed"])
def test_API_RNT_10_accept_requires_a_pending_proposal(world: AcceptWorld, status: str) -> None:
    rental_id = world.proposal(status=status)

    response = world.accept(world.owner_id, rental_id)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"
    assert world.state(rental_id) == (status, None)


def test_API_RNT_10_overdue_proposal_is_saved_as_expired_when_accept_is_refused(
    world: AcceptWorld,
) -> None:
    overdue = world.proposal(expires_at=NOW - timedelta(hours=1))
    neighbour = world.proposal(renter_id=world.other_renter_id, start=_d(12), end=_d(16))

    response = world.accept(world.owner_id, overdue)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PROPOSAL_EXPIRED"
    # O estado foi gravado mesmo com a resposta 409, e nada mais foi tocado.
    assert world.state(overdue) == ("expired", None)
    assert world.state(neighbour) == ("pending", None)
    # Repetir o aceite agora cai no estado inválido.
    repeated = world.accept(world.owner_id, overdue)
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "INVALID_STATE"


@pytest.mark.parametrize(
    ("expires_at", "accepted"),
    [
        pytest.param(NOW, False, id="vence-exatamente-agora"),
        pytest.param(NOW + timedelta(seconds=1), True, id="vence-um-segundo-depois"),
    ],
)
def test_API_RNT_10_deadline_boundary(
    world: AcceptWorld, expires_at: datetime, accepted: bool
) -> None:
    rental_id = world.proposal(expires_at=expires_at)

    response = world.accept(world.owner_id, rental_id)

    assert response.status_code == (204 if accepted else 409)
    assert world.state(rental_id)[0] == ("accepted" if accepted else "expired")


# ---------------------------------------------------------------------------
# RN-48 · API-RNT-11: início maior ou igual a hoje
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "end", "accepted"),
    [
        pytest.param(_d(10), _d(12), True, id="comeca-hoje"),
        pytest.param(_d(11), _d(12), True, id="comeca-amanha"),
        pytest.param(_d(9), _d(12), False, id="comecou-ontem"),
    ],
)
def test_API_RNT_11_start_date_must_not_be_in_the_past(
    world: AcceptWorld, start: date, end: date, accepted: bool
) -> None:
    rental_id = world.proposal(start=start, end=end)

    response = world.accept(world.owner_id, rental_id)

    if accepted:
        assert response.status_code == 204
        assert world.state(rental_id)[0] == "accepted"
    else:
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "PROPOSAL_EXPIRED"
        # O estado expired é gravado mesmo respondendo 409 (RN-48).
        assert world.state(rental_id) == ("expired", None)


@pytest.mark.parametrize(
    ("frozen_at", "accepted"),
    [
        pytest.param("2099-06-11T02:59:59+00:00", True, id="23h59-em-brasilia"),
        pytest.param("2099-06-11T03:00:00+00:00", False, id="meia-noite-em-brasilia"),
    ],
)
def test_API_RNT_11_today_is_the_day_in_brasilia(
    world: AcceptWorld, frozen_at: str, accepted: bool
) -> None:
    """RN-69: 02:59:59Z de 11/06 ainda é dia 10 em Brasília; 03:00:00Z já é dia 11."""
    rental_id = world.proposal(start=_d(10), end=_d(12))

    response = world.accept(world.owner_id, rental_id, at=frozen_at)

    assert response.status_code == (204 if accepted else 409)
    assert world.state(rental_id)[0] == ("accepted" if accepted else "expired")


# ---------------------------------------------------------------------------
# RN-46 · API-RNT-09: propostas sobrepostas
# ---------------------------------------------------------------------------


def test_API_RNT_09_accept_settles_overlapping_pending_proposals_in_the_same_transaction(
    world: AcceptWorld,
) -> None:
    # "Hoje" é 10/06; o aluguel aceito vai de 12 a 16, e as vizinhas começam hoje ou depois,
    # para continuarem válidas (início no passado já seria vencimento, RN-48).
    target = world.proposal(start=_d(12), end=_d(16))
    overlap_inside = world.proposal(world.other_renter_id, _d(14), _d(18))
    contained = world.proposal(world.outsider_id, _d(13), _d(15))
    overlap_last_day = world.proposal(world.outsider_id, _d(16), _d(17))
    overlap_first_day = world.proposal(world.other_renter_id, _d(10), _d(12))
    day_after = world.proposal(world.other_renter_id, _d(17), _d(18))
    day_before = world.proposal(world.outsider_id, _d(10), _d(11))
    other_listing = world.proposal(
        world.other_renter_id, _d(12), _d(16), listing_id=world.other_listing_id
    )
    canceled = world.proposal(world.other_renter_id, _d(12), _d(16), status="canceled")
    overdue = world.proposal(world.outsider_id, _d(13), _d(14), expires_at=NOW - timedelta(hours=1))

    response = world.accept(world.owner_id, target)

    assert response.status_code == 204
    assert world.state(target) == ("accepted", NOW)
    # Sobrepostas e ainda no prazo: recusadas automaticamente (extremos inclusivos).
    for rental_id in (overlap_inside, contained, overlap_last_day, overlap_first_day):
        assert world.state(rental_id) == ("rejected", NOW)
    # Sobreposta, mas já vencida (RN-47): expirada, e não recusada.
    assert world.state(overdue) == ("expired", None)
    # Fora do período, de outro anúncio ou que não eram pendentes: intactas.
    assert world.state(day_after) == ("pending", None)
    assert world.state(day_before) == ("pending", None)
    assert world.state(other_listing) == ("pending", None)
    assert world.state(canceled) == ("canceled", None)
    # Uma proposta recusada pela sobreposição não pode ser aceita depois.
    late = world.accept(world.owner_id, overlap_inside)
    assert late.status_code == 409
    assert late.json()["error"]["code"] == "INVALID_STATE"


def test_API_RNT_09_accepting_without_overlaps_changes_only_the_accepted_proposal(
    world: AcceptWorld,
) -> None:
    target = world.proposal(start=_d(10), end=_d(14))
    separate = world.proposal(world.other_renter_id, _d(20), _d(22))

    assert world.accept(world.owner_id, target).status_code == 204

    assert world.state(target)[0] == "accepted"
    assert world.state(separate) == ("pending", None)

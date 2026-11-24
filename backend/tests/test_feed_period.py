"""H012-3: filtro por período desejado (F-22, RN-29) · API-FEED-06."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

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


def _d(day: int) -> date:
    return date(2099, 6, day)


# Período desejado dos testes: 10/06 a 14/06 (de um ano distante), inclusivos nas duas pontas.
PERIOD = {"needed_from": "2099-06-10", "needed_until": "2099-06-14"}
WIDE_WINDOW = (_d(1), _d(30))


class PeriodWorld:
    """Cliente logado e anúncios de um usuário descartável, isolados por um token no título."""

    def __init__(self, client: TestClient, owner_id: uuid.UUID, token: str) -> None:
        self.client = client
        self.owner_id = owner_id
        self.token = token
        self.listing_ids: list[int] = []

    def add(self, window: tuple[date, date] = WIDE_WINDOW, price: str = "25.00") -> int:
        with Session(get_engine()) as session:
            category_id = session.scalar(select(Category.id).order_by(Category.id).limit(1))
            listing = Listing(
                owner_id=self.owner_id,
                category_id=category_id,
                title=f"Item {self.token} {len(self.listing_ids)}",
                description="Item fictício para testes.",
                daily_price=Decimal(price),
                max_days=1,
                available_from=window[0],
                available_until=window[1],
                pickup_cep="00000000",
                pickup_street="Rua Ficticia",
                pickup_number="0",
                pickup_neighborhood="Bairro Ficticio",
                pickup_city="Cidade Ficticia",
                pickup_state="RS",
            )
            session.add(listing)
            session.commit()
            self.listing_ids.append(listing.id)
            return listing.id

    def rent(self, listing_id: int, start: date, end: date, status: str = "accepted") -> None:
        # O banco não impede o dono de ser o locatário (RN-40 é regra da API); isso evita
        # criar um segundo usuário só para os testes de leitura do feed.
        with Session(get_engine()) as session:
            session.add(
                Rental(
                    listing_id=listing_id,
                    renter_id=self.owner_id,
                    start_date=start,
                    end_date=end,
                    status=status,
                    daily_price_snapshot=Decimal("25.00"),
                    estimated_total=Decimal("125.00"),
                    listing_snapshot={"title": "Cópia de teste"},
                    expires_at=datetime.now(UTC) + timedelta(days=2),
                )
            )
            session.commit()

    def get(self, **params: Any) -> Any:
        return self.client.get("/api/listings", params={"q": self.token, **params})

    def page(self, **params: Any) -> dict[str, Any]:
        response = self.get(**params)
        assert response.status_code == 200, response.text
        return response.json()

    def ids(self, **params: Any) -> set[int]:
        return {item["id"] for item in self.page(limit=50, **params)["items"]}


@pytest.fixture
def world() -> Generator[PeriodWorld, None, None]:
    upgrade_database()
    engine = get_engine()
    owner_id = uuid.uuid4()
    token = uuid.uuid4().hex[:8]

    def override_db() -> Generator[Session, None, None]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with Session(engine) as session:
            suffix = f"{owner_id.int % 10**11:011d}"
            session.add(
                User(
                    id=owner_id,
                    full_name="Pessoa Ficticia",
                    username=f"period_{suffix}",
                    email=f"period-{suffix}@example.invalid",
                    cpf=suffix,
                    phone="00000000000",
                    password_hash="test-only-hash",
                    cep="00000000",
                    street="Rua Ficticia",
                    number="0",
                    neighborhood="Bairro Ficticio",
                    city="Cidade Ficticia",
                    state="RS",
                )
            )
            session.commit()

        with TestClient(app) as client:
            client.cookies.set("vv_session", create_session_token(owner_id, 0))
            yield PeriodWorld(client, owner_id, token)
    finally:
        app.dependency_overrides.pop(get_db, None)
        with Session(engine) as session:
            owned = select(Listing.id).where(Listing.owner_id == owner_id)
            session.execute(delete(Rental).where(Rental.listing_id.in_(owned)))
            session.execute(delete(Listing).where(Listing.owner_id == owner_id))
            session.execute(delete(User).where(User.id == owner_id))
            session.commit()
        engine.dispose()


# (nome, janela do anúncio, a janela cobre o período 10 a 14?)
WINDOW_CASES = [
    ("janela igual ao período", (_d(10), _d(14)), True),
    ("janela maior nos dois lados", (_d(9), _d(15)), True),
    ("janela ampla", (_d(1), _d(30)), True),
    ("começa um dia depois", (_d(11), _d(30)), False),
    ("termina um dia antes", (_d(1), _d(13)), False),
    ("janela depois do período", (_d(15), _d(30)), False),
    ("janela antes do período", (_d(1), _d(9)), False),
]

# (nome, aluguel accepted existente, o período 10 a 14 continua livre?)
RENTAL_CASES = [
    ("sem aluguel", None, True),
    ("encosta no último dia", (_d(14), _d(16)), False),
    ("começa no dia seguinte", (_d(15), _d(16)), True),
    ("encosta no primeiro dia", (_d(8), _d(10)), False),
    ("termina na véspera", (_d(7), _d(9)), True),
    ("dentro do período", (_d(11), _d(12)), False),
    ("cobre o período", (_d(5), _d(20)), False),
    ("1 dia no primeiro dia", (_d(10), _d(10)), False),
    ("1 dia no último dia", (_d(14), _d(14)), False),
    ("1 dia na véspera", (_d(9), _d(9)), True),
    ("1 dia no dia seguinte", (_d(15), _d(15)), True),
]


def test_API_FEED_06_window_must_cover_the_whole_period(world: PeriodWorld) -> None:
    created = [(name, world.add(window=window), covers) for name, window, covers in WINDOW_CASES]

    found = world.ids(**PERIOD)
    for name, listing_id, covers in created:
        assert (listing_id in found) is covers, name
    # Sem o filtro, todos continuam no feed (RN-24).
    assert world.ids() == {listing_id for _, listing_id, _ in created}


def test_API_FEED_06_accepted_rentals_overlap_with_inclusive_ends(world: PeriodWorld) -> None:
    created = []
    for name, rental, free in RENTAL_CASES:
        listing_id = world.add()
        if rental is not None:
            world.rent(listing_id, *rental)
        created.append((name, listing_id, free))

    found = world.ids(**PERIOD)
    for name, listing_id, free in created:
        assert (listing_id in found) is free, name


@pytest.mark.parametrize("status", ["pending", "rejected", "expired", "canceled"])
def test_API_FEED_06_only_accepted_rentals_block_the_period(
    world: PeriodWorld, status: str
) -> None:
    listing_id = world.add()
    world.rent(listing_id, _d(11), _d(12), status=status)

    assert world.ids(**PERIOD) == {listing_id}


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"needed_from": "2099-06-10"}, id="so-needed_from"),
        pytest.param({"needed_until": "2099-06-14"}, id="so-needed_until"),
        pytest.param({}, id="nenhum"),
    ],
)
def test_API_FEED_06_period_filter_is_ignored_unless_both_limits_are_given(
    world: PeriodWorld, params: dict[str, str]
) -> None:
    covering = world.add()
    not_covering = world.add(window=(_d(15), _d(30)))
    rented = world.add()
    world.rent(rented, _d(11), _d(12))

    page = world.page(limit=50, **params)

    assert {item["id"] for item in page["items"]} == {covering, not_covering, rented}
    assert page["total"] == 3


def test_API_FEED_06_single_day_period_is_valid(world: PeriodWorld) -> None:
    one_day = world.add(window=(_d(10), _d(10)))
    rented = world.add()
    world.rent(rented, _d(10), _d(10))
    other_day = world.add(window=(_d(11), _d(11)))

    ids = world.ids(needed_from="2099-06-10", needed_until="2099-06-10")

    assert one_day in ids
    assert rented not in ids
    assert other_day not in ids


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"needed_from": "2099-06-14", "needed_until": "2099-06-10"}, id="invertido"),
        pytest.param({"needed_from": "abc", "needed_until": "2099-06-14"}, id="data-invalida"),
        pytest.param({"needed_from": "2099-02-31"}, id="data-inexistente-sozinha"),
    ],
)
def test_API_FEED_06_rejects_invalid_period(world: PeriodWorld, params: dict[str, str]) -> None:
    response = world.get(**params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "needed_from" in response.json()["error"]["fields"]


def test_API_FEED_06_combines_with_other_filters_and_keeps_total_and_pagination(
    world: PeriodWorld,
) -> None:
    cheap = world.add(price="10.00")
    pricey = world.add(price="30.00")
    cheap_too = world.add(price="12.00")
    world.add(window=(_d(20), _d(30)), price="11.00")  # janela não cobre o período
    blocked = world.add(price="9.00")
    world.rent(blocked, _d(12), _d(13))

    assert world.ids(price_max="20.00", **PERIOD) == {cheap, cheap_too}

    seen: list[int] = []
    params: dict[str, Any] = {"limit": 1, **PERIOD}
    while True:
        body = world.page(**params)
        assert body["total"] == 3
        seen += [item["id"] for item in body["items"]]
        if body["next_cursor"] is None:
            break
        params["cursor"] = body["next_cursor"]
    assert sorted(seen) == sorted([cheap, pricey, cheap_too])
    assert len(set(seen)) == len(seen)

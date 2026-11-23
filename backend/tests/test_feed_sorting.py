"""H012-1: ordenação do feed (F-20) e cursor por chave (RN-30) · API-FEED-07."""

from __future__ import annotations

import base64
import json
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
from app.models import Category, Listing, User
from app.security.session import create_session_token
from app.services.rental_situation import today_br

SORTS = ("newest", "oldest", "price_asc", "price_desc")

# (valor por dia, minutos atrás). Há empates de preço (25,00 ×4 e 40,50 ×2) e de data
# (4 min ×3, 3 min ×2 e 1 min ×2), para o desempate por id atravessar as fronteiras de página.
SEED = [
    ("10.00", 5),
    ("25.00", 4),
    ("25.00", 4),
    ("25.00", 4),
    ("25.00", 3),
    ("40.50", 3),
    ("40.50", 2),
    ("5.00", 1),
    ("99.99", 1),
]


@dataclass(frozen=True)
class Row:
    id: int
    price: Decimal
    created_at: datetime


class SortWorld:
    """Cliente logado mais os anúncios de um usuário descartável, isolados por um token."""

    def __init__(self, client: TestClient, owner_id: uuid.UUID, token: str) -> None:
        self.client = client
        self.owner_id = owner_id
        self.token = token
        self.rows: list[Row] = []

    def add(self, price: str, created_at: datetime) -> int:
        today = today_br()
        with Session(get_engine()) as session:
            category_id = session.scalar(select(Category.id).order_by(Category.id).limit(1))
            listing = Listing(
                owner_id=self.owner_id,
                category_id=category_id,
                title=f"Item {self.token} {len(self.rows)}",
                description="Item fictício para testes.",
                daily_price=Decimal(price),
                max_days=3,
                available_from=today,
                available_until=today + timedelta(days=30),
                pickup_cep="00000000",
                pickup_street="Rua Ficticia",
                pickup_number="0",
                pickup_neighborhood="Bairro Ficticio",
                pickup_city="Cidade Ficticia",
                pickup_state="RS",
                created_at=created_at,
            )
            session.add(listing)
            session.commit()
            self.rows.append(Row(listing.id, Decimal(price), created_at))
            return listing.id

    def get(self, **params: Any) -> Any:
        return self.client.get("/api/listings", params={"q": self.token, **params})

    def page(self, **params: Any) -> dict[str, Any]:
        response = self.get(**params)
        assert response.status_code == 200, response.text
        return response.json()

    def walk(self, sort: str, limit: int, **extra: Any) -> list[dict[str, Any]]:
        """Segue o next_cursor até o fim e devolve todas as páginas."""
        pages: list[dict[str, Any]] = []
        params: dict[str, Any] = {"sort": sort, "limit": limit, **extra}
        while True:
            body = self.page(**params)
            pages.append(body)
            if body["next_cursor"] is None:
                return pages
            assert len(pages) <= len(self.rows), "a paginação não terminou"
            params["cursor"] = body["next_cursor"]


@pytest.fixture
def world() -> Generator[SortWorld, None, None]:
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
                    username=f"sort_{suffix}",
                    email=f"sort-{suffix}@example.invalid",
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
            sort_world = SortWorld(client, owner_id, token)
            base = datetime.now(UTC).replace(microsecond=0)
            for price, minutes_ago in SEED:
                sort_world.add(price, base - timedelta(minutes=minutes_ago))
            yield sort_world
    finally:
        app.dependency_overrides.pop(get_db, None)
        with Session(engine) as session:
            session.execute(delete(Listing).where(Listing.owner_id == owner_id))
            session.execute(delete(User).where(User.id == owner_id))
            session.commit()
        engine.dispose()


def _expected_order(rows: list[Row], sort: str) -> list[int]:
    if sort in ("newest", "oldest"):
        ordered = sorted(rows, key=lambda row: (row.created_at, row.id))
    else:
        ordered = sorted(rows, key=lambda row: (row.price, row.id))
    if sort in ("newest", "price_desc"):
        ordered.reverse()
    return [row.id for row in ordered]


def _ids(pages: list[dict[str, Any]]) -> list[int]:
    return [item["id"] for page in pages for item in page["items"]]


def _cursor(payload: object) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


@pytest.mark.parametrize("limit", [2, 3])
@pytest.mark.parametrize("sort", SORTS)
def test_API_FEED_07_pagination_follows_the_chosen_order_without_repeats_or_gaps(
    world: SortWorld, sort: str, limit: int
) -> None:
    pages = world.walk(sort, limit)

    ids = _ids(pages)
    assert ids == _expected_order(world.rows, sort)
    assert len(set(ids)) == len(ids) == len(SEED)
    assert all(len(page["items"]) == limit for page in pages[:-1])
    assert all(page["total"] == len(SEED) for page in pages)
    assert pages[-1]["next_cursor"] is None


def test_API_FEED_07_default_order_is_newest(world: SortWorld) -> None:
    default = _ids([world.page(limit=50)])
    explicit = _ids([world.page(limit=50, sort="newest")])

    assert default == explicit == _expected_order(world.rows, "newest")


def test_API_FEED_07_rejects_unknown_sort(world: SortWorld) -> None:
    response = world.get(sort="preco")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "sort" in response.json()["error"]["fields"]


def test_API_FEED_07_cursor_only_works_for_the_sort_that_issued_it(world: SortWorld) -> None:
    cursors = {sort: world.page(sort=sort, limit=2)["next_cursor"] for sort in SORTS}

    for issued_for, cursor in cursors.items():
        for requested in SORTS:
            response = world.get(sort=requested, limit=2, cursor=cursor)
            if requested == issued_for:
                assert response.status_code == 200, response.text
            else:
                assert response.status_code == 400, (issued_for, requested)
                assert response.json()["error"]["code"] == "INVALID_CURSOR"


def _price(value: object, listing_id: object = 1) -> dict[str, object]:
    return {"sort": "price_asc", "daily_price": value, "id": listing_id}


def _date(value: object, listing_id: object = 1) -> dict[str, object]:
    return {"sort": "newest", "created_at": value, "id": listing_id}


MALFORMED_CURSORS = [
    pytest.param("price_asc", _price("NaN"), id="nan"),
    pytest.param("price_asc", _price("Infinity"), id="infinito"),
    pytest.param("price_asc", _price("1E+999"), id="expoente"),
    pytest.param("price_asc", _price("-1"), id="negativo"),
    pytest.param("price_asc", _price("5000.01"), id="acima-do-max"),
    pytest.param("price_asc", _price("10.001"), id="3-casas"),
    pytest.param("price_asc", _price("abc"), id="texto"),
    pytest.param("price_asc", _price(12.5), id="numero-json"),
    pytest.param("price_asc", {"sort": "price_asc", "id": 1}, id="sem-chave"),
    pytest.param("price_asc", _price("10.00", 0), id="id-zero"),
    pytest.param("price_asc", _price("10.00", True), id="id-bool"),
    pytest.param("price_asc", _price("10.00", "1"), id="id-texto"),
    pytest.param("price_asc", _price("10.00", 2**63), id="id-enorme"),
    pytest.param("price_asc", {"sort": "price_asc", "daily_price": "10.00"}, id="sem-id"),
    pytest.param("newest", _date("2030-01-01T00:00:00"), id="sem-fuso"),
    pytest.param("newest", _date("ontem"), id="data-invalida"),
    pytest.param("newest", {"created_at": "2030-01-01T00:00:00+00:00", "id": 1}, id="sem-ordem"),
    pytest.param("newest", [1, 2], id="lista"),
    pytest.param("newest", "texto", id="string-json"),
]


@pytest.mark.parametrize(("sort", "payload"), MALFORMED_CURSORS)
def test_API_FEED_07_rejects_malformed_cursors(
    world: SortWorld, sort: str, payload: object
) -> None:
    response = world.get(sort=sort, cursor=_cursor(payload))

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


def test_API_FEED_07_accepts_a_well_formed_handmade_cursor(world: SortWorld) -> None:
    cursor = _cursor({"sort": "price_asc", "daily_price": "10.00", "id": 1})
    body = world.page(sort="price_asc", limit=50, cursor=cursor)

    # Tudo que vem depois de (10,00; id 1) na ordem crescente de preço.
    assert body["items"]
    assert all(Decimal(item["daily_price"]) >= Decimal("10.00") for item in body["items"])


def test_API_FEED_07_price_order_ignores_listings_inserted_during_scroll(
    world: SortWorld,
) -> None:
    before = list(world.rows)
    first = world.page(sort="price_asc", limit=3)
    seen = _ids([first])

    cheap = world.add("1.00", datetime.now(UTC))
    rest_pages: list[dict[str, Any]] = []
    cursor = first["next_cursor"]
    while cursor:
        body = world.page(sort="price_asc", limit=3, cursor=cursor)
        rest_pages.append(body)
        cursor = body["next_cursor"]
    rest = _ids(rest_pages)

    assert cheap not in rest
    assert not set(seen) & set(rest)
    assert seen + rest == _expected_order(before, "price_asc")


def test_API_FEED_07_sort_combines_with_filters_and_keeps_the_total(world: SortWorld) -> None:
    pages = world.walk("price_desc", 2, price_max="25.00")

    eligible = [row for row in world.rows if row.price <= Decimal("25.00")]
    assert _ids(pages) == _expected_order(eligible, "price_desc")
    assert all(page["total"] == len(eligible) for page in pages)

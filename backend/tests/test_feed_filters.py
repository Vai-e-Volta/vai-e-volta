"""H011-1: tag and price filters in the feed (RN-26) and GET /api/tags (F-17)."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_db
from app.db import get_engine
from app.main import app
from app.migrations import upgrade_database
from app.models import Category, Listing, Tag, User, listing_tags
from app.security.session import create_session_token
from app.services.rental_situation import today_br


class FeedWorld:
    """A logged-in client plus helpers that create listings owned by a throwaway user."""

    def __init__(self, client: TestClient, owner_id: uuid.UUID, token: str) -> None:
        self.client = client
        self.owner_id = owner_id
        self.token = token  # unique text in titles and tags isolates this test's rows
        self.tag_ids: list[int] = []

    def tag(self, name: str) -> str:
        return f"{name}{self.token}"

    def listing(self, price: str, tags: list[str], *, status: str = "active") -> int:
        today = today_br()
        with Session(get_engine()) as session:
            category_id = session.scalar(select(Category.id).order_by(Category.id).limit(1))
            listing = Listing(
                owner_id=self.owner_id,
                category_id=category_id,
                title=f"Item {self.token} {price}",
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
                status=status,
            )
            session.add(listing)
            session.flush()
            for name in tags:
                normalized = session.scalar(
                    select(func.lower(func.public.immutable_unaccent(name)))
                )
                tag_id = session.scalar(select(Tag.id).where(Tag.normalized_name == normalized))
                if tag_id is None:
                    tag = Tag(name=name, normalized_name=normalized)
                    session.add(tag)
                    session.flush()
                    tag_id = tag.id
                    self.tag_ids.append(tag_id)
                session.execute(insert(listing_tags).values(listing_id=listing.id, tag_id=tag_id))
            session.commit()
            return listing.id

    def feed(self, **params: object) -> list[str]:
        response = self.client.get("/api/listings", params={"q": self.token, **params})
        assert response.status_code == 200, response.text
        return sorted(item["daily_price"] for item in response.json()["items"])


@pytest.fixture
def world() -> Generator[FeedWorld, None, None]:
    upgrade_database()
    engine = get_engine()
    owner_id = uuid.uuid4()
    token = uuid.uuid4().hex[:8]

    def override_db() -> Generator[Session, None, None]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with Session(engine) as session:
        suffix = f"{owner_id.int % 10**11:011d}"
        session.add(
            User(
                id=owner_id,
                full_name="Pessoa Ficticia",
                username=f"tags_{suffix}",
                email=f"tags-{suffix}@example.invalid",
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
    state = None
    try:
        with TestClient(app) as client:
            client.cookies.set("vv_session", create_session_token(owner_id, 0))
            state = FeedWorld(client, owner_id, token)
            yield state
    finally:
        app.dependency_overrides.pop(get_db, None)
        with Session(engine) as session:
            ids = select(Listing.id).where(Listing.owner_id == owner_id)
            session.execute(delete(listing_tags).where(listing_tags.c.listing_id.in_(ids)))
            if state is not None and state.tag_ids:
                session.execute(delete(Tag).where(Tag.id.in_(state.tag_ids)))
            session.execute(delete(Listing).where(Listing.owner_id == owner_id))
            session.execute(delete(User).where(User.id == owner_id))
            session.commit()
        engine.dispose()


def test_API_FEED_03_tags_and_price_combine_with_and_or_inside_type(world: FeedWorld) -> None:
    drill, paint, garden = world.tag("furadeira"), world.tag("pintura"), world.tag("jardim")
    world.listing("10.00", [drill])
    world.listing("20.00", [paint])
    world.listing("30.00", [drill, paint])
    world.listing("40.00", [garden])
    world.listing("50.00", [])

    assert world.feed() == ["10.00", "20.00", "30.00", "40.00", "50.00"]
    # One tag; several tags of the same type combine with OR.
    assert world.feed(**{"tags[]": [drill]}) == ["10.00", "30.00"]
    assert world.feed(**{"tags[]": [drill, garden]}) == ["10.00", "30.00", "40.00"]
    # Tags match case- and accent-insensitively, ignoring surrounding spaces.
    assert world.feed(**{"tags[]": [f"  {paint.upper()} "]}) == ["20.00", "30.00"]
    assert world.feed(**{"tags[]": [world.tag("desconhecida")]}) == []
    # Price limits are inclusive; different filter types combine with AND.
    assert world.feed(price_min="20.00") == ["20.00", "30.00", "40.00", "50.00"]
    assert world.feed(price_max="30") == ["10.00", "20.00", "30.00"]
    assert world.feed(price_min="20", price_max="40") == ["20.00", "30.00", "40.00"]
    assert world.feed(price_min="30", price_max="30") == ["30.00"]
    assert world.feed(**{"tags[]": [drill, paint]}, price_min="15", price_max="35") == [
        "20.00",
        "30.00",
    ]
    assert world.feed(**{"tags[]": [garden]}, price_max="35") == []


def test_API_FEED_03_tag_filter_ignores_listings_outside_the_feed(world: FeedWorld) -> None:
    drill = world.tag("furadeira")
    world.listing("10.00", [drill])
    world.listing("20.00", [drill], status="paused")
    assert world.feed(**{"tags[]": [drill]}) == ["10.00"]


@pytest.mark.parametrize(
    "params",
    [
        {"price_min": "abc"},
        {"price_min": "-1"},
        {"price_max": "5000.01"},
        {"price_min": "10.123"},
        {"price_min": "NaN"},
        {"price_min": "30", "price_max": "20"},
        {"tags[]": [""]},
        {"tags[]": ["   "]},
        {"tags[]": ["x" * 31]},
        {"tags[]": [f"t{index}" for index in range(21)]},
    ],
)
def test_API_FEED_03_invalid_filters_return_422(world: FeedWorld, params: dict) -> None:
    response = world.client.get("/api/listings", params=params)
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "VALIDATION_ERROR"
    assert set(body["fields"]) <= {"price_min", "price_max", "tags", "tags[]"}


def test_F17_tags_endpoint_lists_most_used_and_searches(world: FeedWorld) -> None:
    common, rare, hidden = world.tag("Elétrica"), world.tag("Solda"), world.tag("Oculta")
    world.listing("10.00", [common, rare])
    world.listing("20.00", [common])
    world.listing("30.00", [common])
    world.listing("40.00", [hidden], status="paused")

    anonymous = TestClient(app).get("/api/tags")
    assert anonymous.status_code == 401

    # Search by part of the name, ignoring case and accents; most used first.
    found = world.client.get("/api/tags", params={"q": world.token})
    assert found.status_code == 200
    assert found.json() == {"tags": [{"name": common, "count": 3}, {"name": rare, "count": 1}]}
    accent = world.client.get("/api/tags", params={"q": f"ELETRICA{world.token}"})
    assert accent.json()["tags"] == [{"name": common, "count": 3}]
    # LIKE metacharacters are literal text.
    assert world.client.get("/api/tags", params={"q": "%_%"}).json()["tags"] == []

    # Without q: the most used tags of visible listings; tags only on paused listings never appear.
    popular = world.client.get("/api/tags", params={"limit": 30}).json()["tags"]
    names = [tag["name"] for tag in popular]
    assert hidden not in names
    assert [tag["count"] for tag in popular] == sorted(
        (tag["count"] for tag in popular), reverse=True
    )

    assert world.client.get("/api/tags", params={"limit": 0}).status_code == 422
    assert world.client.get("/api/tags", params={"q": "x" * 31}).status_code == 422

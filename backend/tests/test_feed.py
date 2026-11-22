from __future__ import annotations

import uuid
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_db
from app.db import get_engine
from app.main import app
from app.migrations import upgrade_database
from app.models import Category, Favorite, Listing, ListingPhoto, Rental, User
from app.security.session import create_session_token


@pytest.fixture
def feed_context() -> Generator[tuple[TestClient, uuid.UUID], None, None]:
    upgrade_database()
    engine = get_engine()
    user_id = uuid.uuid4()

    def override_db() -> Generator[Session, None, None]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with Session(engine) as session:
            suffix = f"{user_id.int % 10**11:011d}"
            user = User(
                id=user_id,
                full_name="Nome Privado de Teste",
                username=f"feed_{suffix}",
                email=f"feed-{suffix}@example.invalid",
                cpf=suffix,
                phone="51999990000",
                password_hash="test-only-hash",
                cep="96200000",
                street="Rua Privada",
                number="123",
                neighborhood="Centro",
                city="Rio Grande",
                state="RS",
            )
            session.add(user)
            session.commit()

        with TestClient(app) as client:
            client.cookies.set("vv_session", create_session_token(user_id, 0))
            yield client, user_id
    finally:
        app.dependency_overrides.pop(get_db, None)
        with Session(engine) as session:
            listing_ids = select(Listing.id).where(Listing.owner_id == user_id)
            session.execute(delete(Favorite).where(Favorite.listing_id.in_(listing_ids)))
            session.execute(delete(ListingPhoto).where(ListingPhoto.listing_id.in_(listing_ids)))
            session.execute(delete(Rental).where(Rental.listing_id.in_(listing_ids)))
            session.execute(delete(Listing).where(Listing.owner_id == user_id))
            session.execute(delete(User).where(User.id == user_id))
            session.commit()
        engine.dispose()


def _insert_listing(
    user_id: uuid.UUID,
    title: str,
    *,
    created_at: datetime | None = None,
    photo: str | None = None,
) -> int:
    engine = get_engine()
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    with Session(engine) as session:
        category_id = session.scalar(select(Category.id).order_by(Category.id).limit(1))
        listing = Listing(
            owner_id=user_id,
            category_id=category_id,
            title=title,
            description="Descrição privada de teste",
            daily_price=Decimal("25.00"),
            max_days=7,
            available_from=today,
            available_until=today + timedelta(days=30),
            pickup_cep="96200000",
            pickup_street="Rua Privada",
            pickup_number="123",
            pickup_neighborhood="Centro",
            pickup_city="Rio Grande",
            pickup_state="RS",
        )
        if created_at is not None:
            listing.created_at = created_at
        session.add(listing)
        session.flush()
        if photo is not None:
            session.add(ListingPhoto(listing_id=listing.id, position=1, filename=photo))
        session.commit()
        return listing.id


def test_feed_requires_login_and_rejects_invalid_cursor(
    feed_context: tuple[TestClient, uuid.UUID],
) -> None:
    client, _user_id = feed_context
    anonymous = TestClient(app).get("/api/listings")
    assert anonymous.status_code == 401

    invalid_cursor = client.get("/api/listings", params={"cursor": "not-a-cursor"})
    assert invalid_cursor.status_code == 400
    assert invalid_cursor.json()["error"]["code"] == "INVALID_CURSOR"


def test_create_listing_with_photo_and_categories(
    feed_context: tuple[TestClient, uuid.UUID], monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    client, user_id = feed_context
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    categories = client.get("/api/categories")
    assert categories.status_code == 200
    category_id = categories.json()[0]["id"]
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    data = {
        "title": "Câmera",
        "description": "Item para aluguel",
        "daily_price": "25.00",
        "max_days": "3",
        "available_from": str(today),
        "available_until": str(today + timedelta(days=10)),
        "category_id": str(category_id),
        "tags[]": "Fotografia",
    }
    image = BytesIO()
    Image.new("RGB", (2, 2)).save(image, format="PNG")
    response = client.post(
        "/api/listings", data=data, files={"photos[]": ("photo.png", image.getvalue(), "image/png")}
    )
    assert response.status_code == 201, response.text
    with Session(get_engine()) as session:
        listing = session.get(Listing, response.json()["id"])
        assert listing is not None
        assert listing.owner_id == user_id
        assert listing.pickup_street == "Rua Privada"
        assert session.scalar(select(ListingPhoto.id).where(ListingPhoto.listing_id == listing.id))
    bad = client.post(
        "/api/listings",
        data={**data, "max_days": "50"},
        files={"photos[]": ("x.png", image.getvalue(), "image/png")},
    )
    assert bad.status_code == 422
    for invalid_data in (
        {**data, "daily_price": "0"},
        {**data, "category_id": "999999"},
        {**data, "pickup_state": "ZZ"},
        {**data, "unexpected": "value"},
    ):
        invalid = client.post(
            "/api/listings",
            data=invalid_data,
            files={"photos[]": ("x.png", image.getvalue(), "image/png")},
        )
        assert invalid.status_code == 422
    duplicate = client.post(
        "/api/listings",
        data={**data, "tags[]": ["Foto", "foto"]},
        files={"photos[]": ("x.png", image.getvalue(), "image/png")},
    )
    assert duplicate.status_code == 422
    invalid_image = client.post(
        "/api/listings", data=data, files={"photos[]": ("x.png", b"bad", "image/png")}
    )
    assert invalid_image.status_code == 415
    with Session(get_engine()) as session:
        listings = session.scalars(select(Listing).where(Listing.owner_id == user_id)).all()
        assert len(listings) == 1


def test_feed_returns_public_fields_owner_flag_and_cover_photo(
    feed_context: tuple[TestClient, uuid.UUID],
) -> None:
    client, user_id = feed_context
    listing_id = _insert_listing(user_id, "Furadeira", photo="cover.jpg")

    response = client.get("/api/listings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert item["id"] == listing_id
    assert item["cover_photo"] == "cover.jpg"
    assert item["is_owner"] is True
    assert item["situation"] == "available"
    assert item["daily_price"] == "25.00"
    assert not {"email", "cpf", "phone", "full_name", "street", "number"} & item.keys()


def test_feed_keyset_cursor_ignores_newer_inserted_listings(
    feed_context: tuple[TestClient, uuid.UUID],
) -> None:
    client, user_id = feed_context
    now = datetime.now(UTC)
    oldest = _insert_listing(user_id, "Mais antigo", created_at=now - timedelta(days=3))
    middle = _insert_listing(user_id, "Intermediário", created_at=now - timedelta(days=2))
    newest = _insert_listing(user_id, "Mais recente", created_at=now - timedelta(days=1))

    first_page = client.get("/api/listings", params={"limit": 2}).json()
    assert [item["id"] for item in first_page["items"]] == [newest, middle]
    assert first_page["next_cursor"]

    inserted_after_scroll = _insert_listing(
        user_id, "Entrou durante a rolagem", created_at=now + timedelta(seconds=1)
    )
    second_page = client.get(
        "/api/listings", params={"limit": 2, "cursor": first_page["next_cursor"]}
    ).json()

    second_page_ids = [item["id"] for item in second_page["items"]]
    assert second_page_ids == [oldest]
    assert inserted_after_scroll not in second_page_ids
    assert not set(second_page_ids) & {newest, middle}


@pytest.mark.parametrize(
    ("title", "query"),
    [
        ("Furadeira elétrica", "FURADEIRA"),
        ("Tecido 100% algodão", "%"),
        ("C_ferramenta", "_"),
        (r"C:\\ferramentas", "\\"),
    ],
)
def test_feed_search_is_case_accent_insensitive_and_escapes_like_metacharacters(
    feed_context: tuple[TestClient, uuid.UUID], title: str, query: str
) -> None:
    client, user_id = feed_context
    matching_id = _insert_listing(user_id, title)
    _insert_listing(user_id, "Anúncio sem correspondência")

    response = client.get("/api/listings", params={"q": query})

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [matching_id]


def test_favorites_are_idempotent_and_filter_the_feed(
    feed_context: tuple[TestClient, uuid.UUID],
) -> None:
    client, user_id = feed_context
    favorite_id = _insert_listing(user_id, "Item favoritado")
    other_id = _insert_listing(user_id, "Outro item")

    assert client.put(f"/api/listings/{favorite_id}/favorite").status_code == 204
    assert client.put(f"/api/listings/{favorite_id}/favorite").status_code == 204
    all_items = {item["id"]: item for item in client.get("/api/listings").json()["items"]}
    assert all_items[favorite_id]["is_favorite"] is True
    assert all_items[other_id]["is_favorite"] is False

    favorites = client.get("/api/listings", params={"favorites": "true"}).json()
    assert [item["id"] for item in favorites["items"]] == [favorite_id]

    assert client.delete(f"/api/listings/{favorite_id}/favorite").status_code == 204
    assert client.delete(f"/api/listings/{favorite_id}/favorite").status_code == 204
    all_items = {item["id"]: item for item in client.get("/api/listings").json()["items"]}
    assert all_items[favorite_id]["is_favorite"] is False
    assert client.get("/api/listings", params={"favorites": "true"}).json()["items"] == []

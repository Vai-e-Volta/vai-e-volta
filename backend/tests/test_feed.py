from __future__ import annotations

import re
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
from app.models import Category, Favorite, Listing, ListingPhoto, Rental, User, listing_tags
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
    duplicate_accents = client.post(
        "/api/listings",
        data={**data, "tags[]": ["Ferramenta", "ferraménta"]},
        files={"photos[]": ("x.png", image.getvalue(), "image/png")},
    )
    assert duplicate_accents.status_code == 422
    too_many_tags = client.post(
        "/api/listings",
        data={**data, "tags[]": [f"tag{i}" for i in range(6)]},
        files={"photos[]": ("x.png", image.getvalue(), "image/png")},
    )
    assert too_many_tags.status_code == 422
    for invalid_data in (
        {**data, "available_from": str(today + timedelta(days=11))},
        {
            **data,
            "available_until": str(today - timedelta(days=1)),
            "available_from": str(today - timedelta(days=10)),
        },
    ):
        invalid = client.post(
            "/api/listings",
            data=invalid_data,
            files={"photos[]": ("x.png", image.getvalue(), "image/png")},
        )
        assert invalid.status_code == 422
    too_many_photos = client.post(
        "/api/listings",
        data=data,
        files=[("photos[]", (f"{i}.png", image.getvalue(), "image/png")) for i in range(6)],
    )
    assert too_many_photos.status_code == 422
    assert TestClient(app).get("/api/categories").status_code == 401
    invalid_image = client.post(
        "/api/listings", data=data, files={"photos[]": ("x.png", b"bad", "image/png")}
    )
    assert invalid_image.status_code == 415
    with Session(get_engine()) as session:
        listings = session.scalars(select(Listing).where(Listing.owner_id == user_id)).all()
        assert len(listings) == 1


def test_my_listings_are_private_and_paginated(
    feed_context: tuple[TestClient, uuid.UUID],
) -> None:
    client, user_id = feed_context
    assert TestClient(app).get("/api/me/listings").status_code == 401
    ids = [_insert_listing(user_id, f"Anúncio {i}") for i in range(3)]
    with Session(get_engine()) as session:
        paused = session.get(Listing, ids[0])
        assert paused is not None
        paused.status = "paused"
        session.commit()
    first = client.get("/api/me/listings", params={"limit": 1})
    assert first.status_code == 200
    assert first.json()["total"] == 2
    assert first.json()["items"][0]["pickup_street"] == "Rua Privada"
    second = client.get(
        "/api/me/listings", params={"limit": 1, "cursor": first.json()["next_cursor"]}
    )
    assert second.status_code == 200
    assert first.json()["items"][0]["id"] != second.json()["items"][0]["id"]
    history = client.get("/api/me/listings", params={"scope": "history"})
    assert [item["id"] for item in history.json()["items"]] == [ids[0]]
    assert client.get("/api/me/listings", params={"cursor": "!"}).status_code == 400


def test_category_filter_combines_categories_and_search(
    feed_context: tuple[TestClient, uuid.UUID],
) -> None:
    client, user_id = feed_context
    listing_ids = [
        _insert_listing(user_id, title) for title in ("Martelo", "Martelo leve", "Serra")
    ]
    with Session(get_engine()) as session:
        categories = list(session.scalars(select(Category.id).order_by(Category.id).limit(3)))
        for listing_id, category_id in zip(listing_ids, categories, strict=True):
            listing = session.get(Listing, listing_id)
            assert listing is not None
            listing.category_id = category_id
        session.commit()
    response = client.get(
        "/api/listings",
        params=[("categories[]", categories[0]), ("categories[]", categories[1]), ("q", "martelo")],
    )
    assert response.status_code == 200
    assert {item["id"] for item in response.json()["items"]} == set(listing_ids[:2])
    assert response.json()["total"] == 2
    invalid = client.get("/api/listings", params={"categories[]": 999999})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["fields"]["categories"]


def test_price_ranges_use_active_prices_and_recalculate(
    feed_context: tuple[TestClient, uuid.UUID],
) -> None:
    client, user_id = feed_context
    assert TestClient(app).get("/api/listings/price-ranges").status_code == 401
    assert client.get("/api/listings/price-ranges").json() == {"ranges": []}
    ids = [_insert_listing(user_id, f"Item {i}") for i in range(4)]
    with Session(get_engine()) as session:
        for listing_id, price in zip(ids, (10, 20, 30, 40), strict=True):
            listing = session.get(Listing, listing_id)
            assert listing is not None
            listing.daily_price = Decimal(price)
        session.commit()
    response = client.get("/api/listings/price-ranges")
    assert response.json() == {
        "ranges": [
            {"label": "Mais baratos", "min": "10.00", "max": "20.00"},
            {"label": "Intermediários", "min": "30.00", "max": "30.00"},
            {"label": "Mais caros", "min": "40.00", "max": "40.00"},
        ]
    }
    with Session(get_engine()) as session:
        listing = session.get(Listing, ids[-1])
        assert listing is not None
        listing.status = "paused"
        session.commit()
    assert client.get("/api/listings/price-ranges").json()["ranges"][-1]["max"] == "30.00"


def test_edit_listing_preserves_snapshot_and_reorders_photos(
    feed_context: tuple[TestClient, uuid.UUID], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    client, user_id = feed_context
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    listing_id = _insert_listing(user_id, "Título antigo")
    names = [f"{uuid.uuid4()}.png" for _ in range(2)]
    for name in names:
        (tmp_path / name).write_bytes(b"original")
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    with Session(get_engine()) as session:
        listing = session.get(Listing, listing_id)
        assert listing is not None
        session.add_all(
            ListingPhoto(listing_id=listing_id, position=i + 1, filename=name)
            for i, name in enumerate(names)
        )
        renter_id = uuid.uuid4()
        suffix = f"{renter_id.int % 10**11:011d}"
        session.add(
            User(
                id=renter_id,
                full_name="Locatário",
                username=f"r{suffix}",
                email=f"r{suffix}@example.invalid",
                cpf=suffix,
                phone="51999990000",
                password_hash="test-only-hash",
                cep="96200000",
                street="Rua",
                number="1",
                neighborhood="Centro",
                city="Rio Grande",
                state="RS",
            )
        )
        session.flush()
        session.add(
            Rental(
                listing_id=listing_id,
                renter_id=renter_id,
                start_date=today + timedelta(days=1),
                end_date=today + timedelta(days=5),
                status="accepted",
                daily_price_snapshot=Decimal("25.00"),
                estimated_total=Decimal("125.00"),
                listing_snapshot={"title": "Título antigo", "photos": names},
                expires_at=datetime.now(UTC) + timedelta(days=2),
            )
        )
        session.commit()
        photos = session.scalars(
            select(ListingPhoto)
            .where(ListingPhoto.listing_id == listing_id)
            .order_by(ListingPhoto.position)
        ).all()
        keep_id = photos[1].id
    try:
        image = BytesIO()
        Image.new("RGB", (2, 2)).save(image, format="PNG")
        other_client = TestClient(app)
        other_client.cookies.set("vv_session", create_session_token(renter_id, 0))
        denied = other_client.patch(
            f"/api/listings/{listing_id}", files=[("title", (None, "Não permitido"))]
        )
        assert denied.status_code == 403
        assert (
            other_client.patch(
                f"/api/listings/{listing_id}", json={"title": "Não permitido"}
            ).status_code
            == 403
        )
        invalid_photo = client.patch(
            f"/api/listings/{listing_id}",
            files=[("title", (None, "Não gravar")), ("photos[]", ("x.png", b"bad", "image/png"))],
        )
        assert invalid_photo.status_code == 415
        with Session(get_engine()) as session:
            unchanged = session.get(Listing, listing_id)
            assert unchanged is not None and unchanged.title == "Título antigo"
        response = client.patch(
            f"/api/listings/{listing_id}",
            files=[
                ("title", (None, "Título novo")),
                ("daily_price", (None, "50.00")),
                ("keep_photo_ids[]", (None, str(keep_id))),
                ("photos[]", ("nova.png", image.getvalue(), "image/png")),
            ],
        )
        assert response.status_code == 200, response.text
        with Session(get_engine()) as session:
            listing = session.get(Listing, listing_id)
            assert listing is not None and listing.title == "Título novo"
            assert listing.daily_price == Decimal("50.00")
            photos = session.scalars(
                select(ListingPhoto)
                .where(ListingPhoto.listing_id == listing_id)
                .order_by(ListingPhoto.position)
            ).all()
            assert [photo.position for photo in photos] == [1, 2]
            assert photos[0].id == keep_id and photos[0].filename == names[1]
            assert (tmp_path / photos[1].filename).exists()
            rental = session.scalar(select(Rental).where(Rental.listing_id == listing_id))
            assert rental is not None and rental.daily_price_snapshot == Decimal("25.00")
            assert rental.listing_snapshot == {"title": "Título antigo", "photos": names}
        assert (tmp_path / names[0]).exists()
        tagged = client.patch(
            f"/api/listings/{listing_id}", files=[("tags[]", (None, "Ferramenta"))]
        )
        assert tagged.status_code == 200
        cleared = client.patch(f"/api/listings/{listing_id}", files=[("tags[]", (None, ""))])
        assert cleared.status_code == 200
        with Session(get_engine()) as session:
            assert not session.execute(
                select(listing_tags).where(listing_tags.c.listing_id == listing_id)
            ).all()
        conflict = client.patch(
            f"/api/listings/{listing_id}",
            files=[
                ("available_until", (None, str(today + timedelta(days=2)))),
                ("max_days", (None, "2")),
            ],
        )
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "LISTING_HAS_ACTIVE_RENTAL"
        bad = client.patch(
            f"/api/listings/{listing_id}", files=[("keep_photo_ids[]", (None, "999999"))]
        )
        assert bad.status_code == 422
    finally:
        with Session(get_engine()) as session:
            session.execute(delete(Rental).where(Rental.listing_id == listing_id))
            session.execute(delete(User).where(User.id == renter_id))
            session.commit()


def test_edit_text_does_not_require_upload_directory(
    feed_context: tuple[TestClient, uuid.UUID], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    client, user_id = feed_context
    missing_dir = tmp_path / "not-created"
    monkeypatch.setenv("UPLOAD_DIR", str(missing_dir))
    listing_id = _insert_listing(user_id, "Título anterior", photo="photo.png")
    response = client.patch(
        f"/api/listings/{listing_id}", files=[("title", (None, "Título alterado"))]
    )
    assert response.status_code == 200
    assert not missing_dir.exists()
    with Session(get_engine()) as session:
        listing = session.get(Listing, listing_id)
        assert listing is not None and listing.title == "Título alterado"


def test_edit_photo_move_failure_rolls_back_database_and_files(
    feed_context: tuple[TestClient, uuid.UUID], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from app.services import listing_edit

    client, user_id = feed_context
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    listing_id = _insert_listing(user_id, "Título anterior", photo="old.png")
    old_file = tmp_path / "old.png"
    old_file.write_bytes(b"existing")
    image = BytesIO()
    Image.new("RGB", (2, 2)).save(image, format="PNG")
    original_replace = listing_edit.os.replace
    calls = 0

    def fail_second_move(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated storage error")
        return original_replace(source, destination)

    with monkeypatch.context() as patch:
        patch.setattr(listing_edit.os, "replace", fail_second_move)
        with pytest.raises(OSError, match="simulated storage error"):
            client.patch(
                f"/api/listings/{listing_id}",
                files=[
                    ("title", (None, "Não gravar")),
                    ("photos[]", ("a.png", image.getvalue(), "image/png")),
                    ("photos[]", ("b.png", image.getvalue(), "image/png")),
                ],
            )
    with Session(get_engine()) as session:
        listing = session.get(Listing, listing_id)
        assert listing is not None and listing.title == "Título anterior"
        names = list(
            session.scalars(
                select(ListingPhoto.filename).where(ListingPhoto.listing_id == listing_id)
            )
        )
        assert names == ["old.png"]
    assert list(tmp_path.iterdir()) == [old_file]


def test_new_proposal_uses_edited_price_and_existing_rental_keeps_snapshot(
    feed_context: tuple[TestClient, uuid.UUID],
) -> None:
    has_proposal_endpoint = any(
        re.fullmatch(r"/api/listings/\{[^}]+\}/rentals", getattr(route, "path", ""))
        and "POST" in (getattr(route, "methods", None) or set())
        for route in app.routes
    )
    if not has_proposal_endpoint:
        pytest.skip("A API de proposta da issue #88 ainda não está disponível nesta base")

    client, user_id = feed_context
    listing_id = _insert_listing(user_id, "Título anterior", photo="old.png")
    renter_id = uuid.uuid4()
    suffix = f"{renter_id.int % 10**11:011d}"
    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    try:
        with Session(get_engine()) as session:
            session.add(
                User(
                    id=renter_id,
                    full_name="Locatário",
                    username=f"r{suffix}",
                    email=f"r{suffix}@example.invalid",
                    cpf=suffix,
                    phone="51999990000",
                    password_hash="test-only-hash",
                    cep="96200000",
                    street="Rua",
                    number="1",
                    neighborhood="Centro",
                    city="Rio Grande",
                    state="RS",
                )
            )
            session.flush()
            session.add(
                Rental(
                    listing_id=listing_id,
                    renter_id=renter_id,
                    start_date=today + timedelta(days=1),
                    end_date=today + timedelta(days=2),
                    status="accepted",
                    daily_price_snapshot=Decimal("25.00"),
                    estimated_total=Decimal("50.00"),
                    listing_snapshot={"title": "Título anterior"},
                    expires_at=datetime.now(UTC) + timedelta(days=2),
                )
            )
            session.commit()
        edited = client.patch(
            f"/api/listings/{listing_id}",
            files=[("title", (None, "Título alterado")), ("daily_price", (None, "50.00"))],
        )
        assert edited.status_code == 200
        renter = TestClient(app)
        renter.cookies.set("vv_session", create_session_token(renter_id, 0))
        response = renter.post(
            f"/api/listings/{listing_id}/rentals",
            json={
                "start_date": str(today + timedelta(days=10)),
                "end_date": str(today + timedelta(days=11)),
            },
        )
        assert response.status_code == 201, response.text
        with Session(get_engine()) as session:
            existing = session.scalar(
                select(Rental).where(Rental.listing_id == listing_id, Rental.status == "accepted")
            )
            proposed = session.scalar(
                select(Rental).where(Rental.listing_id == listing_id, Rental.status == "pending")
            )
            assert existing is not None and existing.daily_price_snapshot == Decimal("25.00")
            assert existing.listing_snapshot["title"] == "Título anterior"
            assert proposed is not None and proposed.daily_price_snapshot == Decimal("50.00")
            assert proposed.estimated_total == Decimal("100.00")
            assert proposed.listing_snapshot["title"] == "Título alterado"
    finally:
        with Session(get_engine()) as session:
            session.execute(delete(Rental).where(Rental.listing_id == listing_id))
            session.execute(delete(User).where(User.id == renter_id))
            session.commit()


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

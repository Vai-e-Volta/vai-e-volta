"""H015-1: detalhe do anúncio e períodos reservados (F-28, F-29, F-31; RN-33 a RN-35, RN-44)."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from dataclasses import dataclass
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
from app.models import Category, Listing, ListingPhoto, Rental, Tag, User, listing_tags
from app.security.session import create_session_token

CEP = "96200000"


@dataclass(frozen=True)
class DetailContext:
    client: TestClient
    owner_id: uuid.UUID
    renter_id: uuid.UUID
    other_id: uuid.UUID
    owner_username: str
    listing_id: int
    category_name: str
    tag_names: list[str]
    photos: list[dict[str, Any]]

    @property
    def path(self) -> str:
        return f"/api/listings/{self.listing_id}"

    def get_as(self, user_id: uuid.UUID, path: str) -> Any:
        self.client.cookies.set("vv_session", create_session_token(user_id, 0))
        return self.client.get(path)


def _make_user(user_id: uuid.UUID, prefix: str, phone: str) -> User:
    suffix = f"{user_id.int % 10**11:011d}"
    return User(
        id=user_id,
        full_name="Nome Privado de Teste",
        username=f"{prefix}_{suffix}",
        email=f"{prefix}-{suffix}@example.invalid",
        cpf=suffix,
        phone=phone,
        password_hash="test-only-hash",
        cep=CEP,
        street="Rua Privada",
        number="999",
        neighborhood="Bairro Privado",
        city="Rio Grande",
        state="RS",
    )


@pytest.fixture
def detail_context() -> Generator[DetailContext, None, None]:
    upgrade_database()
    engine = get_engine()
    owner_id, renter_id, other_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    token = uuid.uuid4().hex[:8]
    tag_keys = (f"tag{token}a", f"tag{token}b")

    def override_db() -> Generator[Session, None, None]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with Session(engine) as session:
            owner = _make_user(owner_id, "dono", "51999990001")
            session.add_all([owner, _make_user(renter_id, "loc", "51999990002")])
            session.add(_make_user(other_id, "outro", "51999990003"))
            session.flush()
            category = session.scalars(select(Category).order_by(Category.id).limit(1)).one()
            tags = [Tag(name=key, normalized_name=key) for key in reversed(tag_keys)]
            session.add_all(tags)
            listing = Listing(
                owner_id=owner_id,
                category_id=category.id,
                title="Furadeira de impacto",
                description="Descrição pública do item.",
                daily_price=Decimal("25.00"),
                max_days=7,
                available_from=date(2030, 6, 1),
                available_until=date(2030, 6, 30),
                pickup_cep=CEP,
                pickup_street="Rua da Retirada",
                pickup_number="123",
                pickup_complement="Fundos",
                pickup_neighborhood="Centro",
                pickup_city="Rio Grande",
                pickup_state="RS",
            )
            session.add(listing)
            session.flush()
            photos = [
                ListingPhoto(listing_id=listing.id, position=1, filename=f"{token}-1.jpg"),
                ListingPhoto(listing_id=listing.id, position=2, filename=f"{token}-2.jpg"),
            ]
            session.add_all(photos)
            session.flush()
            session.execute(
                listing_tags.insert(),
                [{"listing_id": listing.id, "tag_id": tag.id} for tag in tags],
            )
            session.commit()
            context_values = {
                "owner_username": owner.username,
                "listing_id": listing.id,
                "category_name": category.name,
                "photos": [{"id": photo.id, "filename": photo.filename} for photo in photos],
            }

        with TestClient(app) as client:
            yield DetailContext(
                client=client,
                owner_id=owner_id,
                renter_id=renter_id,
                other_id=other_id,
                tag_names=sorted(tag_keys),
                **context_values,
            )
    finally:
        app.dependency_overrides.pop(get_db, None)
        with Session(engine) as session:
            listing_ids = select(Listing.id).where(Listing.owner_id == owner_id)
            session.execute(delete(Rental).where(Rental.listing_id.in_(listing_ids)))
            session.execute(delete(listing_tags).where(listing_tags.c.listing_id.in_(listing_ids)))
            session.execute(delete(ListingPhoto).where(ListingPhoto.listing_id.in_(listing_ids)))
            session.execute(delete(Listing).where(Listing.owner_id == owner_id))
            session.execute(delete(Tag).where(Tag.normalized_name.in_(tag_keys)))
            session.execute(delete(User).where(User.id.in_((owner_id, renter_id, other_id))))
            session.commit()
        engine.dispose()


def _add_rental(
    listing_id: int,
    renter_id: uuid.UUID,
    start: date,
    end: date,
    status: str,
    snapshot: dict[str, Any] | None = None,
) -> None:
    with Session(get_engine()) as session:
        session.add(
            Rental(
                listing_id=listing_id,
                renter_id=renter_id,
                start_date=start,
                end_date=end,
                status=status,
                daily_price_snapshot=Decimal("25.00"),
                estimated_total=Decimal("125.00"),
                listing_snapshot=snapshot or {"title": "Cópia de teste"},
                expires_at=datetime.now(UTC) + timedelta(days=2),
            )
        )
        session.commit()


def _set_listing_status(listing_id: int, status: str) -> None:
    with Session(get_engine()) as session:
        listing = session.get(Listing, listing_id)
        assert listing is not None
        listing.status = status
        session.commit()


# ---------------------------------------------------------------------------
# GET /api/listings/{id} · RN-34 · API-ITM-01
# ---------------------------------------------------------------------------


def test_API_ITM_01_requires_login_and_returns_404_for_unknown_listing(
    detail_context: DetailContext,
) -> None:
    ctx = detail_context
    assert TestClient(app).get(ctx.path).status_code == 401

    missing = ctx.get_as(ctx.other_id, "/api/listings/999999999")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "LISTING_NOT_FOUND"

    assert ctx.get_as(ctx.other_id, "/api/listings/0").status_code == 422


def test_API_ITM_01_active_listing_returns_only_public_fields(
    detail_context: DetailContext,
) -> None:
    ctx = detail_context
    response = ctx.get_as(ctx.other_id, ctx.path)

    assert response.status_code == 200
    # Igualdade exata do corpo: qualquer campo privado a mais (RN-15) quebra o teste.
    assert response.json() == {
        "id": ctx.listing_id,
        "unavailable": False,
        "status": "active",
        "title": "Furadeira de impacto",
        "description": "Descrição pública do item.",
        "daily_price": "25.00",
        "max_days": 7,
        "available_from": "2030-06-01",
        "available_until": "2030-06-30",
        "category": ctx.category_name,
        "tags": ctx.tag_names,
        "photos": ctx.photos,
        "owner_username": ctx.owner_username,
        "is_owner": False,
        "pickup_street": "Rua da Retirada",
        "pickup_neighborhood": "Centro",
        "pickup_city": "Rio Grande",
        "pickup_number": None,
        "pickup_complement": None,
    }


def test_API_ITM_01_owner_flag_is_true_only_for_the_owner(detail_context: DetailContext) -> None:
    ctx = detail_context
    owner_view = ctx.get_as(ctx.owner_id, ctx.path).json()
    other_view = ctx.get_as(ctx.other_id, ctx.path).json()

    assert owner_view["is_owner"] is True
    assert other_view["is_owner"] is False


@pytest.mark.parametrize("status", ["paused", "deleted"])
def test_API_ITM_01_unavailable_listing_is_hidden_except_from_the_owner(
    detail_context: DetailContext, status: str
) -> None:
    ctx = detail_context
    _set_listing_status(ctx.listing_id, status)

    hidden = ctx.get_as(ctx.other_id, ctx.path)
    assert hidden.status_code == 200
    assert hidden.json() == {"id": ctx.listing_id, "unavailable": True}

    owner_view = ctx.get_as(ctx.owner_id, ctx.path)
    assert owner_view.status_code == 200
    body = owner_view.json()
    assert body["unavailable"] is False
    assert body["status"] == status
    assert body["title"] == "Furadeira de impacto"
    assert body["is_owner"] is True


def test_API_ITM_01_listing_from_deleted_account_is_unavailable(
    detail_context: DetailContext,
) -> None:
    ctx = detail_context
    with Session(get_engine()) as session:
        owner = session.get(User, ctx.owner_id)
        assert owner is not None
        owner.deleted_at = datetime.now(UTC)
        session.commit()

    response = ctx.get_as(ctx.other_id, ctx.path)
    assert response.status_code == 200
    assert response.json() == {"id": ctx.listing_id, "unavailable": True}


# ---------------------------------------------------------------------------
# Local de retirada · RN-35, RN-15 · API-ITM-02
# ---------------------------------------------------------------------------

ACCEPTED_SNAPSHOT = {
    "title": "Cópia aceita",
    "pickup_cep": CEP,
    "pickup_street": "Rua da Cópia",
    "pickup_number": "77",
    "pickup_complement": "Apto 3",
    "pickup_neighborhood": "Centro",
    "pickup_city": "Rio Grande",
    "pickup_state": "RS",
}


def test_API_ITM_02_hides_number_and_complement_without_accepted_rental(
    detail_context: DetailContext,
) -> None:
    ctx = detail_context
    response = ctx.get_as(ctx.other_id, ctx.path)
    body = response.json()

    assert body["pickup_street"] == "Rua da Retirada"
    assert body["pickup_neighborhood"] == "Centro"
    assert body["pickup_city"] == "Rio Grande"
    assert body["pickup_number"] is None
    assert body["pickup_complement"] is None
    assert CEP not in response.text
    assert not any("cep" in key for key in body)


@pytest.mark.parametrize("status", ["pending", "rejected", "expired", "canceled", "completed"])
def test_API_ITM_02_only_an_accepted_rental_reveals_number_and_complement(
    detail_context: DetailContext, status: str
) -> None:
    ctx = detail_context
    _add_rental(
        ctx.listing_id,
        ctx.renter_id,
        date(2030, 6, 10),
        date(2030, 6, 12),
        status,
        snapshot=ACCEPTED_SNAPSHOT,
    )

    body = ctx.get_as(ctx.renter_id, ctx.path).json()

    assert body["pickup_number"] is None
    assert body["pickup_complement"] is None


def test_API_ITM_02_accepted_renter_reads_number_and_complement_from_the_snapshot(
    detail_context: DetailContext,
) -> None:
    ctx = detail_context
    _add_rental(
        ctx.listing_id,
        ctx.renter_id,
        date(2030, 6, 10),
        date(2030, 6, 12),
        "accepted",
        snapshot=ACCEPTED_SNAPSHOT,
    )

    renter = ctx.get_as(ctx.renter_id, ctx.path)
    other = ctx.get_as(ctx.other_id, ctx.path)

    # Os valores vêm da cópia do aluguel ("77" e "Apto 3"), não do anúncio atual.
    assert renter.json()["pickup_number"] == "77"
    assert renter.json()["pickup_complement"] == "Apto 3"
    assert CEP not in renter.text
    # Outro usuário continua sem ver nada, mesmo com aluguel aceito de terceiros.
    assert other.json()["pickup_number"] is None
    assert other.json()["pickup_complement"] is None


def test_API_ITM_02_accepted_rental_with_incomplete_snapshot_does_not_break(
    detail_context: DetailContext,
) -> None:
    ctx = detail_context
    _add_rental(ctx.listing_id, ctx.renter_id, date(2030, 6, 10), date(2030, 6, 12), "accepted")

    response = ctx.get_as(ctx.renter_id, ctx.path)

    assert response.status_code == 200
    assert response.json()["pickup_number"] is None
    assert response.json()["pickup_complement"] is None


def test_API_ITM_02_owner_does_not_receive_number_and_complement_here(
    detail_context: DetailContext,
) -> None:
    """RN-35 libera número e complemento só ao locatário; o dono os edita em /api/me/listings."""
    ctx = detail_context
    body = ctx.get_as(ctx.owner_id, ctx.path).json()

    assert body["pickup_number"] is None
    assert body["pickup_complement"] is None


# ---------------------------------------------------------------------------
# GET /api/listings/{id}/booked-periods · F-29 · RN-42, RN-44
# ---------------------------------------------------------------------------


def test_booked_periods_requires_login_and_returns_404_for_unknown_listing(
    detail_context: DetailContext,
) -> None:
    ctx = detail_context
    assert TestClient(app).get(f"{ctx.path}/booked-periods").status_code == 401

    missing = ctx.get_as(ctx.other_id, "/api/listings/999999999/booked-periods")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "LISTING_NOT_FOUND"


def test_booked_periods_is_empty_without_rentals(detail_context: DetailContext) -> None:
    ctx = detail_context
    response = ctx.get_as(ctx.other_id, f"{ctx.path}/booked-periods")

    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_booked_periods_list_only_accepted_and_completed_rentals_in_order(
    detail_context: DetailContext,
) -> None:
    ctx = detail_context
    # Só accepted e completed entram na restrição de exclusão (RN-42), então não se sobrepõem.
    _add_rental(ctx.listing_id, ctx.renter_id, date(2030, 6, 10), date(2030, 6, 14), "accepted")
    _add_rental(ctx.listing_id, ctx.renter_id, date(2030, 6, 2), date(2030, 6, 4), "completed")
    # Os demais estados não bloqueiam datas; pendentes podem se sobrepor (RN-44).
    for status, start, end in [
        ("pending", date(2030, 6, 10), date(2030, 6, 12)),
        ("pending", date(2030, 6, 10), date(2030, 6, 12)),
        ("rejected", date(2030, 6, 20), date(2030, 6, 22)),
        ("expired", date(2030, 6, 20), date(2030, 6, 22)),
        ("canceled", date(2030, 6, 20), date(2030, 6, 22)),
    ]:
        _add_rental(ctx.listing_id, ctx.other_id, start, end, status)

    response = ctx.get_as(ctx.other_id, f"{ctx.path}/booked-periods")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"start_date": "2030-06-02", "end_date": "2030-06-04"},
            {"start_date": "2030-06-10", "end_date": "2030-06-14"},
        ]
    }


def test_booked_periods_of_an_unavailable_listing_are_visible_only_to_the_owner(
    detail_context: DetailContext,
) -> None:
    ctx = detail_context
    _add_rental(ctx.listing_id, ctx.renter_id, date(2030, 6, 10), date(2030, 6, 14), "accepted")
    _set_listing_status(ctx.listing_id, "paused")

    other = ctx.get_as(ctx.other_id, f"{ctx.path}/booked-periods")
    owner = ctx.get_as(ctx.owner_id, f"{ctx.path}/booked-periods")

    assert other.json() == {"items": []}
    assert owner.json() == {"items": [{"start_date": "2030-06-10", "end_date": "2030-06-14"}]}

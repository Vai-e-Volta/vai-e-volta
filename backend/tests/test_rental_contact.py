"""H017-4: contato das partes nas respostas de aluguel (F-39, RN-17, RN-35).

API-USR-03: o telefone da outra parte só aparece para as duas partes de um aluguel `accepted`.
API-ITM-02: o endereço completo de retirada, lido da listing_snapshot, segue a mesma regra.
"""

from __future__ import annotations

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
from app.models import Category, Listing, Rental, User
from app.schemas.rentals import AcceptedRentalListItem, RentalListItem
from app.security.session import create_session_token
from app.services.rental_situation import today_br
from app.services.rentals import serialize_rental_item

OWNER_PHONE = "51988880001"
RENTER_PHONE = "51988880002"
OUTSIDER_PHONE = "51988880003"

# Endereço do anúncio hoje (editado depois do aceite) e cópia guardada no aluguel.
SNAPSHOT = {
    "title": "Cópia congelada",
    "pickup_cep": "96200999",
    "pickup_street": "Rua da Cópia",
    "pickup_number": "77",
    "pickup_complement": "Apto 3",
    "pickup_neighborhood": "Cassino",
    "pickup_city": "Rio Grande",
    "pickup_state": "RS",
}
SNAPSHOT_ADDRESS = {
    "street": "Rua da Cópia",
    "number": "77",
    "complement": "Apto 3",
    "neighborhood": "Cassino",
    "city": "Rio Grande",
    "state": "RS",
}
PRIVATE_TEXTS = [OWNER_PHONE, RENTER_PHONE, "Rua da Cópia", "Apto 3", "96200999", "96200000"]


@dataclass
class ContactWorld:
    client: TestClient
    owner_id: uuid.UUID
    renter_id: uuid.UUID
    outsider_id: uuid.UUID
    listing_id: int

    def rental(
        self,
        status: str = "accepted",
        renter_id: uuid.UUID | None = None,
        snapshot: dict[str, Any] | None = None,
        start_in: int = 2,
        end_in: int = 4,
    ) -> int:
        today = today_br()
        with Session(get_engine()) as session:
            rental = Rental(
                listing_id=self.listing_id,
                renter_id=renter_id or self.renter_id,
                start_date=today + timedelta(days=start_in),
                end_date=today + timedelta(days=end_in),
                status=status,
                daily_price_snapshot=Decimal("25.00"),
                estimated_total=Decimal("75.00"),
                listing_snapshot=SNAPSHOT if snapshot is None else snapshot,
                expires_at=datetime.now(UTC) + timedelta(hours=48),
            )
            session.add(rental)
            session.commit()
            return rental.id

    def delete_account(self, user_id: uuid.UUID) -> None:
        with Session(get_engine()) as session:
            user = session.get(User, user_id)
            assert user is not None
            user.deleted_at = datetime.now(UTC)
            session.commit()

    def get(self, user_id: uuid.UUID, role: str, scope: str) -> Any:
        self.client.cookies.set("vv_session", create_session_token(user_id, 0))
        response = self.client.get("/api/me/rentals", params={"role": role, "scope": scope})
        assert response.status_code == 200, response.text
        return response


def _make_user(user_id: uuid.UUID, prefix: str, phone: str) -> User:
    suffix = f"{user_id.int % 10**11:011d}"
    return User(
        id=user_id,
        full_name=f"Pessoa {prefix}",
        username=f"{prefix}_{suffix}",
        email=f"{prefix}-{suffix}@example.invalid",
        cpf=suffix,
        phone=phone,
        password_hash="test-only-hash",
        cep="96200000",
        street="Rua Cadastral",
        number="1",
        neighborhood="Centro",
        city="Rio Grande",
        state="RS",
    )


@pytest.fixture
def world() -> Generator[ContactWorld, None, None]:
    upgrade_database()
    engine = get_engine()
    owner_id, renter_id, outsider_id = (uuid.uuid4() for _ in range(3))

    def override_db() -> Generator[Session, None, None]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        today = today_br()
        with Session(engine) as session:
            session.add_all(
                [
                    _make_user(owner_id, "dono", OWNER_PHONE),
                    _make_user(renter_id, "loc", RENTER_PHONE),
                    _make_user(outsider_id, "outro", OUTSIDER_PHONE),
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
                available_from=today,
                available_until=today + timedelta(days=60),
                pickup_cep="96200000",
                pickup_street="Rua Atual",
                pickup_number="100",
                pickup_complement="Fundos",
                pickup_neighborhood="Centro",
                pickup_city="Rio Grande",
                pickup_state="RS",
            )
            session.add(listing)
            session.commit()
            listing_id = listing.id

        with TestClient(app) as client:
            yield ContactWorld(client, owner_id, renter_id, outsider_id, listing_id)
    finally:
        app.dependency_overrides.pop(get_db, None)
        with Session(engine) as session:
            session.execute(delete(Rental).where(Rental.listing_id == listing_id))
            session.execute(delete(Listing).where(Listing.id == listing_id))
            owners = (owner_id, renter_id, outsider_id)
            session.execute(delete(User).where(User.id.in_(owners)))
            session.commit()
        engine.dispose()


def test_API_USR_03_both_parties_of_an_accepted_rental_receive_phone_and_address(
    world: ContactWorld,
) -> None:
    rental_id = world.rental()

    as_renter = world.get(world.renter_id, "renter", "active")
    as_owner = world.get(world.owner_id, "owner", "active")

    renter_item = as_renter.json()["items"][0]
    owner_item = as_owner.json()["items"][0]
    assert renter_item["id"] == owner_item["id"] == rental_id
    # Cada parte recebe o telefone da outra, e ambas o endereço da cópia do aluguel (RN-35).
    assert renter_item["other_party_phone"] == OWNER_PHONE
    assert owner_item["other_party_phone"] == RENTER_PHONE
    assert renter_item["pickup_address"] == SNAPSHOT_ADDRESS
    assert owner_item["pickup_address"] == SNAPSHOT_ADDRESS
    # O CEP nunca é devolvido, nem o do anúncio nem o da cópia.
    for response in (as_renter, as_owner):
        assert "96200999" not in response.text
        assert "96200000" not in response.text
        assert "pickup_cep" not in response.text
        assert '"cep"' not in response.text
    # O endereço atual do anúncio não vaza: vale o que foi congelado no aluguel.
    assert "Rua Atual" not in as_renter.text


@pytest.mark.parametrize("status", ["pending", "rejected", "expired", "canceled", "completed"])
def test_API_USR_03_non_accepted_rentals_never_carry_contact_fields(
    world: ContactWorld, status: str
) -> None:
    world.rental(status=status)
    scope = "active" if status == "pending" else "history"

    for user_id, role in ((world.renter_id, "renter"), (world.owner_id, "owner")):
        response = world.get(user_id, role, scope)
        item = response.json()["items"][0]
        assert "other_party_phone" not in item
        assert "pickup_address" not in item
        for private in PRIVATE_TEXTS:
            assert private not in response.text


def test_API_USR_03_a_third_party_never_receives_the_rental_or_its_contact(
    world: ContactWorld,
) -> None:
    world.rental()
    own = world.rental(status="pending", renter_id=world.outsider_id, start_in=10, end_in=12)

    for role in ("renter", "owner"):
        for scope in ("active", "history"):
            response = world.get(world.outsider_id, role, scope)
            ids = {item["id"] for item in response.json()["items"]}
            assert ids == ({own} if (role, scope) == ("renter", "active") else set())
            for private in PRIVATE_TEXTS:
                assert private not in response.text


@pytest.mark.parametrize("deleted", ["owner_id", "renter_id"])
def test_API_USR_03_deleted_counterpart_leaves_no_contact(
    world: ContactWorld, deleted: str
) -> None:
    world.rental()
    world.delete_account(getattr(world, deleted))
    viewer, role = (
        (world.renter_id, "renter") if deleted == "owner_id" else (world.owner_id, "owner")
    )

    response = world.get(viewer, role, "active")

    item = response.json()["items"][0]
    assert item["other_party_name"] == "Usuário excluído"
    assert "other_party_phone" not in item
    assert "pickup_address" not in item
    for private in PRIVATE_TEXTS:
        assert private not in response.text


def test_API_ITM_02_accepted_rental_without_pickup_data_has_a_null_address(
    world: ContactWorld,
) -> None:
    world.rental(snapshot={"title": "Cópia sem endereço"})

    item = world.get(world.renter_id, "renter", "active").json()["items"][0]

    assert item["other_party_phone"] == OWNER_PHONE
    assert item["pickup_address"] is None


def test_API_ITM_02_partial_snapshot_returns_only_what_it_has(world: ContactWorld) -> None:
    world.rental(snapshot={"title": "Cópia parcial", "pickup_street": "Rua da Cópia"})

    item = world.get(world.renter_id, "renter", "active").json()["items"][0]

    assert item["pickup_address"] == {
        "street": "Rua da Cópia",
        "number": None,
        "complement": None,
        "neighborhood": None,
        "city": None,
        "state": None,
    }


def test_API_USR_03_serializer_checks_the_viewer_before_adding_contact() -> None:
    """O ponto único de serialização não confia no chamador: só as duas partes recebem contato."""
    now = datetime.now(UTC)
    owner_id, renter_id = uuid.uuid4(), uuid.uuid4()
    owner = User(id=owner_id, full_name="Dono", phone=OWNER_PHONE, deleted_at=None)
    rental = Rental(
        id=1,
        listing_id=2,
        renter_id=renter_id,
        start_date=today_br() + timedelta(days=2),
        end_date=today_br() + timedelta(days=4),
        status="accepted",
        daily_price_snapshot=Decimal("25.00"),
        estimated_total=Decimal("75.00"),
        listing_snapshot=SNAPSHOT,
        expires_at=now + timedelta(hours=48),
        created_at=now,
    )
    listing = Listing(id=2, owner_id=owner_id)

    def serialize(viewer_id: uuid.UUID) -> RentalListItem:
        viewer = User(id=viewer_id)
        return serialize_rental_item(rental, listing, owner, None, viewer, now)

    stranger = serialize(uuid.uuid4())
    assert type(stranger) is RentalListItem
    assert not hasattr(stranger, "other_party_phone")
    assert isinstance(serialize(renter_id), AcceptedRentalListItem)
    assert isinstance(serialize(owner_id), AcceptedRentalListItem)

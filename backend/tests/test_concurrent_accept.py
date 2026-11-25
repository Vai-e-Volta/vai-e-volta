"""H017-2: aceite concorrente (RN-42, RN-46) · DB-RNT-01 e API-RNT-09.

Estes testes fazem commit de verdade e usam threads (duas sessões ao mesmo tempo); por isso não
congelam o relógio (freezegun é global) e limpam o banco com TRUNCATE ao final (Doc. Técnico 15.2).
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.routes.auth import get_db
from app.db import get_engine
from app.main import app
from app.migrations import upgrade_database
from app.models import Category, Listing, Rental, User
from app.security.session import create_session_token
from app.services.rental_situation import today_br

ROUNDS = 5


@dataclass
class ConcurrencyWorld:
    owner_id: uuid.UUID
    renter_id: uuid.UUID
    other_renter_id: uuid.UUID
    listing_id: int

    def proposal(
        self, renter_id: uuid.UUID, start_in: int, end_in: int, status: str = "pending"
    ) -> int:
        """Proposta de `start_in` a `end_in` dias a partir de hoje (inclusivos)."""
        today = today_br()
        with Session(get_engine()) as session:
            rental = Rental(
                listing_id=self.listing_id,
                renter_id=renter_id,
                start_date=today + timedelta(days=start_in),
                end_date=today + timedelta(days=end_in),
                status=status,
                daily_price_snapshot=Decimal("25.00"),
                estimated_total=Decimal("125.00"),
                listing_snapshot={"title": "Cópia de teste"},
                expires_at=datetime.now(UTC) + timedelta(hours=48),
            )
            session.add(rental)
            session.commit()
            return rental.id

    def owner_client(self) -> TestClient:
        client = TestClient(app)
        client.cookies.set("vv_session", create_session_token(self.owner_id, 0))
        return client

    def status(self, rental_id: int) -> str:
        with Session(get_engine()) as session:
            rental = session.get(Rental, rental_id)
            assert rental is not None
            return rental.status


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
def world() -> Generator[ConcurrencyWorld, None, None]:
    upgrade_database()
    engine = get_engine()
    owner_id, renter_id, other_renter_id = (uuid.uuid4() for _ in range(3))

    def override_db() -> Generator[Session, None, None]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        today = today_br()
        with Session(engine) as session:
            session.add_all(
                [
                    _make_user(owner_id, "dono"),
                    _make_user(renter_id, "loc"),
                    _make_user(other_renter_id, "loc2"),
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
                max_days=30,
                available_from=today,
                available_until=today + timedelta(days=400),
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

        yield ConcurrencyWorld(owner_id, renter_id, other_renter_id, listing_id)
    finally:
        app.dependency_overrides.pop(get_db, None)
        # Testes com commit e threads: TRUNCATE em vez de rollback (Doc. Técnico 15.2).
        with engine.begin() as connection:
            connection.execute(text("TRUNCATE TABLE rentals, listings, users CASCADE"))
        engine.dispose()


def test_DB_RNT_01_concurrent_acceptances_raise_exclusion_violation_for_the_second_session(
    world: ConcurrencyWorld,
) -> None:
    first_id = world.proposal(world.renter_id, 5, 9)
    second_id = world.proposal(world.other_renter_id, 7, 11)  # sobrepõe a primeira
    engine = get_engine()
    errors: list[IntegrityError] = []

    first = Session(engine)
    second = Session(engine)
    try:
        first.execute(update(Rental).where(Rental.id == first_id).values(status="accepted"))

        def second_accepts() -> None:
            try:
                second.execute(
                    update(Rental).where(Rental.id == second_id).values(status="accepted")
                )
                second.commit()
            except IntegrityError as error:
                second.rollback()
                errors.append(error)

        thread = threading.Thread(target=second_accepts)
        thread.start()
        # A segunda sessão espera a primeira terminar; o resultado é o mesmo se ela chegar depois.
        time.sleep(0.5)
        first.commit()
        thread.join(timeout=15)
        assert not thread.is_alive()
    finally:
        first.close()
        second.close()

    assert len(errors) == 1
    assert getattr(errors[0].orig, "sqlstate", None) == "23P01"
    assert errors[0].orig.diag.constraint_name == "rentals_no_overlap"
    assert world.status(first_id) == "accepted"
    assert world.status(second_id) == "pending"


def test_API_RNT_09_simultaneous_acceptances_of_overlapping_proposals_have_exactly_one_winner(
    world: ConcurrencyWorld,
) -> None:
    for round_number in range(ROUNDS):
        # Cada rodada usa um período próprio, para as rodadas não se sobreporem.
        base = 10 + round_number * 30
        first_id = world.proposal(world.renter_id, base, base + 4)
        second_id = world.proposal(world.other_renter_id, base + 2, base + 6)
        barrier = threading.Barrier(2)
        responses: dict[int, Any] = {}

        def accept(rental_id: int) -> None:
            client = world.owner_client()
            barrier.wait(timeout=15)
            responses[rental_id] = client.post(f"/api/rentals/{rental_id}/accept")

        threads = [threading.Thread(target=accept, args=(rid,)) for rid in (first_id, second_id)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
        assert all(not thread.is_alive() for thread in threads), round_number

        codes = sorted(response.status_code for response in responses.values())
        assert codes == [204, 409], (round_number, codes)
        loser = next(response for response in responses.values() if response.status_code == 409)
        # O perdedor nunca vira erro 500: ou vê a proposta já recusada, ou o banco o barra.
        assert loser.json()["error"]["code"] in {"INVALID_STATE", "RENTAL_OVERLAP"}
        assert {world.status(first_id), world.status(second_id)} == {"accepted", "rejected"}


def test_API_RNT_09_exclusion_violation_becomes_rental_overlap_and_undoes_everything(
    world: ConcurrencyWorld, caplog: pytest.LogCaptureFixture
) -> None:
    # Situação que a corrida entre propor e aceitar pode deixar: uma proposta pendente que já
    # nasceu sobreposta a um aluguel aceito (propostas pendentes não entram na restrição, RN-44).
    accepted_id = world.proposal(world.renter_id, 5, 9, status="accepted")
    target_id = world.proposal(world.other_renter_id, 8, 12)
    neighbour_id = world.proposal(world.renter_id, 11, 14)  # sobrepõe só a proposta alvo
    caplog.set_level("WARNING", logger="app.services.rental_accept")

    response = world.owner_client().post(f"/api/rentals/{target_id}/accept")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RENTAL_OVERLAP"
    # Nada do aceite sobrevive: nem a proposta, nem a recusa automática da vizinha.
    assert world.status(accepted_id) == "accepted"
    assert world.status(target_id) == "pending"
    assert world.status(neighbour_id) == "pending"
    assert "Rental booking conflict on accept" in caplog.text
    assert any(
        record.levelname == "WARNING"
        and getattr(record, "rental_id", None) == target_id
        and getattr(record, "listing_id", None) == world.listing_id
        for record in caplog.records
    )

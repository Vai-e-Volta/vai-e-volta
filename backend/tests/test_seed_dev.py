from __future__ import annotations

import os
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import Connection, func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import app
from app.models import Listing, ListingPhoto, Rental, User
from app.scripts import seed_dev
from app.services.rental_situation import rental_situation


def test_seed_creates_demo_and_can_run_twice_without_overwriting(
    db: Connection, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(seed_dev.settings, "APP_ENV", "dev")
    monkeypatch.setattr(seed_dev.settings, "UPLOAD_DIR", str(tmp_path))
    now = datetime.now(UTC)
    with Session(
        bind=db, join_transaction_mode="create_savepoint", expire_on_commit=False
    ) as session:
        seed_dev.seed_demo(session, now)
        users = session.scalars(
            select(User).where(User.id.in_([seed_dev._user_id(row[0]) for row in seed_dev._USERS]))
        ).all()
        listings = session.scalars(
            select(Listing).where(
                Listing.id.between(seed_dev._LISTING_BASE, seed_dev._LISTING_BASE + 14)
            )
        ).all()
        rentals = session.scalars(
            select(Rental).where(
                Rental.id.between(seed_dev._RENTAL_BASE, seed_dev._RENTAL_BASE + 4)
            )
        ).all()
        assert len(users) == 5 and len(listings) == 15 and len(rentals) == 5
        assert {user.username for user in users} == {row[0] for row in seed_dev._USERS}
        assert all(user.email.endswith("@exemplo.test") for user in users)
        assert {
            rental_situation(r.status, r.start_date, r.end_date, r.expires_at, now=now)
            for r in rentals
        } == {"Aguardando", "Reservado", "Em andamento", "Atrasado", "Concluído"}
        assert (
            session.scalar(
                select(func.count(ListingPhoto.id)).where(
                    ListingPhoto.listing_id.between(
                        seed_dev._LISTING_BASE, seed_dev._LISTING_BASE + 14
                    )
                )
            )
            == 15
        )
        assert len(list(tmp_path.glob("*.png"))) == 15
        for photo in tmp_path.glob("*.png"):
            if os.name != "nt":
                assert photo.stat().st_mode & 0o444 == 0o444
            with Image.open(photo) as image:
                image.verify()
        elisa = session.get(User, seed_dev._user_id("elisa_rocha"))
        assert elisa is not None and elisa.deleted_at is not None and elisa.purge_after > now
        assert all(r.status == "completed" for r in rentals if r.renter_id == elisa.id)
        assert all(r.listing_snapshot["category"] and r.listing_snapshot["tags"] for r in rentals)
        assert all(r.listing_snapshot["photos"] for r in rentals)
        original_hash = elisa.password_hash
        listing = session.get(Listing, seed_dev._LISTING_BASE)
        assert listing is not None
        listing.title = "Alteração do desenvolvedor"
        session.commit()
        seed_dev.seed_demo(session, now)
        assert session.get(Listing, seed_dev._LISTING_BASE).title == "Alteração do desenvolvedor"
        assert session.get(User, elisa.id).password_hash == original_hash
        assert (
            session.scalar(
                select(func.count(Listing.id)).where(
                    Listing.id.between(seed_dev._LISTING_BASE, seed_dev._LISTING_BASE + 14)
                )
            )
            == 15
        )
        assert (
            session.scalar(
                select(func.count(Rental.id)).where(
                    Rental.id.between(seed_dev._RENTAL_BASE, seed_dev._RENTAL_BASE + 4)
                )
            )
            == 5
        )
        assert len(list(tmp_path.glob("*.png"))) == 15

    def override_db() -> Generator[Session, None, None]:
        with Session(
            bind=db, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            for username, *_ in seed_dev._USERS:
                response = client.post(
                    "/api/auth/login", json={"identifier": username, "password": "Dev@12345"}
                )
                assert response.status_code == 200, response.text
                assert response.json()["username"] == username
        with Session(
            bind=db, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            reactivated = session.get(User, seed_dev._user_id("elisa_rocha"))
            assert reactivated is not None and reactivated.deleted_at is None
            seed_dev.seed_demo(session, now)
            assert session.get(User, reactivated.id).deleted_at is None
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.parametrize("environment", ["test", "prod"])
def test_seed_refuses_non_development_before_writing(
    db: Connection, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, environment: str
) -> None:
    monkeypatch.setattr(seed_dev.settings, "APP_ENV", environment)
    target = tmp_path / "uploads"
    monkeypatch.setattr(seed_dev.settings, "UPLOAD_DIR", str(target))
    with Session(bind=db, join_transaction_mode="create_savepoint") as session:
        with pytest.raises(RuntimeError, match="APP_ENV=dev"):
            seed_dev.seed_demo(session)
        assert session.get(User, seed_dev._user_id("ana_silva")) is None
    assert not target.exists()


def test_seed_rolls_back_created_rows_and_files_on_failure(
    db: Connection, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(seed_dev.settings, "APP_ENV", "dev")
    monkeypatch.setattr(seed_dev.settings, "UPLOAD_DIR", str(tmp_path))
    original = seed_dev._create_demo_image
    calls = 0

    def fail_second(path: Path, title: str, index: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated image error")
        original(path, title, index)

    monkeypatch.setattr(seed_dev, "_create_demo_image", fail_second)
    with Session(bind=db, join_transaction_mode="create_savepoint") as session:
        with pytest.raises(OSError, match="simulated image error"):
            seed_dev.seed_demo(session)
        assert session.get(User, seed_dev._user_id("ana_silva")) is None
        assert session.get(Listing, seed_dev._LISTING_BASE) is None
    assert list(tmp_path.iterdir()) == []

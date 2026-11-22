from __future__ import annotations

import uuid
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from freezegun import freeze_time
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.routes.auth import get_db
from app.db import get_engine
from app.main import app
from app.models import User
from app.worker.tasks import anonymize_accounts


@pytest.fixture
def auth_context() -> Generator[tuple[TestClient, str], None, None]:
    prefix = f"t{uuid.uuid4().hex[:10]}_"

    def override_db() -> Generator[Session, None, None]:
        with Session(get_engine(), expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client, prefix
    finally:
        app.dependency_overrides.clear()


def _register(client: TestClient, prefix: str) -> dict[str, str]:
    base = f"{uuid.uuid4().int % 1_000_000_000:09d}"
    digits = [int(character) for character in base]
    first = sum(value * weight for value, weight in zip(digits, range(10, 1, -1)))
    first = 0 if first % 11 < 2 else 11 - first % 11
    second = sum(value * weight for value, weight in zip(digits + [first], range(11, 1, -1)))
    second = 0 if second % 11 < 2 else 11 - second % 11
    cpf = "".join(map(str, digits + [first, second]))
    payload = {
        "full_name": "Pessoa de Teste",
        "username": f"{prefix}user",
        "email": f"{prefix}user@example.com",
        "password": "SenhaForte1!",
        "cpf": cpf,
        "phone": "51999990000",
        "cep": "96200000",
        "street": "Rua de Teste",
        "number": "123",
        "complement": None,
        "neighborhood": "Centro",
        "city": "Rio Grande",
        "state": "RS",
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return payload


def test_login_and_anonymization_serialize_on_user(
    auth_context: tuple[TestClient, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import authentication

    client, prefix = auth_context
    payload = _register(client, prefix)
    now = datetime.now(UTC)
    with Session(get_engine()) as session:
        user = session.scalar(select(User).where(User.email == payload["email"]))
        assert user is not None
        user_id = user.id
        user.deleted_at = now - timedelta(days=364)
        user.purge_after = now + timedelta(minutes=1)
        session.commit()

    verifying, release = Event(), Event()
    original_verify = authentication._verify_password

    def delayed_verify(password_hash: str, password: str, *, fallback: bool = True) -> bool:
        verifying.set()
        if not release.wait(10):
            raise TimeoutError("test did not release password verification")
        return original_verify(password_hash, password, fallback=fallback)

    monkeypatch.setattr(authentication, "_verify_password", delayed_verify)
    with ThreadPoolExecutor(max_workers=1) as pool:
        login = pool.submit(
            client.post,
            "/api/auth/login",
            json={"identifier": payload["email"], "password": payload["password"]},
        )
        try:
            assert verifying.wait(10)
            with Session(get_engine()) as session:
                anonymize_accounts(session, now + timedelta(minutes=2))
                session.commit()
                still_locked = session.get(User, user_id)
                assert still_locked is not None and still_locked.anonymized_at is None
                assert still_locked.deleted_at is not None
        finally:
            release.set()
        assert login.result(timeout=10).status_code == 200

    with Session(get_engine()) as session:
        anonymize_accounts(session, now + timedelta(minutes=2))
        session.commit()
        user = session.get(User, user_id)
        assert user is not None and user.deleted_at is None and user.anonymized_at is None


def test_edit_account_validates_and_reports_conflicts(auth_context: tuple[TestClient, str]) -> None:
    client, prefix = auth_context
    first = _register(client, prefix)
    second = _register(client, prefix + "b")
    assert (
        client.post(
            "/api/auth/login", json={"identifier": first["email"], "password": first["password"]}
        ).status_code
        == 200
    )
    updated = client.patch("/api/me", json={"full_name": "Novo Nome", "state": "sp"})
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Novo Nome"
    assert updated.json()["state"] == "SP"
    conflict = client.patch("/api/me", json={"email": second["email"]})
    assert conflict.status_code == 409
    assert conflict.json()["error"]["fields"]["email"]
    assert client.patch("/api/me", json={"cpf": "12345678900"}).status_code == 422
    assert client.patch("/api/me", json={"password": "NewPassword1!"}).status_code == 422
    assert client.patch("/api/me", json={"full_name": None}).status_code == 422
    assert TestClient(app).patch("/api/me", json={"city": "Outra"}).status_code == 401


def test_login_session_me_and_logout(auth_context: tuple[TestClient, str]) -> None:
    client, prefix = auth_context
    unsupported_media_type = client.post(
        "/api/auth/login", content="{}", headers={"content-type": "text/plain"}
    )
    assert unsupported_media_type.status_code == 415
    payload = _register(client, prefix)

    response = client.post(
        "/api/auth/login",
        json={"identifier": payload["email"].upper(), "password": payload["password"]},
    )
    assert response.status_code == 200
    cookie = response.cookies["vv_session"]
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=lax" in response.headers["set-cookie"].lower()
    assert client.get("/api/auth/me").json()["email"] == payload["email"]

    other_client = TestClient(app)
    bad_known = other_client.post(
        "/api/auth/login", json={"identifier": payload["username"], "password": "Errada1!"}
    )
    bad_unknown = other_client.post(
        "/api/auth/login", json={"identifier": "unknown@example.com", "password": "Errada1!"}
    )
    assert bad_known.status_code == bad_unknown.status_code == 401
    assert bad_known.json() == bad_unknown.json()

    logged_out = client.post("/api/auth/logout", json={})
    assert logged_out.status_code == 204
    assert "max-age=0" in logged_out.headers["set-cookie"].lower()
    assert client.get("/api/auth/me").status_code == 401
    assert cookie


def test_login_lockout_returns_retry_after(
    auth_context: tuple[TestClient, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with freeze_time("2026-01-01T12:00:00+00:00") as frozen_time:
        caplog.set_level("WARNING", logger="app.services.authentication")

        client, prefix = auth_context
        payload = _register(client, prefix)

        for _ in range(5):
            response = client.post(
                "/api/auth/login",
                json={"identifier": payload["username"], "password": "Wrong1!"},
            )
            assert response.status_code == 401

        locked = client.post(
            "/api/auth/login",
            json={"identifier": payload["username"], "password": payload["password"]},
        )

        assert locked.status_code == 429
        assert int(locked.headers["retry-after"]) == 900
        assert locked.json()["error"]["code"] == "LOGIN_LOCKED"

        assert "Login blocked due to too many failed attempts" in caplog.text
        assert payload["username"] not in caplog.text

        frozen_time.tick(delta=timedelta(minutes=15))

        unlocked = client.post(
            "/api/auth/login",
            json={"identifier": payload["username"], "password": payload["password"]},
        )
        assert unlocked.status_code == 200


def test_login_remains_locked_after_failure_window_expires(
    auth_context: tuple[TestClient, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LOGIN_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("LOGIN_WINDOW_MINUTES", "5")
    monkeypatch.setenv("LOGIN_LOCK_MINUTES", "15")

    with freeze_time("2026-01-01T12:00:00+00:00") as frozen_time:
        client, prefix = auth_context
        payload = _register(client, prefix)

        for _ in range(3):
            response = client.post(
                "/api/auth/login",
                json={"identifier": payload["username"], "password": "Wrong1!"},
            )
            assert response.status_code == 401

        locked = client.post(
            "/api/auth/login",
            json={"identifier": payload["username"], "password": payload["password"]},
        )
        assert locked.status_code == 429
        assert int(locked.headers["retry-after"]) == 900

        frozen_time.tick(delta=timedelta(minutes=6))

        still_locked = client.post(
            "/api/auth/login",
            json={"identifier": payload["username"], "password": payload["password"]},
        )

        assert still_locked.status_code == 429
        assert int(still_locked.headers["retry-after"]) == 540
        assert still_locked.json()["error"]["code"] == "LOGIN_LOCKED"


def test_change_password_rotates_other_sessions_and_keeps_current(
    auth_context: tuple[TestClient, str],
) -> None:
    client, prefix = auth_context
    payload = _register(client, prefix)
    client.post(
        "/api/auth/login", json={"identifier": payload["username"], "password": payload["password"]}
    )
    old_token = client.cookies["vv_session"]
    previous_session = TestClient(app)
    previous_session.cookies.set("vv_session", old_token)

    wrong_current = client.put(
        "/api/me/password",
        json={"current_password": "Wrong1!", "new_password": "OutraSenha2!"},
    )
    assert wrong_current.status_code == 401
    invalid_new = client.put(
        "/api/me/password",
        json={"current_password": payload["password"], "new_password": "weak"},
    )
    assert invalid_new.status_code == 422
    assert "new_password" in invalid_new.json()["error"]["fields"]

    changed = client.put(
        "/api/me/password",
        json={"current_password": payload["password"], "new_password": "OutraSenha2!"},
    )
    assert changed.status_code == 204
    assert client.cookies["vv_session"] != old_token
    assert client.get("/api/auth/me").status_code == 200
    assert previous_session.get("/api/auth/me").status_code == 401


def test_delete_account_blocks_active_rental_and_reactivates_within_retention(
    auth_context: tuple[TestClient, str],
) -> None:
    client, prefix = auth_context
    payload = _register(client, prefix)
    login = client.post(
        "/api/auth/login", json={"identifier": payload["username"], "password": payload["password"]}
    )
    user_id = login.json()["id"]

    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    with Session(get_engine()) as session:
        category_id = session.execute(text("SELECT min(id) FROM categories")).scalar_one()
        listing_id = session.execute(
            text(
                "INSERT INTO listings (owner_id, category_id, title, description, daily_price, "
                "max_days, available_from, available_until, pickup_cep, pickup_street, "
                "pickup_number, pickup_neighborhood, pickup_city, pickup_state) "
                "VALUES (:owner, :category, 'Furadeira', 'Item de teste', 25.00, 7, :start, "
                ":end, '96200000', 'Rua Teste', '1', 'Centro', 'Rio Grande', 'RS') RETURNING id"
            ),
            {
                "owner": user_id,
                "category": category_id,
                "start": today,
                "end": today + timedelta(days=30),
            },
        ).scalar_one()
        session.execute(
            text(
                "INSERT INTO rentals (listing_id, renter_id, start_date, end_date, status, "
                "daily_price_snapshot, estimated_total, listing_snapshot, expires_at) "
                "VALUES (:listing, :renter, :start, :end, 'accepted', 25.00, 50.00, '{}'::jsonb, "
                ":expires)"
            ),
            {
                "listing": listing_id,
                "renter": user_id,
                "start": today + timedelta(days=1),
                "end": today + timedelta(days=2),
                "expires": datetime.now(UTC) + timedelta(days=3),
            },
        )
        session.commit()

    blocked = client.request("DELETE", "/api/me", json={"password": payload["password"]})
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "ACCOUNT_HAS_ACTIVE_RENTAL"

    with Session(get_engine()) as session:
        session.execute(
            text("DELETE FROM rentals WHERE listing_id = :listing"), {"listing": listing_id}
        )
        session.execute(
            text(
                "INSERT INTO rentals (listing_id, renter_id, start_date, end_date, status, "
                "daily_price_snapshot, estimated_total, listing_snapshot, expires_at) "
                "VALUES (:listing, :renter, :start, :end, 'pending', 25.00, 50.00, '{}'::jsonb, "
                ":expires)"
            ),
            {
                "listing": listing_id,
                "renter": user_id,
                "start": today + timedelta(days=1),
                "end": today + timedelta(days=2),
                "expires": datetime.now(UTC) + timedelta(days=3),
            },
        )
        session.commit()

    deleted = client.request("DELETE", "/api/me", json={"password": payload["password"]})
    assert deleted.status_code == 204
    with Session(get_engine()) as session:
        user = session.get(User, user_id)
        assert user is not None and user.deleted_at is not None and user.purge_after is not None
        assert (
            session.execute(
                text("SELECT status FROM listings WHERE id=:id"), {"id": listing_id}
            ).scalar_one()
            == "paused"
        )
        assert (
            session.execute(
                text("SELECT status FROM rentals WHERE listing_id=:id"), {"id": listing_id}
            ).scalar_one()
            == "canceled"
        )

    reactivated = client.post(
        "/api/auth/login", json={"identifier": payload["email"], "password": payload["password"]}
    )
    assert reactivated.status_code == 200
    with Session(get_engine()) as session:
        user = session.get(User, user_id)
        assert user is not None and user.deleted_at is None and user.purge_after is None
        assert (
            session.execute(
                text("SELECT status FROM listings WHERE id=:id"), {"id": listing_id}
            ).scalar_one()
            == "paused"
        )

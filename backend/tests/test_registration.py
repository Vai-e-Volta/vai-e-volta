from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import get_db, get_engine
from app.main import app
from app.models import User


@pytest.fixture
def registration_context() -> Generator[tuple[TestClient, str], None, None]:
    username_prefix = f"t{uuid.uuid4().hex[:10]}_"

    def override_db() -> Generator[Session, None, None]:
        with Session(get_engine()) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client, username_prefix
    finally:
        app.dependency_overrides.clear()
        with Session(get_engine()) as session:
            session.query(User).filter(User.username.like(f"{username_prefix}%")).delete(
                synchronize_session=False
            )
            session.commit()


def _valid_payload(
    username: str,
    email: str,
    cpf: str = "11144477735",
) -> dict[str, str | None]:
    return {
        "full_name": "Pessoa de Teste",
        "username": username,
        "email": email,
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


def test_API_REG_01_requires_name_and_limits_name_and_email(
    registration_context: tuple[TestClient, str],
) -> None:
    client, prefix = registration_context
    payload = _valid_payload(f"{prefix}user", f"{prefix}user@example.com")
    del payload["full_name"]

    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "full_name" in response.json()["error"]["fields"]

    for field, value in (("full_name", "x" * 121), ("email", f"{'x' * 245}@example.com")):
        invalid = _valid_payload(f"{prefix}user", f"{prefix}user@example.com")
        invalid[field] = value
        invalid_response = client.post("/api/auth/register", json=invalid)
        assert invalid_response.status_code == 422
        assert field in invalid_response.json()["error"]["fields"]

    for field, value in (("email", "email-invalido"), ("username", "NomeInvalido")):
        invalid = _valid_payload(f"{prefix}user", f"{prefix}user@example.com")
        invalid[field] = value
        invalid_response = client.post("/api/auth/register", json=invalid)
        assert invalid_response.status_code == 422
        assert field in invalid_response.json()["error"]["fields"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("street", "R" * 101),
        ("number", "1" * 11),
        ("complement", "C" * 61),
        ("neighborhood", "B" * 101),
        ("city", "C" * 101),
        ("cep", "96200-000"),
        ("state", "XX"),
    ],
)
def test_API_REG_02_rejects_invalid_address_fields(
    registration_context: tuple[TestClient, str], field: str, value: str
) -> None:
    client, prefix = registration_context
    payload = _valid_payload(f"{prefix}user", f"{prefix}user@example.com")
    payload[field] = value

    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 422
    assert field in response.json()["error"]["fields"]


@pytest.mark.parametrize("duplicate_field", ["username", "email", "cpf"])
def test_API_REG_03_reports_each_duplicate_field(
    registration_context: tuple[TestClient, str], duplicate_field: str
) -> None:
    client, prefix = registration_context
    first = _valid_payload(f"{prefix}first", f"{prefix}first@example.com")
    second = _valid_payload(f"{prefix}second", f"{prefix}second@example.com", cpf="12345678909")
    assert client.post("/api/auth/register", json=first).status_code == 201
    second[duplicate_field] = first[duplicate_field]

    response = client.post("/api/auth/register", json=second)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FIELD_IN_USE"
    assert response.json()["error"]["fields"] == {duplicate_field: "Este campo já está cadastrado."}


def test_API_REG_03_email_and_username_uniqueness_ignore_case(
    registration_context: tuple[TestClient, str],
) -> None:
    client, prefix = registration_context
    first = _valid_payload(f"{prefix}first", f"{prefix}first@example.com")
    assert client.post("/api/auth/register", json=first).status_code == 201

    for field in ("username", "email"):
        second = _valid_payload(
            f"{prefix}second{field[0]}", f"{prefix}second{field[0]}@example.com", "24681357928"
        )
        second[field] = str(first[field]).upper() if field == "email" else first[field]
        response = client.post("/api/auth/register", json=second)
        assert response.status_code == 409
        assert field in response.json()["error"]["fields"]


def test_API_REG_04_returns_only_public_fields_and_stores_argon2id_hash(
    registration_context: tuple[TestClient, str], caplog: pytest.LogCaptureFixture
) -> None:
    client, prefix = registration_context
    payload = _valid_payload(f"{prefix}user", f"{prefix}user@example.com")
    password = str(payload["password"])

    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 201
    result = response.json()
    assert set(result) == {"id", "username", "created_at"}
    assert password not in response.text
    assert "password_hash" not in response.text
    assert "email" not in result
    assert "full_name" not in result
    assert password not in caplog.text

    with Session(get_engine()) as session:
        user = session.query(User).filter_by(username=payload["username"]).one()
        assert user.password_hash.startswith("$argon2id$")
        assert PasswordHasher().verify(user.password_hash, password)
        assert user.password_hash != password
        assert user.cpf == "11144477735"


def test_API_REG_04_validation_error_does_not_echo_short_password(
    registration_context: tuple[TestClient, str],
) -> None:
    client, prefix = registration_context
    payload = _valid_payload(f"{prefix}user", f"{prefix}user@example.com")
    secret_sentinel = "S3c!"
    payload["password"] = secret_sentinel

    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 422
    assert secret_sentinel not in response.text
    assert response.json()["error"]["fields"]["password"]


def test_API_REG_04_invalid_password_cpf_and_phone_report_their_fields(
    registration_context: tuple[TestClient, str],
) -> None:
    client, prefix = registration_context
    for field, value in (
        ("password", "senhafraca"),
        ("cpf", "11111111111"),
        ("phone", "+55 51 99999-0000"),
    ):
        payload = _valid_payload(f"{prefix}{field[0]}", f"{prefix}{field}@example.com")
        payload[field] = value
        response = client.post("/api/auth/register", json=payload)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert field in response.json()["error"]["fields"]


def test_UT_REG_04_phone_accepts_mask_and_stores_only_digits(
    registration_context: tuple[TestClient, str],
) -> None:
    client, prefix = registration_context
    payload = _valid_payload(f"{prefix}phone", f"{prefix}phone@example.com")
    payload["phone"] = "(51) 99999-0000"

    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 201
    with Session(get_engine()) as session:
        user = session.query(User).filter_by(username=payload["username"]).one()
        assert user.phone == "51999990000"

import os
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.main import app
from app.migrations import upgrade_database

EXPECTED_EXTENSIONS = {"citext", "pg_trgm", "unaccent", "btree_gist"}
DATABASE_URL = os.environ["DATABASE_URL"]


def _alembic_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


def _database_state() -> tuple[set[str], bool]:
    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as connection:
            extensions = set(connection.scalars(text("SELECT extname FROM pg_extension")))
            wrapper_exists = connection.scalar(
                text("SELECT to_regprocedure('public.immutable_unaccent(text)') IS NOT NULL")
            )
        return extensions, bool(wrapper_exists)
    finally:
        engine.dispose()


def test_initial_migration_installs_extensions_and_wrapper() -> None:
    command.downgrade(_alembic_config(), "base")
    command.upgrade(_alembic_config(), "20261022_0001")

    extensions, wrapper_exists = _database_state()

    assert EXPECTED_EXTENSIONS <= extensions
    assert wrapper_exists


def test_h001_1_users_migration_downgrade_and_upgrade() -> None:
    command.downgrade(_alembic_config(), "base")
    command.upgrade(_alembic_config(), "head")
    command.downgrade(_alembic_config(), "20261022_0001")
    _, wrapper_exists = _database_state()
    assert wrapper_exists
    engine = create_engine(DATABASE_URL)
    try:
        assert "users" not in inspect(engine).get_table_names()
    finally:
        engine.dispose()

    upgrade_database()
    _, wrapper_exists = _database_state()
    assert wrapper_exists
    engine = create_engine(DATABASE_URL)
    try:
        assert "users" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_h001_1_users_constraints_reject_duplicate_identifiers_and_invalid_values() -> None:
    upgrade_database()
    engine = create_engine(DATABASE_URL)
    valid_user = {
        "full_name": "Pessoa Ficticia",
        "username": "pessoa_ficticia",
        "email": "ficticio@example.invalid",
        "cpf": "00000000000",
        "phone": "00000000000",
        "password_hash": "$argon2id$fake-test-hash",
        "cep": "00000000",
        "street": "Rua Ficticia",
        "number": "0",
        "complement": None,
        "neighborhood": "Bairro Ficticio",
        "city": "Cidade Ficticia",
        "state": "RS",
    }
    columns = ", ".join(valid_user)
    values = ", ".join(f":{column}" for column in valid_user)
    insert_user = text(f"INSERT INTO users ({columns}) VALUES ({values})")

    try:
        with engine.begin() as connection:
            connection.execute(insert_user, valid_user)
            assert (
                connection.scalar(
                    text("SELECT token_version FROM users WHERE username = :username"),
                    {"username": valid_user["username"]},
                )
                == 0
            )

            for index, field in enumerate(("username", "email", "cpf"), start=1):
                with pytest.raises(IntegrityError), connection.begin_nested():
                    duplicate = valid_user | {
                        "username": f"duplicado_{index}",
                        "email": f"duplicado{index}@example.invalid",
                        "cpf": f"1234567890{index}",
                        "phone": f"1111111111{index}",
                    }
                    duplicate[field] = valid_user[field]
                    if field == "email":
                        duplicate[field] = valid_user[field].upper()
                    connection.execute(insert_user, duplicate)

            for field, invalid_value in (
                ("username", "_invalido"),
                ("username", "ab"),
                ("cpf", "123"),
                ("phone", "abc"),
                ("cep", "123"),
                ("state", "R1"),
                ("email", "x" * 255),
                ("token_version", -1),
            ):
                with pytest.raises(IntegrityError), connection.begin_nested():
                    invalid = valid_user | {"phone": "22222222222"}
                    invalid[field] = invalid_value
                    if field == "token_version":
                        insert_with_token_version = text(
                            f"INSERT INTO users ({columns}, token_version) "
                            f"VALUES ({values}, :token_version)"
                        )
                        connection.execute(insert_with_token_version, invalid)
                    else:
                        connection.execute(insert_user, invalid)
    finally:
        engine.dispose()


def test_fastapi_startup_migrates_before_serving() -> None:
    command.downgrade(_alembic_config(), "20261022_0001")

    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    _, wrapper_exists = _database_state()
    assert wrapper_exists

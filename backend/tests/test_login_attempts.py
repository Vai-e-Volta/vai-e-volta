"""H002-1: login_attempts table (RN-14)."""

import hashlib
import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.migrations import upgrade_database

DATABASE_URL = os.environ["DATABASE_URL"]


def _alembic_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


def _identifier_hash(identifier: str) -> str:
    return hashlib.sha256(identifier.strip().lower().encode()).hexdigest()


def test_h002_1_migration_downgrade_and_upgrade() -> None:
    upgrade_database()
    command.downgrade(_alembic_config(), "20261109_0001")
    engine = create_engine(DATABASE_URL)
    try:
        assert "login_attempts" not in inspect(engine).get_table_names()
        upgrade_database()
        inspector = inspect(engine)
        assert "login_attempts" in inspector.get_table_names()
        indexes = {
            index["name"]: index["column_names"]
            for index in inspector.get_indexes("login_attempts")
        }
        assert indexes["ix_login_attempts_identifier_hash_attempted_at"] == [
            "identifier_hash",
            "attempted_at",
        ]
    finally:
        engine.dispose()


def test_h002_1_stores_hash_and_defaults_attempted_at() -> None:
    upgrade_database()
    engine = create_engine(DATABASE_URL)
    digest = _identifier_hash("Pessoa@Example.invalid")
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(
                    text(
                        "INSERT INTO login_attempts (identifier_hash, success) VALUES (:h, false)"
                    ),
                    {"h": digest},
                )
                row = connection.execute(
                    text(
                        "SELECT identifier_hash, success, attempted_at IS NOT NULL "
                        "FROM login_attempts WHERE identifier_hash = :h"
                    ),
                    {"h": digest},
                ).one()
                assert row == (digest, False, True)

                for invalid in ("pessoa@example.invalid", digest.upper(), digest[:-1]):
                    with pytest.raises(IntegrityError), connection.begin_nested():
                        connection.execute(
                            text(
                                "INSERT INTO login_attempts (identifier_hash, success) "
                                "VALUES (:h, true)"
                            ),
                            {"h": invalid},
                        )
                with pytest.raises(IntegrityError), connection.begin_nested():
                    connection.execute(
                        text("INSERT INTO login_attempts (identifier_hash) VALUES (:h)"),
                        {"h": digest},
                    )
            finally:
                transaction.rollback()
    finally:
        engine.dispose()

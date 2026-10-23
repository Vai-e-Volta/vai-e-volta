import os
from pathlib import Path

from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

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
    upgrade_database()

    extensions, wrapper_exists = _database_state()

    assert EXPECTED_EXTENSIONS <= extensions
    assert wrapper_exists


def test_migration_downgrade_and_upgrade() -> None:
    command.downgrade(_alembic_config(), "-1")
    _, wrapper_exists = _database_state()
    assert not wrapper_exists

    upgrade_database()
    _, wrapper_exists = _database_state()
    assert wrapper_exists


def test_fastapi_startup_migrates_before_serving() -> None:
    command.downgrade(_alembic_config(), "-1")

    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    _, wrapper_exists = _database_state()
    assert wrapper_exists

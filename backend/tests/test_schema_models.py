"""The SQLAlchemy models must describe exactly the schema created by the migrations."""

import os

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

import app.models  # noqa: F401  (registers every model in the metadata)
from app.db import Base
from app.migrations import upgrade_database


def test_models_match_migrated_schema() -> None:
    upgrade_database()
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            differences = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    assert differences == []

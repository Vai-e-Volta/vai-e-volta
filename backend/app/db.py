import os
from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models used by Alembic autogeneration."""


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create the database engine on first use, after runtime configuration is loaded."""
    return create_engine(os.environ["DATABASE_URL"], hide_parameters=True, pool_pre_ping=True)


def get_db() -> Generator[Session, None, None]:
    """Yield one synchronous database session per request."""
    session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    with session_factory() as session:
        yield session

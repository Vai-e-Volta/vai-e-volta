from pathlib import Path

from alembic.config import Config

from alembic import command


def upgrade_database() -> None:
    """Apply all pending migrations before the API starts accepting requests."""
    config_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    config = Config(str(config_path))
    command.upgrade(config, "head")

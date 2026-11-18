"""Add trigram index for normalized listing title searches.

Revision ID: 20261118_0006
Revises: 20261117_0005
Create Date: 2026-11-18
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20261118_0006"
down_revision: str | None = "20261117_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_listings_title_search_trgm ON listings "
        "USING gin (immutable_unaccent(lower(title::text)) gin_trgm_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_listings_title_search_trgm", table_name="listings")

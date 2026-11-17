"""Create the favorites table (RN-31).

Revision ID: 20261117_0003
Revises: 20261117_0002
Create Date: 2026-11-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261117_0003"
down_revision: str | None = "20261117_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # No ON DELETE CASCADE: listings are deleted logically and the favorite of an
    # unavailable listing is kept (it is only hidden from the list, RN-31).
    op.create_table(
        "favorites",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("listing_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_favorites_user_id_users"),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["listings.id"], name="fk_favorites_listing_id_listings"
        ),
        sa.PrimaryKeyConstraint("user_id", "listing_id", name="pk_favorites"),
    )
    op.create_index("ix_favorites_listing_id", "favorites", ["listing_id"])


def downgrade() -> None:
    op.drop_index("ix_favorites_listing_id", table_name="favorites")
    op.drop_table("favorites")

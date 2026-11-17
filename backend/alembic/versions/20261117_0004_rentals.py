"""Create the rentals table (proposals and rentals).

Revision ID: 20261117_0004
Revises: 20261117_0003
Create Date: 2026-11-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261117_0004"
down_revision: str | None = "20261117_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rentals",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("listing_id", sa.BigInteger(), nullable=False),
        sa.Column("renter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("daily_price_snapshot", sa.Numeric(precision=7, scale=2), nullable=False),
        sa.Column("estimated_total", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("listing_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("return_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("returned_on", sa.Date(), nullable=True),
        sa.Column("original_end_date", sa.Date(), nullable=True),
        sa.CheckConstraint("start_date <= end_date", name="ck_rentals_period_order"),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'expired', 'canceled', 'completed')",
            name="ck_rentals_status",
        ),
        sa.CheckConstraint(
            "daily_price_snapshot > 0", name="ck_rentals_daily_price_snapshot_positive"
        ),
        sa.CheckConstraint("estimated_total > 0", name="ck_rentals_estimated_total_positive"),
        sa.CheckConstraint("expires_at > created_at", name="ck_rentals_expires_after_created"),
        sa.CheckConstraint(
            "jsonb_typeof(listing_snapshot) = 'object'",
            name="ck_rentals_listing_snapshot_object",
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["listings.id"], name="fk_rentals_listing_id_listings"
        ),
        sa.ForeignKeyConstraint(["renter_id"], ["users.id"], name="fk_rentals_renter_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_rentals"),
    )
    op.create_index("ix_rentals_listing_id_status", "rentals", ["listing_id", "status"])
    op.create_index("ix_rentals_renter_id_status", "rentals", ["renter_id", "status"])

    # RN-42: accepted or completed rentals of the same listing never overlap. Both ends are
    # inclusive, so a return on day 14 frees a new pickup only on day 15. Pending proposals
    # are not part of the constraint (RN-44). Requires btree_gist (first migration).
    op.execute(
        """
        ALTER TABLE rentals ADD CONSTRAINT rentals_no_overlap
          EXCLUDE USING gist (
            listing_id WITH =,
            daterange(start_date, end_date, '[]') WITH &&
          ) WHERE (status IN ('accepted', 'completed'))
        """
    )


def downgrade() -> None:
    op.drop_index("ix_rentals_renter_id_status", table_name="rentals")
    op.drop_index("ix_rentals_listing_id_status", table_name="rentals")
    op.drop_table("rentals")

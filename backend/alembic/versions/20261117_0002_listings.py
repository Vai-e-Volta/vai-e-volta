"""Create categories, listings, listing_photos, tags and listing_tags.

Revision ID: 20261117_0002
Revises: 20261117_0001
Create Date: 2026-11-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261117_0002"
down_revision: str | None = "20261117_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# RN-58: fixed categories, in the order shown to the user.
CATEGORIES = (
    "Ferramentas",
    "Eletrônicos",
    "Esportes e lazer",
    "Casa e jardim",
    "Equipamentos",
    "Veículos",
    "Livros",
    "Festas e jogos",
)


def upgrade() -> None:
    categories = op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.UniqueConstraint("name", name="uq_categories_name"),
    )
    op.bulk_insert(categories, [{"name": name} for name in CATEGORIES])

    op.create_table(
        "listings",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("daily_price", sa.Numeric(precision=7, scale=2), nullable=False),
        sa.Column("max_days", sa.Integer(), nullable=False),
        sa.Column("available_from", sa.Date(), nullable=False),
        sa.Column("available_until", sa.Date(), nullable=False),
        sa.Column("pickup_cep", sa.Text(), nullable=False),
        sa.Column("pickup_street", sa.Text(), nullable=False),
        sa.Column("pickup_number", sa.Text(), nullable=False),
        sa.Column("pickup_complement", sa.Text(), nullable=True),
        sa.Column("pickup_neighborhood", sa.Text(), nullable=False),
        sa.Column("pickup_city", sa.Text(), nullable=False),
        sa.Column("pickup_state", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("char_length(title) >= 1", name="ck_listings_title_length"),
        sa.CheckConstraint(
            "daily_price BETWEEN 1.00 AND 5000.00", name="ck_listings_daily_price_range"
        ),
        sa.CheckConstraint("max_days >= 1", name="ck_listings_max_days_positive"),
        sa.CheckConstraint(
            "available_from <= available_until", name="ck_listings_availability_order"
        ),
        sa.CheckConstraint(
            "max_days <= available_until - available_from + 1",
            name="ck_listings_max_days_within_window",
        ),
        sa.CheckConstraint("pickup_cep ~ '^[0-9]{8}$'", name="ck_listings_pickup_cep_format"),
        sa.CheckConstraint("pickup_state ~ '^[A-Z]{2}$'", name="ck_listings_pickup_state_format"),
        sa.CheckConstraint("status IN ('active', 'paused', 'deleted')", name="ck_listings_status"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_listings_owner_id_users"),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], name="fk_listings_category_id_categories"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_listings"),
    )
    op.create_index("ix_listings_owner_id", "listings", ["owner_id"])
    op.create_index("ix_listings_status_available_until", "listings", ["status", "available_until"])
    op.create_index("ix_listings_created_at_id", "listings", ["created_at", "id"])
    op.create_index("ix_listings_daily_price_id", "listings", ["daily_price", "id"])

    op.create_table(
        "listing_photos",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("listing_id", sa.BigInteger(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.CheckConstraint("position BETWEEN 1 AND 5", name="ck_listing_photos_position_range"),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listings.id"],
            name="fk_listing_photos_listing_id_listings",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_listing_photos"),
        sa.UniqueConstraint("listing_id", "position", name="uq_listing_photos_listing_position"),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=30), nullable=False),
        sa.Column("normalized_name", sa.String(length=30), nullable=False),
        sa.CheckConstraint("char_length(name) >= 1", name="ck_tags_name_length"),
        sa.CheckConstraint(
            "normalized_name = lower(public.immutable_unaccent(normalized_name))",
            name="ck_tags_normalized_name_format",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tags"),
        sa.UniqueConstraint("normalized_name", name="uq_tags_normalized_name"),
    )

    op.create_table(
        "listing_tags",
        sa.Column("listing_id", sa.BigInteger(), nullable=False),
        sa.Column("tag_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listings.id"],
            name="fk_listing_tags_listing_id_listings",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], name="fk_listing_tags_tag_id_tags"),
        sa.PrimaryKeyConstraint("listing_id", "tag_id", name="pk_listing_tags"),
    )
    op.create_index("ix_listing_tags_tag_id", "listing_tags", ["tag_id"])


def downgrade() -> None:
    op.drop_index("ix_listing_tags_tag_id", table_name="listing_tags")
    op.drop_table("listing_tags")
    op.drop_table("tags")
    op.drop_table("listing_photos")
    op.drop_index("ix_listings_daily_price_id", table_name="listings")
    op.drop_index("ix_listings_created_at_id", table_name="listings")
    op.drop_index("ix_listings_status_available_until", table_name="listings")
    op.drop_index("ix_listings_owner_id", table_name="listings")
    op.drop_table("listings")
    op.drop_table("categories")

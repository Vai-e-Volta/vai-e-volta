from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

LISTING_STATUSES = ("active", "paused", "deleted")


class Category(Base):
    """Fixed categories (RN-58); rows are inserted by the migration."""

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", name="uq_categories_name"),)

    id: Mapped[int] = mapped_column(Integer, Identity(always=False), primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        CheckConstraint("char_length(title) >= 1", name="ck_listings_title_length"),
        CheckConstraint(
            "daily_price BETWEEN 1.00 AND 5000.00", name="ck_listings_daily_price_range"
        ),
        CheckConstraint("max_days >= 1", name="ck_listings_max_days_positive"),
        CheckConstraint("available_from <= available_until", name="ck_listings_availability_order"),
        CheckConstraint(
            "max_days <= available_until - available_from + 1",
            name="ck_listings_max_days_within_window",
        ),
        CheckConstraint("pickup_cep ~ '^[0-9]{8}$'", name="ck_listings_pickup_cep_format"),
        CheckConstraint("pickup_state ~ '^[A-Z]{2}$'", name="ck_listings_pickup_state_format"),
        CheckConstraint("status IN ('active', 'paused', 'deleted')", name="ck_listings_status"),
        Index("ix_listings_owner_id", "owner_id"),
        Index("ix_listings_status_available_until", "status", "available_until"),
        Index("ix_listings_created_at_id", "created_at", "id"),
        Index("ix_listings_daily_price_id", "daily_price", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_listings_owner_id_users"),
        nullable=False,
    )
    category_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("categories.id", name="fk_listings_category_id_categories"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    daily_price: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    max_days: Mapped[int] = mapped_column(Integer, nullable=False)
    available_from: Mapped[date] = mapped_column(Date, nullable=False)
    available_until: Mapped[date] = mapped_column(Date, nullable=False)

    pickup_cep: Mapped[str] = mapped_column(Text, nullable=False)
    pickup_street: Mapped[str] = mapped_column(Text, nullable=False)
    pickup_number: Mapped[str] = mapped_column(Text, nullable=False)
    pickup_complement: Mapped[str | None] = mapped_column(Text)
    pickup_neighborhood: Mapped[str] = mapped_column(Text, nullable=False)
    pickup_city: Mapped[str] = mapped_column(Text, nullable=False)
    pickup_state: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ListingPhoto(Base):
    """Listing photo; position 1 is the cover (RN-56). The API checks the 1 to 5 count."""

    __tablename__ = "listing_photos"
    __table_args__ = (
        CheckConstraint("position BETWEEN 1 AND 5", name="ck_listing_photos_position_range"),
        UniqueConstraint("listing_id", "position", name="uq_listing_photos_listing_position"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("listings.id", name="fk_listing_photos_listing_id_listings", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)


class Tag(Base):
    """Tag shared between listings; normalized_name is lowercase and without accents (RN-57)."""

    __tablename__ = "tags"
    __table_args__ = (
        CheckConstraint("char_length(name) >= 1", name="ck_tags_name_length"),
        CheckConstraint(
            "normalized_name = lower(public.immutable_unaccent(normalized_name))",
            name="ck_tags_normalized_name_format",
        ),
        UniqueConstraint("normalized_name", name="uq_tags_normalized_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(30), nullable=False)


# Association table; the limit of 5 tags per listing is checked by the API.
listing_tags = Table(
    "listing_tags",
    Base.metadata,
    Column(
        "listing_id",
        BigInteger,
        ForeignKey("listings.id", name="fk_listing_tags_listing_id_listings", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "tag_id",
        BigInteger,
        ForeignKey("tags.id", name="fk_listing_tags_tag_id_tags"),
        primary_key=True,
    ),
    Index("ix_listing_tags_tag_id", "tag_id"),
)

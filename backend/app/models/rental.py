from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

RENTAL_STATUSES = ("pending", "accepted", "rejected", "expired", "canceled", "completed")


class Rental(Base):
    """Proposal and rental. The stored status is not the displayed situation (RN-65).

    The no-overlap EXCLUDE constraint (RN-42) is created by the migration with raw SQL.
    """

    __tablename__ = "rentals"
    __table_args__ = (
        CheckConstraint("start_date <= end_date", name="ck_rentals_period_order"),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'rejected', 'expired', 'canceled', 'completed')",
            name="ck_rentals_status",
        ),
        CheckConstraint(
            "daily_price_snapshot > 0", name="ck_rentals_daily_price_snapshot_positive"
        ),
        CheckConstraint("estimated_total > 0", name="ck_rentals_estimated_total_positive"),
        CheckConstraint("expires_at > created_at", name="ck_rentals_expires_after_created"),
        CheckConstraint(
            "jsonb_typeof(listing_snapshot) = 'object'",
            name="ck_rentals_listing_snapshot_object",
        ),
        Index("ix_rentals_listing_id_status", "listing_id", "status"),
        Index("ix_rentals_renter_id_status", "renter_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("listings.id", name="fk_rentals_listing_id_listings"),
        nullable=False,
    )
    renter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_rentals_renter_id_users"),
        nullable=False,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))
    daily_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    estimated_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    listing_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    return_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    returned_on: Mapped[date | None] = mapped_column(Date)
    original_end_date: Mapped[date | None] = mapped_column(Date)

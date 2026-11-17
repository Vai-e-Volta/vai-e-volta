from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Favorite(Base):
    """A user's favorite listing. Kept when the listing becomes unavailable (RN-31)."""

    __tablename__ = "favorites"
    __table_args__ = (Index("ix_favorites_listing_id", "listing_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_favorites_user_id_users"),
        primary_key=True,
    )
    listing_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("listings.id", name="fk_favorites_listing_id_listings"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

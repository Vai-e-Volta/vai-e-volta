from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Identity, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class LoginAttempt(Base):
    """One login attempt; the identifier is stored only as a SHA-256 hex digest (RN-14)."""

    __tablename__ = "login_attempts"
    __table_args__ = (
        CheckConstraint(
            "identifier_hash ~ '^[0-9a-f]{64}$'",
            name="ck_login_attempts_identifier_hash_sha256",
        ),
        Index("ix_login_attempts_identifier_hash_attempted_at", "identifier_hash", "attempted_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    identifier_hash: Mapped[str] = mapped_column(Text, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)

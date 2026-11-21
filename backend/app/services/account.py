from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Listing, Rental, User
from app.services.authentication import hash_password, password_is_valid, verify_current_password


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if not verify_current_password(user, current_password):
        raise ApiError(
            status_code=401, code="INVALID_CREDENTIALS", message="Senha atual incorreta."
        )
    if not password_is_valid(new_password):
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Revise os campos informados.",
            fields={"new_password": "Use de 8 a 128 caracteres, com maiúscula, número e símbolo."},
        )

    user.password_hash = hash_password(new_password)
    user.token_version += 1
    db.commit()
    db.refresh(user)


def delete_account(db: Session, user: User, password: str) -> None:
    if not verify_current_password(user, password):
        raise ApiError(
            status_code=401, code="INVALID_CREDENTIALS", message="Senha atual incorreta."
        )

    today = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    active_rental = db.scalar(
        select(Rental.id)
        .outerjoin(Listing, Listing.id == Rental.listing_id)
        .where(
            Rental.status == "accepted",
            Rental.end_date >= today,
            or_(Rental.renter_id == user.id, Listing.owner_id == user.id),
        )
        .limit(1)
    )
    if active_rental is not None:
        raise ApiError(
            status_code=409,
            code="ACCOUNT_HAS_ACTIVE_RENTAL",
            message="Conclua ou cancele seus aluguéis aceitos antes de excluir a conta.",
        )

    now = datetime.now(UTC)
    retention_days = int(os.getenv("ACCOUNT_RETENTION_DAYS", "365"))
    # All state changes occur in this transaction so the user never reaches a partial deletion.
    db.execute(
        update(Rental)
        .where(
            Rental.status == "pending",
            or_(
                Rental.renter_id == user.id,
                Rental.listing_id.in_(select(Listing.id).where(Listing.owner_id == user.id)),
            ),
        )
        .values(status="canceled", canceled_at=now)
    )
    db.execute(
        update(Listing)
        .where(Listing.owner_id == user.id, Listing.status == "active")
        .values(status="paused", updated_at=now)
    )
    user.deleted_at = now
    user.purge_after = now + timedelta(days=retention_days)
    user.token_version += 1
    db.commit()

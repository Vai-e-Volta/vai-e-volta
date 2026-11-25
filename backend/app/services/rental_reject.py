"""Owner refuses a pending proposal (F-39; RN-63).

The refusal needs no reason. The notice to the renter (reason `owner`) is H023-1.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Listing, Rental, User
from app.services.proposal_expiry import proposal_has_expired


def reject_proposal(db: Session, user: User, rental_id: int) -> None:
    rental = db.get(Rental, rental_id)
    if rental is None:
        raise ApiError(status_code=404, code="RENTAL_NOT_FOUND", message="Aluguel não encontrado.")

    # RN-63: only the owner decides. Checked before taking the lock.
    owner_id = db.scalar(select(Listing.owner_id).where(Listing.id == rental.listing_id))
    if owner_id != user.id:
        raise ApiError(
            status_code=403, code="FORBIDDEN", message="Somente o dono pode recusar a proposta."
        )

    # A concurrent acceptance, cancellation or expiration must finish before the state is read.
    rental = db.scalars(
        select(Rental)
        .where(Rental.id == rental_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()

    if rental.status != "pending":
        raise ApiError(
            status_code=409,
            code="INVALID_STATE",
            message="Somente propostas aguardando resposta podem ser recusadas.",
        )

    now = datetime.now(UTC)
    if proposal_has_expired(rental.expires_at, rental.start_date, now):
        # Same rule as the acceptance (RN-47, RN-48): an overdue proposal is expired, not refused.
        rental.status = "expired"
        db.commit()
        raise ApiError(
            status_code=409,
            code="PROPOSAL_EXPIRED",
            message="A proposta expirou e não pode mais ser recusada.",
        )

    rental.status = "rejected"
    rental.responded_at = now
    db.commit()

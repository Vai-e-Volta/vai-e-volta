"""Owner accepts a pending proposal (F-39; RN-42, RN-46, RN-48, RN-63).

Validation order follows the technical document: owner, then state and expiry, then the
transaction that accepts the proposal and settles the overlapping ones. The database has the last
word on overlaps (RN-42): if its exclusion constraint fires, the whole transaction is undone and the
answer is 409 RENTAL_OVERLAP. The notices to the renters (H023-1) are not part of this step.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Listing, Rental, User
from app.services.proposal_expiry import proposal_has_expired

logger = logging.getLogger(__name__)

# PostgreSQL SQLSTATE for a violated exclusion constraint (rentals_no_overlap, RN-42).
EXCLUSION_VIOLATION = "23P01"


def accept_proposal(db: Session, user: User, rental_id: int) -> None:
    rental = db.get(Rental, rental_id)
    if rental is None:
        raise ApiError(status_code=404, code="RENTAL_NOT_FOUND", message="Aluguel não encontrado.")

    # RN-63: only the owner decides. Checked before taking any lock, so a stranger cannot hold one.
    owner_id = db.scalar(select(Listing.owner_id).where(Listing.id == rental.listing_id))
    if owner_id != user.id:
        raise ApiError(
            status_code=403, code="FORBIDDEN", message="Somente o dono pode aceitar a proposta."
        )

    # Same lock order as pausing a listing (listing first, then its rentals), so the two cannot
    # deadlock. The proposal is reloaded under the lock to see what a concurrent request did.
    db.scalar(select(Listing.id).where(Listing.id == rental.listing_id).with_for_update())
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
            message="Somente propostas aguardando resposta podem ser aceitas.",
        )

    now = datetime.now(UTC)
    if proposal_has_expired(rental.expires_at, rental.start_date, now):
        # RN-47 (deadline reached) and RN-48 (start date already passed): the expired state is
        # saved before the error is raised, so the answer does not roll it back.
        rental.status = "expired"
        db.commit()
        raise ApiError(
            status_code=409,
            code="PROPOSAL_EXPIRED",
            message="A proposta expirou e não pode mais ser aceita.",
        )

    listing_id = rental.listing_id
    try:
        rental.status = "accepted"
        rental.responded_at = now

        # RN-46, same transaction: overlapping pending proposals of this listing are settled.
        # This query also flushes the acceptance, which is where the constraint can fire.
        overlapping = db.scalars(
            select(Rental)
            .where(
                Rental.listing_id == listing_id,
                Rental.id != rental.id,
                Rental.status == "pending",
                Rental.start_date <= rental.end_date,
                Rental.end_date >= rental.start_date,
            )
            .order_by(Rental.id)
            .with_for_update()
        )
        for other in overlapping:
            if proposal_has_expired(other.expires_at, other.start_date, now):
                # Already expired (RN-47) even if the worker has not run: not a refusal.
                other.status = "expired"
            else:
                other.status = "rejected"
                other.responded_at = now
        db.commit()
    except IntegrityError as error:
        # Nothing of this acceptance survives: not the proposal, not the refusals.
        db.rollback()
        if getattr(error.orig, "sqlstate", None) != EXCLUSION_VIOLATION:
            raise
        logger.warning(
            "Rental booking conflict on accept",
            extra={"rental_id": rental_id, "listing_id": listing_id},
        )
        raise ApiError(
            status_code=409,
            code="RENTAL_OVERLAP",
            message="Este período já está reservado por outro aluguel aceito.",
        ) from error

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Listing, Notification, Rental, User
from app.services.rental_situation import today_br


def change_listing_status(db: Session, user: User, listing_id: int, action: str) -> None:
    """Serialize owner actions, rental checks and proposal notifications."""
    listing = db.scalar(select(Listing).where(Listing.id == listing_id).with_for_update())
    if listing is None:
        raise ApiError(status_code=404, code="LISTING_NOT_FOUND", message="Anúncio não encontrado.")
    if listing.owner_id != user.id:
        raise ApiError(
            status_code=403, code="FORBIDDEN", message="Somente o dono pode alterar o anúncio."
        )
    if listing.status == "deleted":
        if action == "delete":
            return
        raise ApiError(status_code=409, code="INVALID_STATE", message="Anúncio indisponível.")

    if action == "resume":
        if listing.available_until < today_br():
            raise ApiError(
                status_code=409,
                code="INVALID_STATE",
                message="Atualize a janela de disponibilidade antes de reativar.",
            )
        listing.status = "active"
        listing.updated_at = datetime.now(UTC)
        db.commit()
        return

    rentals = list(
        db.scalars(
            select(Rental)
            .where(Rental.listing_id == listing.id, Rental.status.in_(("pending", "accepted")))
            .order_by(Rental.id)
            .with_for_update()
        )
    )
    if any(rental.status == "accepted" and rental.end_date >= today_br() for rental in rentals):
        raise ApiError(
            status_code=409,
            code="LISTING_HAS_ACTIVE_RENTAL",
            message="O anúncio possui aluguel aceito em curso ou futuro.",
        )
    now = datetime.now(UTC)
    for rental in rentals:
        if rental.status != "pending":
            continue
        rental.status = "rejected"
        rental.responded_at = now
        db.add(
            Notification(
                user_id=rental.renter_id,
                type="proposal_rejected",
                rental_id=rental.id,
                payload={
                    "listing_id": listing.id,
                    "listing_title": rental.listing_snapshot.get("title", listing.title),
                    "reason": "listing_unavailable",
                },
            )
        )
    listing.status = "paused" if action == "pause" else "deleted"
    listing.updated_at = now
    db.commit()

"""Owner marks a rental as returned (F-40; RN-64).

Only the plain completion lives here. The early return, which shortens the period and recalculates
the estimated value, is H021-2, and the notice to the renter is H023-2.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Listing, Rental, User
from app.services.rental_situation import today_br


def mark_rental_returned(db: Session, user: User, rental_id: int) -> None:
    rental = db.get(Rental, rental_id)
    if rental is None:
        raise ApiError(status_code=404, code="RENTAL_NOT_FOUND", message="Aluguel não encontrado.")

    # RN-64: only the owner marks the return. Checked before taking the lock.
    owner_id = db.scalar(select(Listing.owner_id).where(Listing.id == rental.listing_id))
    if owner_id != user.id:
        raise ApiError(
            status_code=403,
            code="FORBIDDEN",
            message="Somente o dono pode marcar o aluguel como devolvido.",
        )

    # A concurrent cancellation must finish before the state is inspected.
    rental = db.scalars(
        select(Rental)
        .where(Rental.id == rental_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()

    today = today_br(datetime.now(UTC))
    if rental.status != "accepted" or rental.start_date > today:
        raise ApiError(
            status_code=409,
            code="INVALID_STATE",
            message="Só um aluguel aceito e já iniciado pode ser marcado como devolvido.",
        )

    # An overdue rental can be completed like any other: lateness has no fine and no block.
    rental.status = "completed"
    rental.returned_on = today
    db.commit()

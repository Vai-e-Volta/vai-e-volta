"""Expiration of pending proposals (RN-47).

A pending proposal expires when the owner does not answer within ``PROPOSAL_TTL_HOURS``
(``expires_at`` reached) or when its start date arrives without an answer. The rule here is
the same one used by ``rental_situation`` to show "Expirado", so the worker and the reads agree.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ColumnElement, and_, or_, update
from sqlalchemy.orm import Session

from app.models import Rental
from app.services.rental_situation import today_br


def pending_is_expired(now: datetime) -> ColumnElement[bool]:
    """SQL condition: the row is ``pending`` but already past its deadline at ``now``."""
    return and_(
        Rental.status == "pending",
        or_(Rental.expires_at <= now, Rental.start_date < today_br(now)),
    )


def expire_pending_proposals(session: Session, now: datetime) -> list[int]:
    """Move every overdue ``pending`` proposal to ``expired``; return the ids changed.

    Idempotent: a second run at the same instant finds nothing left to change. The ids are
    returned so the renter notice (H023-2) can be sent in the same transaction.
    """
    result = session.execute(
        update(Rental)
        .where(pending_is_expired(now))
        .values(status="expired")
        .returning(Rental.id)
        .execution_options(synchronize_session=False)
    )
    return sorted(result.scalars().all())

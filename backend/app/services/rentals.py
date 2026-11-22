from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Listing, ListingPhoto, Rental, User
from app.services.proposal_expiry import effective_status, pending_is_expired
from app.services.rental_situation import rental_situation


def _encode_cursor(created_at: datetime, rental_id: int) -> str:
    payload = json.dumps(
        {"created_at": created_at.astimezone(UTC).isoformat(), "id": rental_id},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        payload = json.loads(
            base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
        )
        created_at = datetime.fromisoformat(payload["created_at"])
        rental_id = payload["id"]
        if (
            created_at.tzinfo is None
            or isinstance(rental_id, bool)
            or not isinstance(rental_id, int)
            or rental_id < 1
        ):
            raise ValueError
        return created_at, rental_id
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise ApiError(
            status_code=400,
            code="INVALID_CURSOR",
            message="Cursor inválido.",
        ) from None


def list_rentals(
    db: Session,
    user: User,
    role: str,
    scope: str,
    limit: int,
    cursor: str | None,
) -> dict:
    now = datetime.now(UTC)
    stmt = select(Rental, Listing, User).join(Listing, Listing.id == Rental.listing_id)
    if role == "renter":
        stmt = stmt.join(User, User.id == Listing.owner_id).where(Rental.renter_id == user.id)
    else:
        stmt = stmt.join(User, User.id == Rental.renter_id).where(Listing.owner_id == user.id)

    # An overdue pending proposal already belongs to the history, even before the worker
    # moves it to expired (H018-3).
    active = or_(
        and_(Rental.status == "pending", not_(pending_is_expired(now))),
        Rental.status == "accepted",
    )
    stmt = stmt.where(active if scope == "active" else not_(active))
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.scalar(count_stmt) or 0

    if cursor:
        created_at, rental_id = _decode_cursor(cursor)
        stmt = stmt.where(
            or_(
                Rental.created_at < created_at,
                and_(Rental.created_at == created_at, Rental.id < rental_id),
            )
        )
    cover = (
        select(ListingPhoto.filename)
        .where(ListingPhoto.listing_id == Listing.id, ListingPhoto.position == 1)
        .correlate(Listing)
        .scalar_subquery()
    )
    rows = db.execute(
        stmt.add_columns(cover.label("cover_photo"))
        .order_by(Rental.created_at.desc(), Rental.id.desc())
        .limit(limit + 1)
    ).all()
    has_more = len(rows) > limit
    items = []
    for rental, listing, other_party, cover_photo in rows[:limit]:
        deleted = other_party.deleted_at is not None
        items.append(
            {
                "id": rental.id,
                "listing_id": listing.id,
                "title": rental.listing_snapshot.get("title", "Anúncio indisponível"),
                "cover_photo": cover_photo,
                "start_date": rental.start_date,
                "end_date": rental.end_date,
                "status": effective_status(
                    rental.status, rental.expires_at, rental.start_date, now
                ),
                "situation": rental_situation(
                    rental.status,
                    rental.start_date,
                    rental.end_date,
                    rental.expires_at,
                    now=now,
                ),
                "daily_price": rental.daily_price_snapshot,
                "estimated_total": rental.estimated_total,
                "created_at": rental.created_at,
                "other_party_name": "Usuário excluído" if deleted else other_party.full_name,
                "other_party_phone": (
                    None if deleted or rental.status != "accepted" else other_party.phone
                ),
            }
        )
    next_cursor = (
        _encode_cursor(items[-1]["created_at"], items[-1]["id"]) if has_more and items else None
    )
    return {"items": items, "next_cursor": next_cursor, "total": total}

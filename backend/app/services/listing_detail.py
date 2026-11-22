"""Listing page: detail and booked periods (F-28, F-29, F-31; RN-33, RN-34, RN-35)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Category, Listing, ListingPhoto, Rental, Tag, User, listing_tags


def _load_listing(db: Session, listing_id: int) -> tuple[Listing, User]:
    stmt = select(Listing, User).join(User, User.id == Listing.owner_id)
    row = db.execute(stmt.where(Listing.id == listing_id)).one_or_none()
    if row is None:
        raise ApiError(
            status_code=404,
            code="LISTING_NOT_FOUND",
            message="Anúncio não encontrado.",
        )
    return row[0], row[1]


def _is_unavailable_for(listing: Listing, owner: User, user: User) -> bool:
    """RN-34: paused, deleted or from a deleted account; the owner still sees it."""
    unavailable = listing.status != "active" or owner.deleted_at is not None
    return unavailable and listing.owner_id != user.id


def _text_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _renter_snapshot(db: Session, user: User, listing_id: int) -> dict[str, Any] | None:
    """Snapshot of the renter's latest accepted rental of this listing, if any (RN-35)."""
    return db.scalar(
        select(Rental.listing_snapshot)
        .where(
            Rental.listing_id == listing_id,
            Rental.renter_id == user.id,
            Rental.status == "accepted",
        )
        .order_by(Rental.start_date.desc(), Rental.id.desc())
        .limit(1)
    )


def get_listing_detail(db: Session, user: User, listing_id: int) -> dict[str, Any]:
    listing, owner = _load_listing(db, listing_id)
    if _is_unavailable_for(listing, owner, user):
        return {"id": listing.id, "unavailable": True}

    is_owner = listing.owner_id == user.id
    category = db.scalar(select(Category.name).where(Category.id == listing.category_id))
    photos = db.execute(
        select(ListingPhoto.id, ListingPhoto.filename)
        .where(ListingPhoto.listing_id == listing.id)
        .order_by(ListingPhoto.position)
    ).all()
    tags = db.scalars(
        select(Tag.name)
        .join(listing_tags, listing_tags.c.tag_id == Tag.id)
        .where(listing_tags.c.listing_id == listing.id)
        .order_by(Tag.name)
    ).all()

    # RN-35: number and complement only for the renter of an accepted rental, read from the
    # copy kept in that rental. The CEP is never returned.
    number = complement = None
    snapshot = None if is_owner else _renter_snapshot(db, user, listing.id)
    if snapshot is not None:
        number = _text_or_none(snapshot.get("pickup_number"))
        complement = _text_or_none(snapshot.get("pickup_complement"))

    return {
        "id": listing.id,
        "unavailable": False,
        "status": listing.status,
        "title": listing.title,
        "description": listing.description,
        "daily_price": listing.daily_price,
        "max_days": listing.max_days,
        "available_from": listing.available_from,
        "available_until": listing.available_until,
        "category": category,
        "tags": list(tags),
        "photos": [{"id": photo_id, "filename": name} for photo_id, name in photos],
        "owner_username": owner.username,
        "is_owner": is_owner,
        "pickup_street": listing.pickup_street,
        "pickup_neighborhood": listing.pickup_neighborhood,
        "pickup_city": listing.pickup_city,
        "pickup_number": number,
        "pickup_complement": complement,
    }


def get_booked_periods(db: Session, user: User, listing_id: int) -> dict[str, Any]:
    """Periods that block dates: accepted and completed rentals, like RN-42 (not pending)."""
    listing, owner = _load_listing(db, listing_id)
    if _is_unavailable_for(listing, owner, user):
        return {"items": []}
    rows = db.execute(
        select(Rental.start_date, Rental.end_date)
        .where(
            Rental.listing_id == listing.id,
            Rental.status.in_(("accepted", "completed")),
        )
        .order_by(Rental.start_date, Rental.id)
    ).all()
    return {"items": [{"start_date": start, "end_date": end} for start, end in rows]}

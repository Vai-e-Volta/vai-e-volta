from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import Listing, ListingPhoto, User
from app.schemas.my_listings import MyListing, MyListingsResponse
from app.schemas.registration import ApiErrorResponse
from app.services.feed import _decode_cursor, _encode_cursor

router = APIRouter(prefix="/api/me/listings", tags=["listings"])


@router.get(
    "",
    response_model=MyListingsResponse,
    responses={400: {"model": ApiErrorResponse}, 401: {"model": ApiErrorResponse}},
)
def my_listings(
    scope: Literal["active", "history"] = Query(default="active"),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MyListingsResponse:
    conditions = [Listing.owner_id == user.id]
    conditions.append(
        Listing.status == "active" if scope == "active" else Listing.status != "active"
    )
    total = db.scalar(select(func.count(Listing.id)).where(*conditions)) or 0
    if cursor:
        created_at, listing_id = _decode_cursor(cursor)
        conditions.append(
            or_(
                Listing.created_at < created_at,
                and_(Listing.created_at == created_at, Listing.id < listing_id),
            )
        )
    cover = (
        select(ListingPhoto.filename)
        .where(ListingPhoto.listing_id == Listing.id, ListingPhoto.position == 1)
        .correlate(Listing)
        .scalar_subquery()
    )
    rows = db.execute(
        select(Listing, cover)
        .where(*conditions)
        .order_by(Listing.created_at.desc(), Listing.id.desc())
        .limit(limit + 1)
    ).all()
    items = [
        MyListing.model_validate(listing).model_copy(update={"cover_photo": photo})
        for listing, photo in rows[:limit]
    ]
    next_cursor = _encode_cursor(items[-1].created_at, items[-1].id) if len(rows) > limit else None
    return MyListingsResponse(items=items, next_cursor=next_cursor, total=total)

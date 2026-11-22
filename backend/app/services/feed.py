from __future__ import annotations

import base64
import json
from datetime import UTC, datetime

from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Category, Favorite, Listing, ListingPhoto, Rental, User
from app.services.rental_situation import today_br


def price_ranges(db: Session) -> dict:
    prices = db.scalars(
        select(Listing.daily_price)
        .join(User, User.id == Listing.owner_id)
        .where(
            Listing.status == "active",
            Listing.available_until >= today_br(),
            User.deleted_at.is_(None),
        )
        .order_by(Listing.daily_price, Listing.id)
    ).all()
    count = len(prices)
    if count < 3:
        return {"ranges": []}
    # Distribui os anúncios em três grupos consecutivos, de tamanhos próximos.
    boundaries = (0, (count + 2) // 3, (2 * count + 2) // 3, count)
    labels = ("Mais baratos", "Intermediários", "Mais caros")
    return {
        "ranges": [
            {"label": label, "min": f"{prices[start]:.2f}", "max": f"{prices[end - 1]:.2f}"}
            for label, start, end in zip(labels, boundaries[:-1], boundaries[1:], strict=True)
        ]
    }


def _encode_cursor(created_at: datetime, listing_id: int) -> str:
    payload = json.dumps(
        {"created_at": created_at.astimezone(UTC).isoformat(), "id": listing_id},
        separators=(",", ":"),
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.b64decode(padded, altchars=b"-_", validate=True))
        created_at = datetime.fromisoformat(payload["created_at"])
        listing_id = payload["id"]
        if (
            created_at.tzinfo is None
            or isinstance(listing_id, bool)
            or not isinstance(listing_id, int)
            or listing_id < 1
        ):
            raise ValueError
        return created_at, listing_id
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        raise ApiError(
            status_code=400,
            code="INVALID_CURSOR",
            message="Cursor inválido.",
        ) from None


def escape_like(value: str) -> str:
    """Escape SQL LIKE metacharacters so user input is always literal text."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_feed(
    db: Session,
    user: User,
    limit: int,
    cursor: str | None,
    q: str | None = None,
    favorites: bool = False,
    categories: list[int] | None = None,
) -> dict:
    today = today_br()
    base_conditions = (
        Listing.status == "active",
        Listing.available_until >= today,
        User.deleted_at.is_(None),
    )
    active_rental = exists(
        select(Rental.id).where(
            Rental.listing_id == Listing.id,
            Rental.status == "accepted",
            Rental.start_date <= today,
            Rental.end_date >= today,
        )
    )
    favorite_for_user = exists(
        select(Favorite.listing_id).where(
            Favorite.user_id == user.id,
            Favorite.listing_id == Listing.id,
        )
    )
    cover = (
        select(ListingPhoto.filename)
        .where(ListingPhoto.listing_id == Listing.id, ListingPhoto.position == 1)
        .correlate(Listing)
        .scalar_subquery()
    )
    stmt = (
        select(
            Listing.id,
            cover.label("cover_photo"),
            case((active_rental, "rented"), else_="available").label("situation"),
            Category.name.label("category"),
            Listing.title,
            Listing.daily_price,
            Listing.pickup_neighborhood.label("neighborhood"),
            Listing.pickup_city.label("city"),
            Listing.created_at,
            (Listing.owner_id == user.id).label("is_owner"),
            favorite_for_user.label("is_favorite"),
        )
        .join(User, User.id == Listing.owner_id)
        .join(Category, Category.id == Listing.category_id)
        .order_by(Listing.created_at.desc(), Listing.id.desc())
    )
    conditions = list(base_conditions)
    if categories:
        requested = set(categories)
        known = set(db.scalars(select(Category.id).where(Category.id.in_(requested))).all())
        if requested != known:
            raise ApiError(
                status_code=422,
                code="VALIDATION_ERROR",
                message="Revise os campos informados.",
                fields={"categories": "Categoria desconhecida."},
            )
        conditions.append(Listing.category_id.in_(requested))
    if q:
        pattern = f"%{escape_like(q)}%"
        conditions.append(
            func.public.immutable_unaccent(func.lower(Listing.title)).ilike(pattern, escape="\\")
        )
    if favorites:
        conditions.append(favorite_for_user)
    stmt = stmt.where(*conditions)
    total_stmt = select(func.count(Listing.id)).join(User, User.id == Listing.owner_id)
    total = db.scalar(total_stmt.where(*conditions)) or 0
    if cursor:
        created_at, listing_id = _decode_cursor(cursor)
        stmt = stmt.where(
            or_(
                Listing.created_at < created_at,
                and_(Listing.created_at == created_at, Listing.id < listing_id),
            )
        )
    rows = db.execute(stmt.limit(limit + 1)).mappings().all()
    has_more = len(rows) > limit
    items = [dict(row) for row in rows[:limit]]
    next_cursor = (
        _encode_cursor(items[-1]["created_at"], items[-1]["id"]) if has_more and items else None
    )
    return {"items": items, "next_cursor": next_cursor, "total": total}

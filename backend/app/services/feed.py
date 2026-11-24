from __future__ import annotations

import base64
import json
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import ColumnElement, and_, case, exists, func, or_, select, text
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import (
    Category,
    Favorite,
    Listing,
    ListingPhoto,
    Rental,
    Tag,
    User,
    listing_tags,
)
from app.services.rental_situation import today_br

MAX_TAG_LENGTH = 30
MAX_PRICE = Decimal("5000")
MAX_BIGINT = 2**63 - 1

# sort -> (chave do cursor, coluna da chave, crescente?). O desempate por id segue a mesma
# direção da chave, para os índices (created_at, id) e (daily_price, id) servirem às 4 ordens.
_SORTS: dict[str, tuple[str, Any, bool]] = {
    "newest": ("created_at", Listing.created_at, False),
    "oldest": ("created_at", Listing.created_at, True),
    "price_asc": ("daily_price", Listing.daily_price, True),
    "price_desc": ("daily_price", Listing.daily_price, False),
}


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


def _invalid_cursor() -> ApiError:
    return ApiError(status_code=400, code="INVALID_CURSOR", message="Cursor inválido.")


def _encode_feed_cursor(sort: str, last: dict[str, Any]) -> str:
    """Cursor por chave (RN-30): ordem usada, chave dessa ordem e id do último item."""
    key_name = _SORTS[sort][0]
    key = last[key_name]
    value = key.astimezone(UTC).isoformat() if isinstance(key, datetime) else f"{key:.2f}"
    payload = json.dumps(
        {"sort": sort, key_name: value, "id": last["id"]}, separators=(",", ":")
    ).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _parse_price_key(raw: object) -> Decimal:
    if not isinstance(raw, str):
        raise ValueError
    price = Decimal(raw)
    if not price.is_finite() or not 0 <= price <= MAX_PRICE or price.as_tuple().exponent < -2:
        raise ValueError
    return price


def _decode_feed_cursor(cursor: str, sort: str) -> tuple[datetime | Decimal, int]:
    """Valida o cursor para a ordem pedida; qualquer defeito vira 400 INVALID_CURSOR."""
    key_name = _SORTS[sort][0]
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.b64decode(padded, altchars=b"-_", validate=True))
        listing_id = payload["id"]
        if (
            payload["sort"] != sort
            or isinstance(listing_id, bool)
            or not isinstance(listing_id, int)
            or not 1 <= listing_id <= MAX_BIGINT
        ):
            raise ValueError
        if key_name == "created_at":
            key = datetime.fromisoformat(payload[key_name])
            if key.tzinfo is None:
                raise ValueError
        else:
            key = _parse_price_key(payload[key_name])
        return key, listing_id
    except (ValueError, TypeError, KeyError, InvalidOperation):
        raise _invalid_cursor() from None


def escape_like(value: str) -> str:
    """Escape SQL LIKE metacharacters so user input is always literal text."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def visible_listing_conditions(today: date) -> tuple[ColumnElement[bool], ...]:
    """Listings shown in the feed (RN-24): active, still available and owner not deleted.

    Requires ``User`` joined as the listing owner.
    """
    return (
        Listing.status == "active",
        Listing.available_until >= today,
        User.deleted_at.is_(None),
    )


def normalize_tags(db: Session, tags: list[str]) -> list[str]:
    """Tags as stored in ``tags.normalized_name``: trimmed, lowercase, without accents (RN-57)."""
    cleaned = [tag.strip() for tag in tags]
    if any(not tag or len(tag) > MAX_TAG_LENGTH for tag in cleaned):
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Revise os campos informados.",
            fields={"tags": f"Cada tag deve ter de 1 a {MAX_TAG_LENGTH} caracteres."},
        )
    normalized = db.scalar(
        text(
            "SELECT array(SELECT lower(public.immutable_unaccent(t)) "
            "FROM unnest(CAST(:tags AS text[])) AS t)"
        ),
        {"tags": cleaned},
    )
    return sorted(set(normalized))


def popular_tags(db: Session, q: str | None, limit: int) -> list[dict]:
    """Tags of visible listings, most used first; with ``q``, those containing it (F-17)."""
    usage = func.count(func.distinct(Listing.id)).label("count")
    stmt = (
        select(Tag.name, usage)
        .join(listing_tags, listing_tags.c.tag_id == Tag.id)
        .join(Listing, Listing.id == listing_tags.c.listing_id)
        .join(User, User.id == Listing.owner_id)
        .where(*visible_listing_conditions(today_br()))
        .group_by(Tag.id, Tag.name)
        .order_by(usage.desc(), Tag.normalized_name)
        .limit(limit)
    )
    if q and q.strip():
        term = normalize_tags(db, [q])[0]
        stmt = stmt.where(Tag.normalized_name.like(f"%{escape_like(term)}%", escape="\\"))
    return [{"name": name, "count": count} for name, count in db.execute(stmt).all()]


def get_feed(
    db: Session,
    user: User,
    limit: int,
    cursor: str | None,
    q: str | None = None,
    favorites: bool = False,
    categories: list[int] | None = None,
    availability: str = "all",
    needed_from: date | None = None,
    needed_until: date | None = None,
    tags: list[str] | None = None,
    price_min: Decimal | None = None,
    price_max: Decimal | None = None,
    sort: str = "newest",
) -> dict:
    today = today_br()
    base_conditions = visible_listing_conditions(today)
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
    _key_name, key_column, ascending = _SORTS[sort]
    if ascending:
        order = (key_column.asc(), Listing.id.asc())
    else:
        order = (key_column.desc(), Listing.id.desc())
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
        .order_by(*order)
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
    if tags:
        normalized = normalize_tags(db, tags)
        # OU dentro do tipo (RN-26): o anúncio precisa ter qualquer uma das tags.
        conditions.append(
            exists(
                select(listing_tags.c.listing_id)
                .join(Tag, Tag.id == listing_tags.c.tag_id)
                .where(
                    listing_tags.c.listing_id == Listing.id,
                    Tag.normalized_name.in_(normalized),
                )
            )
        )
    if price_min is not None and price_max is not None and price_min > price_max:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Revise os campos informados.",
            fields={"price_min": "O mínimo não pode ser maior que o máximo."},
        )
    if price_min is not None:
        conditions.append(Listing.daily_price >= price_min)
    if price_max is not None:
        conditions.append(Listing.daily_price <= price_max)
    if q:
        pattern = f"%{escape_like(q)}%"
        conditions.append(
            func.public.immutable_unaccent(func.lower(Listing.title)).ilike(pattern, escape="\\")
        )
    if favorites:
        conditions.append(favorite_for_user)
    # RN-28: "all" não restringe; os grupos abaixo usam o mesmo "hoje" (today_br) do feed.
    if availability == "available_now":
        # Anúncio ativo (base), janela vigente hoje e sem aluguel aceito cobrindo hoje.
        conditions.extend([Listing.available_from <= today, ~active_rental])
    elif availability == "rented_now":
        conditions.append(active_rental)
    # RN-29 (F-22): só vale com os dois limites; com apenas um deles o filtro é ignorado.
    if needed_from is not None and needed_until is not None:
        if needed_from > needed_until:
            raise ApiError(
                status_code=422,
                code="VALIDATION_ERROR",
                message="Revise os campos informados.",
                fields={"needed_from": "A data inicial não pode ser depois da final."},
            )
        # Intervalos inclusivos nas duas pontas, como na restrição de aluguéis (RN-42, RN-36).
        overlapping_rental = exists(
            select(Rental.id).where(
                Rental.listing_id == Listing.id,
                Rental.status == "accepted",
                Rental.start_date <= needed_until,
                Rental.end_date >= needed_from,
            )
        )
        conditions.append(Listing.available_from <= needed_from)
        conditions.append(Listing.available_until >= needed_until)
        conditions.append(~overlapping_rental)
    stmt = stmt.where(*conditions)
    total_stmt = select(func.count(Listing.id)).join(User, User.id == Listing.owner_id)
    total = db.scalar(total_stmt.where(*conditions)) or 0
    if cursor:
        key, listing_id = _decode_feed_cursor(cursor, sort)
        if ascending:
            after = or_(key_column > key, and_(key_column == key, Listing.id > listing_id))
        else:
            after = or_(key_column < key, and_(key_column == key, Listing.id < listing_id))
        stmt = stmt.where(after)
    rows = db.execute(stmt.limit(limit + 1)).mappings().all()
    has_more = len(rows) > limit
    items = [dict(row) for row in rows[:limit]]
    next_cursor = _encode_feed_cursor(sort, items[-1]) if has_more and items else None
    return {"items": items, "next_cursor": next_cursor, "total": total}

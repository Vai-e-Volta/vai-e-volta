from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.errors import ApiError
from app.models import Favorite, Listing, User
from app.schemas.feed import FeedResponse, PriceRangesResponse
from app.schemas.registration import ApiErrorResponse
from app.services.feed import get_feed, price_ranges

router = APIRouter(prefix="/api/listings", tags=["feed"])


@router.get("/price-ranges", response_model=PriceRangesResponse)
def listing_price_ranges(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> PriceRangesResponse:
    return PriceRangesResponse.model_validate(price_ranges(db))


@router.get(
    "",
    response_model=FeedResponse,
    responses={
        400: {"model": ApiErrorResponse, "description": "Cursor inválido"},
        401: {"model": ApiErrorResponse, "description": "Sessão inválida"},
        422: {"model": ApiErrorResponse, "description": "Filtro inválido"},
    },
)
def listing_feed(
    q: str | None = Query(default=None),
    favorites: bool = Query(default=False),
    categories: list[int] | None = Query(default=None, alias="categories[]"),
    availability: Literal["all", "available_now", "rented_now"] = Query(default="all"),
    tags: list[str] | None = Query(default=None, alias="tags[]", max_length=20),
    price_min: Decimal | None = Query(default=None, ge=0, le=5000, decimal_places=2),
    price_max: Decimal | None = Query(default=None, ge=0, le=5000, decimal_places=2),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedResponse:
    return FeedResponse.model_validate(
        get_feed(
            db,
            user,
            limit,
            cursor,
            q,
            favorites,
            categories,
            availability=availability,
            tags=tags,
            price_min=price_min,
            price_max=price_max,
        )
    )


def _require_listing(db: Session, listing_id: int, *, allow_deleted: bool = False) -> None:
    listing = db.get(Listing, listing_id)
    if listing is None or (listing.status == "deleted" and not allow_deleted):
        raise ApiError(
            status_code=404,
            code="LISTING_NOT_FOUND",
            message="Anúncio não encontrado.",
        )


@router.put(
    "/{listing_id}/favorite",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ApiErrorResponse, "description": "Anúncio não encontrado"}},
)
def add_favorite(
    listing_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    _require_listing(db, listing_id)
    statement = (
        insert(Favorite)
        .values(user_id=user.id, listing_id=listing_id)
        .on_conflict_do_nothing(index_elements=["user_id", "listing_id"])
    )
    db.execute(statement)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{listing_id}/favorite",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ApiErrorResponse, "description": "Anúncio não encontrado"}},
)
def remove_favorite(
    listing_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    _require_listing(db, listing_id, allow_deleted=True)
    db.query(Favorite).filter_by(user_id=user.id, listing_id=listing_id).delete()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

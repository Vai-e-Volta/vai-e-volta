from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.errors import ApiError
from app.models import Favorite, Listing, User
from app.schemas.feed import FeedResponse
from app.schemas.registration import ApiErrorResponse
from app.services.feed import get_feed

router = APIRouter(prefix="/api/listings", tags=["feed"])


@router.get(
    "",
    response_model=FeedResponse,
    responses={
        400: {"model": ApiErrorResponse, "description": "Cursor inválido"},
        401: {"model": ApiErrorResponse, "description": "Sessão inválida"},
    },
)
def listing_feed(
    q: str | None = Query(default=None),
    favorites: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedResponse:
    return FeedResponse.model_validate(get_feed(db, user, limit, cursor, q, favorites))


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

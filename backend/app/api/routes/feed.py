from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import User
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
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FeedResponse:
    return FeedResponse.model_validate(get_feed(db, user, limit, cursor))

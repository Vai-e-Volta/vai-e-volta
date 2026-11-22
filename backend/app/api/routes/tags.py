from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import User
from app.schemas.feed import TagsResponse
from app.schemas.registration import ApiErrorResponse
from app.services.feed import MAX_TAG_LENGTH, popular_tags

router = APIRouter(prefix="/api/tags", tags=["feed"])


@router.get(
    "",
    response_model=TagsResponse,
    responses={
        401: {"model": ApiErrorResponse, "description": "Sessão inválida"},
        422: {"model": ApiErrorResponse, "description": "Parâmetro inválido"},
    },
)
def list_tags(
    q: str | None = Query(default=None, max_length=MAX_TAG_LENGTH),
    limit: int = Query(default=10, ge=1, le=30),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> TagsResponse:
    """Tags mais usadas nos anúncios visíveis no feed; com ``q``, as que contêm o texto (F-17)."""
    return TagsResponse.model_validate({"tags": popular_tags(db, q, limit)})

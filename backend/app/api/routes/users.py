from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.errors import ApiError
from app.models import Listing, User
from app.schemas.registration import ApiErrorResponse
from app.schemas.users import PublicListing, PublicUser

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get(
    "/{username}",
    response_model=PublicUser,
    responses={
        401: {
            "model": ApiErrorResponse,
            "description": "Autenticação obrigatória",
        },
        404: {
            "model": ApiErrorResponse,
            "description": "Perfil não encontrado",
        },
    },
)
def get_public_profile(
    username: str,
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PublicUser:
    user = db.scalar(
        select(User).where(
            User.username == username,
            User.deleted_at.is_(None),
            User.anonymized_at.is_(None),
        )
    )

    if user is None:
        raise ApiError(
            status_code=404,
            code="USER_NOT_FOUND",
            message="Perfil não encontrado.",
        )

    listings = db.scalars(
        select(Listing)
        .where(
            Listing.owner_id == user.id,
            Listing.status == "active",
            Listing.available_until >= func.current_date(),
        )
        .order_by(Listing.id)
    ).all()

    return PublicUser(
        username=user.username,
        neighborhood=user.neighborhood,
        city=user.city,
        created_at=user.created_at,
        listings=[
            PublicListing.model_validate(listing, from_attributes=True) for listing in listings
        ],
    )

from __future__ import annotations

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import User
from app.schemas.listing_detail import (
    BookedPeriodsResponse,
    ListingUnavailable,
    PublicListingDetail,
)
from app.schemas.registration import ApiErrorResponse
from app.services.listing_detail import get_booked_periods, get_listing_detail

router = APIRouter(prefix="/api/listings", tags=["listings"])

responses = {
    401: {"model": ApiErrorResponse, "description": "Sessão inválida"},
    404: {"model": ApiErrorResponse, "description": "Anúncio não encontrado"},
}


@router.get(
    "/{listing_id}",
    response_model=PublicListingDetail | ListingUnavailable,
    responses=responses,
)
def listing_detail(
    listing_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PublicListingDetail | ListingUnavailable:
    data = get_listing_detail(db, user, listing_id)
    if data["unavailable"]:
        return ListingUnavailable.model_validate(data)
    return PublicListingDetail.model_validate(data)


@router.get(
    "/{listing_id}/booked-periods",
    response_model=BookedPeriodsResponse,
    responses=responses,
)
def listing_booked_periods(
    listing_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BookedPeriodsResponse:
    return BookedPeriodsResponse.model_validate(get_booked_periods(db, user, listing_id))

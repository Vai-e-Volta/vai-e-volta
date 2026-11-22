from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import User
from app.schemas.registration import ApiErrorResponse
from app.services.listing_lifecycle import change_listing_status

router = APIRouter(prefix="/api/listings", tags=["listings"])
responses = {
    401: {"model": ApiErrorResponse},
    403: {"model": ApiErrorResponse},
    404: {"model": ApiErrorResponse},
    409: {"model": ApiErrorResponse},
}


@router.post("/{listing_id}/pause", status_code=status.HTTP_204_NO_CONTENT, responses=responses)
def pause_listing(
    listing_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    change_listing_status(db, user, listing_id, "pause")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{listing_id}/resume", status_code=status.HTTP_204_NO_CONTENT, responses=responses)
def resume_listing(
    listing_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    change_listing_status(db, user, listing_id, "resume")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT, responses=responses)
def delete_listing(
    listing_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    change_listing_status(db, user, listing_id, "delete")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

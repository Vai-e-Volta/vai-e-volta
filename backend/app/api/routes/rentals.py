from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.errors import ApiError
from app.models import Rental, User
from app.schemas.registration import ApiErrorResponse
from app.schemas.rentals import RentalListResponse
from app.services.rental_accept import accept_proposal
from app.services.rental_situation import today_br
from app.services.rentals import list_rentals

router = APIRouter(prefix="/api/rentals", tags=["rentals"])
list_router = APIRouter(prefix="/api/me/rentals", tags=["rentals"])


@router.post(
    "/{rental_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ApiErrorResponse, "description": "Sessão inválida"},
        403: {"model": ApiErrorResponse, "description": "Somente o locatário pode cancelar"},
        404: {"model": ApiErrorResponse, "description": "Aluguel não encontrado"},
        409: {"model": ApiErrorResponse, "description": "Cancelamento não permitido"},
    },
)
def cancel_rental(
    rental_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    # A concurrent acceptance or expiration must finish before we inspect the state.
    rental = db.scalar(select(Rental).where(Rental.id == rental_id).with_for_update())
    if rental is None:
        raise ApiError(status_code=404, code="RENTAL_NOT_FOUND", message="Aluguel não encontrado.")
    if rental.renter_id != user.id:
        raise ApiError(
            status_code=403, code="FORBIDDEN", message="Somente o locatário pode cancelar."
        )
    now = datetime.now(UTC)
    if rental.status == "accepted" and rental.start_date <= today_br(now):
        raise ApiError(
            status_code=409,
            code="CANCEL_NOT_ALLOWED",
            message="Não é possível cancelar um aluguel que já começou.",
        )
    if rental.status not in ("pending", "accepted"):
        raise ApiError(status_code=409, code="INVALID_STATE", message="Aluguel em estado inválido.")
    rental.status = "canceled"
    rental.canceled_at = now
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{rental_id}/return-request",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ApiErrorResponse, "description": "Sessão inválida"},
        403: {"model": ApiErrorResponse, "description": "Somente o locatário pode avisar"},
        404: {"model": ApiErrorResponse, "description": "Aluguel não encontrado"},
        409: {"model": ApiErrorResponse, "description": "Aluguel em estado inválido"},
    },
)
def request_return(
    rental_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    rental = db.get(Rental, rental_id)
    if rental is None:
        raise ApiError(status_code=404, code="RENTAL_NOT_FOUND", message="Aluguel não encontrado.")
    if rental.renter_id != user.id:
        raise ApiError(
            status_code=403,
            code="FORBIDDEN",
            message="Somente o locatário pode avisar a devolução.",
        )
    if rental.status != "accepted" or rental.start_date > today_br():
        raise ApiError(
            status_code=409,
            code="INVALID_STATE",
            message="A devolução só pode ser avisada durante um aluguel iniciado.",
        )
    if rental.return_requested_at is None:
        rental.return_requested_at = datetime.now(UTC)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{rental_id}/accept",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ApiErrorResponse, "description": "Sessão inválida"},
        403: {"model": ApiErrorResponse, "description": "Somente o dono pode aceitar"},
        404: {"model": ApiErrorResponse, "description": "Aluguel não encontrado"},
        409: {"model": ApiErrorResponse, "description": "Proposta expirada ou em estado inválido"},
    },
)
def accept_rental(
    rental_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    accept_proposal(db, user, rental_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@list_router.get(
    "",
    response_model=RentalListResponse,
    responses={
        400: {"model": ApiErrorResponse, "description": "Cursor inválido"},
        401: {"model": ApiErrorResponse, "description": "Sessão inválida"},
    },
)
def rentals(
    role: Literal["renter", "owner"] = Query(),
    scope: Literal["active", "history"] = Query(),
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RentalListResponse:
    data = list_rentals(db, user, role, scope, limit, cursor)
    return RentalListResponse.model_validate(data)

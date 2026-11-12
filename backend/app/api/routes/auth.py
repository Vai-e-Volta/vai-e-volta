from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.registration import ApiErrorResponse, RegistrationRequest, RegistrationResponse
from app.security.registration import RegistrationSecurity, registration_security
from app.services.registration import register_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def get_registration_security() -> RegistrationSecurity:
    return registration_security


@router.post(
    "/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {
            "model": ApiErrorResponse,
            "description": "Campo já cadastrado",
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "model": ApiErrorResponse,
            "description": "Dados de cadastro inválidos",
        },
    },
)
def register(
    payload: RegistrationRequest,
    db: Session = Depends(get_db),
    security: RegistrationSecurity = Depends(get_registration_security),
) -> RegistrationResponse:
    user: User = register_user(db, payload, security)
    return RegistrationResponse(id=user.id, username=user.username, created_at=user.created_at)

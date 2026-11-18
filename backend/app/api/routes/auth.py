from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.security import APIKeyCookie
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ApiError
from app.models import User
from app.schemas.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    LoginRequest,
    MeResponse,
)
from app.schemas.registration import ApiErrorResponse, RegistrationRequest, RegistrationResponse
from app.security.registration import RegistrationSecurity, registration_security
from app.security.session import (
    SESSION_COOKIE,
    cookie_secure,
    create_session_token,
    session_lifetime,
)
from app.services.account import change_password, delete_account
from app.services.authentication import authenticate, current_user_from_token
from app.services.registration import register_user

router = APIRouter(prefix="/api/auth", tags=["auth"])
account_router = APIRouter(prefix="/api/me", tags=["account"])
session_cookie_auth = APIKeyCookie(
    name=SESSION_COOKIE,
    scheme_name="SessionCookie",
    description="Cookie de sessão HttpOnly vv_session.",
    auto_error=False,
)


def get_registration_security() -> RegistrationSecurity:
    return registration_security


def require_json_or_multipart(request: Request) -> None:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"application/json", "multipart/form-data"}:
        raise ApiError(
            status_code=415,
            code="UNSUPPORTED_MEDIA_TYPE",
            message="Use application/json ou multipart/form-data.",
        )


def get_current_user(
    token: str | None = Depends(session_cookie_auth), db: Session = Depends(get_db)
) -> User:
    if not token:
        raise ApiError(
            status_code=401, code="UNAUTHENTICATED", message="Faça login para continuar."
        )
    return current_user_from_token(db, token)


def _set_session_cookie(response: Response, token: str) -> None:
    lifetime = session_lifetime()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=int(lifetime.total_seconds()),
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )


def _delete_session_cookie(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
    )


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
    dependencies=[Depends(require_json_or_multipart)],
)
def register(
    payload: RegistrationRequest,
    db: Session = Depends(get_db),
    security: RegistrationSecurity = Depends(get_registration_security),
) -> RegistrationResponse:
    user: User = register_user(db, payload, security)
    return RegistrationResponse(id=user.id, username=user.username, created_at=user.created_at)


@router.post(
    "/login",
    response_model=MeResponse,
    responses={401: {"model": ApiErrorResponse}, 429: {"model": ApiErrorResponse}},
    dependencies=[Depends(require_json_or_multipart)],
)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> MeResponse:
    user, token = authenticate(db, payload.identifier, payload.password)
    _set_session_cookie(response, token)
    return MeResponse.model_validate(user, from_attributes=True)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    _media_type: None = Depends(require_json_or_multipart),
    _user: User = Depends(get_current_user),
) -> Response:
    _delete_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse.model_validate(user, from_attributes=True)


@account_router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def update_password(
    payload: ChangePasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
    _media_type: None = Depends(require_json_or_multipart),
    user: User = Depends(get_current_user),
) -> Response:
    change_password(db, user, payload.current_password, payload.new_password)
    _set_session_cookie(response, create_session_token(user.id, user.token_version))
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@account_router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def remove_account(
    payload: DeleteAccountRequest,
    response: Response,
    db: Session = Depends(get_db),
    _media_type: None = Depends(require_json_or_multipart),
    user: User = Depends(get_current_user),
) -> Response:
    delete_account(db, user, payload.password)
    _delete_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response

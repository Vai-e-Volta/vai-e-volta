from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import LoginAttempt, User
from app.security.registration import registration_security
from app.security.session import create_session_token, decode_session_token

INVALID_CREDENTIALS = "E-mail, usuário ou senha incorretos"
_password_hasher = PasswordHasher()
_dummy_password_hash = _password_hasher.hash("Vai-e-Volta-dummy-password-9!")


def _identifier_hash(identifier: str) -> str:
    return hashlib.sha256(identifier.casefold().encode("utf-8")).hexdigest()


def _invalid_credentials() -> ApiError:
    return ApiError(status_code=401, code="INVALID_CREDENTIALS", message=INVALID_CREDENTIALS)


def _verify_password(password_hash: str, password: str, *, fallback: bool = True) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        if fallback and password_hash != _dummy_password_hash:
            _verify_password(_dummy_password_hash, password, fallback=False)
        return False


def authenticate(db: Session, identifier: str, password: str) -> tuple[User, str]:
    normalized_identifier = identifier.strip()
    identifier_digest = _identifier_hash(normalized_identifier)
    now = datetime.now(UTC)
    window = timedelta(minutes=int(os.getenv("LOGIN_WINDOW_MINUTES", "15")))
    lock_duration = timedelta(minutes=int(os.getenv("LOGIN_LOCK_MINUTES", "15")))
    max_attempts = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))

    failures = list(
        db.scalars(
            select(LoginAttempt)
            .where(
                LoginAttempt.identifier_hash == identifier_digest,
                LoginAttempt.success.is_(False),
                LoginAttempt.attempted_at >= now - window,
            )
            .order_by(LoginAttempt.attempted_at.desc())
        )
    )
    if len(failures) >= max_attempts:
        retry_after = max(0, int((failures[0].attempted_at + lock_duration - now).total_seconds()))
        if retry_after > 0:
            raise ApiError(
                status_code=429,
                code="LOGIN_LOCKED",
                message="Muitas tentativas de login. Aguarde antes de tentar novamente.",
                headers={"Retry-After": str(retry_after)},
            )

    user = db.scalar(
        select(User).where(
            or_(
                func.lower(User.username) == normalized_identifier.casefold(),
                func.lower(User.email) == normalized_identifier.casefold(),
            )
        )
    )
    password_matches = _verify_password(user.password_hash, password) if user else False
    if user is None:
        _verify_password(_dummy_password_hash, password)

    if (
        user is None
        or not password_matches
        or user.anonymized_at is not None
        or (user.deleted_at is not None and (user.purge_after is None or user.purge_after <= now))
    ):
        db.add(LoginAttempt(identifier_hash=identifier_digest, success=False))
        db.commit()
        raise _invalid_credentials()

    # A valid login inside the retention period reactivates the account. Listings stay paused.
    if user.deleted_at is not None:
        user.deleted_at = None
        user.purge_after = None
        user.token_version += 1

    db.add(LoginAttempt(identifier_hash=identifier_digest, success=True))
    db.commit()
    db.refresh(user)
    return user, create_session_token(user.id, user.token_version)


def current_user_from_token(db: Session, token: str) -> User:
    try:
        user_id, token_version = decode_session_token(token)
    except (jwt.InvalidTokenError, ValueError, RuntimeError):
        raise ApiError(
            status_code=401, code="UNAUTHENTICATED", message="Faça login para continuar."
        ) from None

    user = db.get(User, user_id)
    if (
        user is None
        or user.deleted_at is not None
        or user.anonymized_at is not None
        or user.token_version != token_version
    ):
        raise ApiError(
            status_code=401, code="UNAUTHENTICATED", message="Faça login para continuar."
        )
    return user


def verify_current_password(user: User, password: str) -> bool:
    return _verify_password(user.password_hash, password)


def hash_password(password: str) -> str:
    return registration_security.hash_password(password)


def password_is_valid(password: str) -> bool:
    return registration_security.validate_password(password)

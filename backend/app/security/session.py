from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

SESSION_COOKIE = "vv_session"
SESSION_ALGORITHM = "HS256"


def session_lifetime() -> timedelta:
    days = int(os.getenv("JWT_EXPIRES_DAYS", "15"))
    if days < 1:
        raise ValueError("JWT_EXPIRES_DAYS must be positive")
    return timedelta(days=days)


def jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 characters")
    return secret


def create_session_token(user_id: UUID, token_version: int) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "tv": token_version,
        "iat": now,
        "exp": now + session_lifetime(),
    }
    return jwt.encode(claims, jwt_secret(), algorithm=SESSION_ALGORITHM)


def decode_session_token(token: str) -> tuple[UUID, int]:
    claims = jwt.decode(
        token,
        jwt_secret(),
        algorithms=[SESSION_ALGORITHM],
        options={"require": ["sub", "tv", "iat", "exp"]},
    )
    user_id = UUID(claims["sub"])
    token_version = claims["tv"]
    if not isinstance(token_version, int) or token_version < 0:
        raise jwt.InvalidTokenError("Invalid token version")
    return user_id, token_version


def cookie_secure() -> bool:
    return os.getenv("COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"}

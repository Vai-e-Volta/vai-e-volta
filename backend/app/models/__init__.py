"""SQLAlchemy models registered in the shared metadata."""

from app.models.login_attempt import LoginAttempt
from app.models.user import User

__all__ = ["LoginAttempt", "User"]

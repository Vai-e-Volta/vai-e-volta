"""SQLAlchemy models registered in the shared metadata."""

from app.models.favorite import Favorite
from app.models.listing import Category, Listing, ListingPhoto, Tag, listing_tags
from app.models.login_attempt import LoginAttempt
from app.models.rental import Rental
from app.models.user import User

__all__ = [
    "Category",
    "Favorite",
    "Listing",
    "ListingPhoto",
    "LoginAttempt",
    "Rental",
    "Tag",
    "User",
    "listing_tags",
]

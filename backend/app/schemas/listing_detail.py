from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PublicListingPhoto(BaseModel):
    id: int
    filename: str


class PublicListingDetail(BaseModel):
    """Listing page for the public (RN-15): never carries CEP, e-mail, CPF or phone."""

    model_config = ConfigDict(extra="forbid")

    id: int
    unavailable: bool
    status: str
    title: str
    description: str
    daily_price: Decimal
    max_days: int
    available_from: date
    available_until: date
    category: str
    tags: list[str]
    photos: list[PublicListingPhoto]
    owner_username: str
    is_owner: bool
    pickup_street: str
    pickup_neighborhood: str
    pickup_city: str
    pickup_number: str | None
    pickup_complement: str | None


class ListingUnavailable(BaseModel):
    """Answer for a paused or deleted listing, or one from a deleted account (RN-34)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    unavailable: bool


class BookedPeriod(BaseModel):
    start_date: date
    end_date: date


class BookedPeriodsResponse(BaseModel):
    items: list[BookedPeriod]

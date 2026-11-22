from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PublicListing(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cover_photo: str | None
    situation: str
    category: str
    title: str
    daily_price: Decimal
    neighborhood: str
    city: str
    created_at: datetime
    is_owner: bool
    is_favorite: bool


class FeedResponse(BaseModel):
    items: list[PublicListing]
    next_cursor: str | None
    total: int


class PriceRange(BaseModel):
    label: str
    min: str
    max: str


class PriceRangesResponse(BaseModel):
    ranges: list[PriceRange]

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class RentalListItem(BaseModel):
    id: int
    listing_id: int
    title: str
    cover_photo: str | None
    start_date: date
    end_date: date
    status: str
    situation: str
    daily_price: Decimal
    estimated_total: Decimal
    created_at: datetime
    other_party_name: str
    other_party_phone: str | None


class RentalListResponse(BaseModel):
    items: list[RentalListItem]
    next_cursor: str | None
    total: int

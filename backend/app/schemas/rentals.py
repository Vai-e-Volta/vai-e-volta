from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class PickupAddress(BaseModel):
    """Pickup address from the rental's listing_snapshot (RN-35). The CEP is never returned."""

    street: str | None
    number: str | None
    complement: str | None
    neighborhood: str | None
    city: str | None
    state: str | None


class RentalListItem(BaseModel):
    """What any party of a rental sees, in any state: no phone and no complete address."""

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


class AcceptedRentalListItem(RentalListItem):
    """Only for the two parties of an `accepted` rental: phone (RN-17) and address (RN-35)."""

    other_party_phone: str
    pickup_address: PickupAddress | None


class RentalListResponse(BaseModel):
    items: list[AcceptedRentalListItem | RentalListItem]
    next_cursor: str | None
    total: int

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class MyListing(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    title: str
    description: str
    daily_price: Decimal
    max_days: int
    available_from: date
    available_until: date
    status: str
    pickup_cep: str
    pickup_street: str
    pickup_number: str
    pickup_complement: str | None
    pickup_neighborhood: str
    pickup_city: str
    pickup_state: str
    created_at: datetime
    cover_photo: str | None = None


class MyListingsResponse(BaseModel):
    items: list[MyListing]
    next_cursor: str | None
    total: int

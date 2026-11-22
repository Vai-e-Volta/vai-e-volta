from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PublicListing(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: int
    title: str
    daily_price: Decimal


class PublicUser(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    username: str
    neighborhood: str
    city: str
    created_at: datetime
    listings: list[PublicListing]

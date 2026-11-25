from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    """One notice. The text is built by the frontend from `type` and `payload` (RN-68)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    rental_id: int | None
    payload: dict[str, Any]
    created_at: datetime
    read_at: datetime | None


class NotificationsResponse(BaseModel):
    items: list[NotificationOut]
    next_cursor: str | None
    total: int


class UnreadCountResponse(BaseModel):
    count: int

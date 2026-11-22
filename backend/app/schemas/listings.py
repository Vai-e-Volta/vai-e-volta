from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.registration import VALID_UF


class ListingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=1000)
    daily_price: Decimal = Field(ge=1, le=5000, max_digits=7, decimal_places=2)
    max_days: int = Field(ge=1)
    available_from: date
    available_until: date
    category_id: int = Field(ge=1)
    pickup_cep: str | None = Field(default=None, pattern=r"^\d{8}$")
    pickup_street: str | None = Field(default=None, min_length=1, max_length=100)
    pickup_number: str | None = Field(default=None, min_length=1, max_length=10)
    pickup_complement: str | None = Field(default=None, max_length=60)
    pickup_neighborhood: str | None = Field(default=None, min_length=1, max_length=100)
    pickup_city: str | None = Field(default=None, min_length=1, max_length=100)
    pickup_state: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")

    @field_validator("pickup_state")
    @classmethod
    def validate_pickup_state(cls, value: str | None) -> str | None:
        if value is not None and value not in VALID_UF:
            raise ValueError("UF inválida")
        return value


class ListingCreated(BaseModel):
    id: int


class CategoryResponse(BaseModel):
    id: int
    name: str

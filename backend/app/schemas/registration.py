from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationInfo, field_validator

VALID_UF = {
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
}


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=1, max_length=120)
    username: str = Field(min_length=3, max_length=30, pattern=r"^[a-z][a-z0-9_]{2,29}$")
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)
    cpf: str = Field(min_length=11, max_length=14)
    phone: str = Field(min_length=11, max_length=15)
    cep: str = Field(pattern=r"^\d{8}$")
    street: str = Field(min_length=1, max_length=100)
    number: str = Field(min_length=1, max_length=10)
    complement: str | None = Field(default=None, max_length=60)
    neighborhood: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(pattern=r"^[A-Za-z]{2}$")

    @field_validator("*", mode="before")
    @classmethod
    def strip_non_password_fields(cls, value: object, info: ValidationInfo) -> object:
        if info.field_name != "password" and isinstance(value, str):
            return value.strip()
        return value

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str) -> str:
        value = value.upper()
        if value not in VALID_UF:
            raise ValueError("UF inválida")
        return value


class RegistrationResponse(BaseModel):
    id: UUID
    username: str
    created_at: datetime


class ApiErrorDetail(BaseModel):
    code: str
    message: str
    fields: dict[str, str]


class ApiErrorResponse(BaseModel):
    error: ApiErrorDetail

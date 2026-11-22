from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identifier: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class MeResponse(BaseModel):
    id: UUID
    full_name: str
    username: str
    email: str = Field(json_schema_extra={"format": "email"})
    phone: str
    cep: str
    street: str
    number: str
    complement: str | None
    neighborhood: str
    city: str
    state: str
    created_at: datetime


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class DeleteAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=128)


class UpdateAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = None
    username: str | None = None
    email: str | None = None
    cpf: str | None = None
    phone: str | None = None
    cep: str | None = None
    street: str | None = None
    number: str | None = None
    complement: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    state: str | None = None

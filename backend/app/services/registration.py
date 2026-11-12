from __future__ import annotations

from typing import Protocol

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import User
from app.schemas.registration import RegistrationRequest


class RegistrationSecurity(Protocol):
    def normalize_cpf(self, cpf: str) -> str | None: ...

    def validate_password(self, password: str) -> bool: ...

    def normalize_phone(self, phone: str) -> str | None: ...

    def hash_password(self, password: str) -> str: ...


def _field_in_use(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    constraint_name = getattr(diagnostic, "constraint_name", None)
    return {
        "uq_users_username": "username",
        "uq_users_email": "email",
        "uq_users_cpf": "cpf",
    }.get(constraint_name)


def register_user(
    db: Session, payload: RegistrationRequest, security: RegistrationSecurity
) -> User:
    """Apply registration rules in order and persist one user."""
    if not security.validate_password(payload.password):
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Revise os campos informados.",
            fields={"password": "Use de 8 a 128 caracteres, com maiúscula, número e símbolo."},
        )

    phone = security.normalize_phone(payload.phone)
    if phone is None:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Revise os campos informados.",
            fields={"phone": "Informe um telefone celular com DDD."},
        )

    cpf = security.normalize_cpf(payload.cpf)
    if cpf is None:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Revise os campos informados.",
            fields={"cpf": "CPF inválido."},
        )

    user = User(
        full_name=payload.full_name,
        username=payload.username,
        email=str(payload.email),
        cpf=cpf,
        phone=phone,
        password_hash=security.hash_password(payload.password),
        cep=payload.cep,
        street=payload.street,
        number=payload.number,
        complement=payload.complement,
        neighborhood=payload.neighborhood,
        city=payload.city,
        state=payload.state,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        field = _field_in_use(error)
        if field is None:
            raise
        raise ApiError(
            status_code=409,
            code="FIELD_IN_USE",
            message="Um dos campos já está em uso.",
            fields={field: "Este campo já está cadastrado."},
        ) from error

    db.refresh(user)
    return user

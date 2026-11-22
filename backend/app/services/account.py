from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import Listing, Rental, User
from app.schemas.registration import RegistrationRequest
from app.security.registration import registration_security
from app.services.authentication import hash_password, password_is_valid, verify_current_password
from app.services.proposal_expiry import expire_pending_proposals
from app.services.registration import _field_in_use
from app.services.rental_situation import today_br


def update_account(db: Session, user: User, changes: dict) -> None:
    values = {
        name: getattr(user, name) for name in RegistrationRequest.model_fields if name != "password"
    }
    values.update(changes)
    values["password"] = "Unused1!"
    try:
        validated = RegistrationRequest.model_validate(values)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from None
    normalized_cpf = registration_security.normalize_cpf(validated.cpf)
    normalized_phone = registration_security.normalize_phone(validated.phone)
    fields = {}
    if normalized_cpf is None:
        fields["cpf"] = "CPF inválido."
    if normalized_phone is None:
        fields["phone"] = "Informe um telefone celular com DDD."
    if fields:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Revise os campos informados.",
            fields=fields,
        )
    for name in changes:
        value = getattr(validated, name)
        if name == "cpf":
            value = normalized_cpf
        elif name == "phone":
            value = normalized_phone
        elif name == "email":
            value = str(value)
        setattr(user, name, value)
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


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    if not verify_current_password(user, current_password):
        raise ApiError(
            status_code=401, code="INVALID_CREDENTIALS", message="Senha atual incorreta."
        )
    if not password_is_valid(new_password):
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Revise os campos informados.",
            fields={"new_password": "Use de 8 a 128 caracteres, com maiúscula, número e símbolo."},
        )

    user.password_hash = hash_password(new_password)
    user.token_version += 1
    db.commit()
    db.refresh(user)


def delete_account(db: Session, user: User, password: str) -> None:
    if not verify_current_password(user, password):
        raise ApiError(
            status_code=401, code="INVALID_CREDENTIALS", message="Senha atual incorreta."
        )

    today = today_br()
    active_rental = db.scalar(
        select(Rental.id)
        .outerjoin(Listing, Listing.id == Rental.listing_id)
        .where(
            Rental.status == "accepted",
            Rental.end_date >= today,
            or_(Rental.renter_id == user.id, Listing.owner_id == user.id),
        )
        .limit(1)
    )
    if active_rental is not None:
        raise ApiError(
            status_code=409,
            code="ACCOUNT_HAS_ACTIVE_RENTAL",
            message="Conclua ou cancele seus aluguéis aceitos antes de excluir a conta.",
        )

    now = datetime.now(UTC)
    retention_days = int(os.getenv("ACCOUNT_RETENTION_DAYS", "365"))
    # All state changes occur in this transaction so the user never reaches a partial deletion.
    involved = or_(
        Rental.renter_id == user.id,
        Rental.listing_id.in_(select(Listing.id).where(Listing.owner_id == user.id)),
    )
    # Overdue pending proposals are expired, not canceled (RN-47, H018-3).
    expire_pending_proposals(db, now, involved)
    db.execute(
        update(Rental)
        .where(Rental.status == "pending", involved)
        .values(status="canceled", canceled_at=now)
    )
    db.execute(
        update(Listing)
        .where(Listing.owner_id == user.id, Listing.status == "active")
        .values(status="paused", updated_at=now)
    )
    user.deleted_at = now
    user.purge_after = now + timedelta(days=retention_days)
    user.token_version += 1
    db.commit()

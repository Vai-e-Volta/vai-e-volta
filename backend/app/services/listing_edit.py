from __future__ import annotations

import os
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.errors import ApiError
from app.models import Category, Listing, ListingPhoto, Rental, Tag, User, listing_tags
from app.schemas.listings import ListingCreate
from app.services.listing_photos import (
    _ALLOWED_FORMATS,
    _detect_format,
    _read_file,
    _sanitize_image,
    _settings,
)
from app.services.rental_situation import today_br


def invalid(field: str, message: str) -> ApiError:
    return ApiError(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Revise os campos informados.",
        fields={field: message},
    )


def edit_listing(db: Session, user: User, listing_id: int, form: Any) -> None:
    listing = db.scalar(select(Listing).where(Listing.id == listing_id).with_for_update())
    if listing is None:
        raise ApiError(status_code=404, code="LISTING_NOT_FOUND", message="Anúncio não encontrado.")
    if listing.owner_id != user.id:
        raise ApiError(status_code=403, code="FORBIDDEN", message="Somente o dono pode editar.")
    if listing.status == "deleted":
        raise ApiError(status_code=409, code="INVALID_STATE", message="Anúncio indisponível.")

    list_fields = {"tags[]", "photos[]", "keep_photo_ids[]"}
    changes = {key: form.get(key) for key in form.keys() if key not in list_fields}
    if any(len(form.getlist(key)) != 1 for key in changes):
        raise invalid("body", "Campo repetido.")
    final_values = {name: getattr(listing, name) for name in ListingCreate.model_fields}
    final_values.update(changes)
    try:
        data = ListingCreate.model_validate(final_values)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from None
    if data.available_from > data.available_until:
        raise invalid("available_until", "A data final deve ser posterior à inicial.")
    if data.available_until < today_br():
        raise invalid("available_until", "A data final não pode estar no passado.")
    if data.max_days > (data.available_until - data.available_from).days + 1:
        raise invalid("max_days", "O prazo excede a janela de disponibilidade.")
    if db.get(Category, data.category_id) is None:
        raise invalid("category_id", "Categoria desconhecida.")
    if any(
        getattr(data, key) is None
        for key in (
            "pickup_cep",
            "pickup_street",
            "pickup_number",
            "pickup_neighborhood",
            "pickup_city",
            "pickup_state",
        )
    ):
        raise invalid("pickup", "Informe o endereço de retirada completo.")

    tags = form.getlist("tags[]") if "tags[]" in form else None
    if tags == [""]:
        tags = []
    normalized = []
    if tags is not None:
        if len(tags) > 5 or any(
            not isinstance(tag, str) or not tag.strip() or len(tag.strip()) > 30 for tag in tags
        ):
            raise invalid("tags", "Informe até 5 tags de até 30 caracteres.")
        normalized = [
            db.scalar(select(func.lower(func.public.immutable_unaccent(tag.strip()))))
            for tag in tags
        ]
        if len(set(normalized)) != len(normalized):
            raise invalid("tags", "Tags duplicadas não são permitidas.")

    changing_photos = "keep_photo_ids[]" in form or "photos[]" in form
    current = db.execute(
        select(ListingPhoto.id, ListingPhoto.filename)
        .where(ListingPhoto.listing_id == listing.id)
        .order_by(ListingPhoto.position)
    ).all()
    photos = form.getlist("photos[]") if changing_photos else []
    if any(not isinstance(photo, UploadFile) for photo in photos):
        raise invalid("photos", "Envie arquivos de imagem válidos.")
    try:
        keep_ids = [int(value) for value in form.getlist("keep_photo_ids[]")]
    except (ValueError, TypeError):
        raise invalid("keep_photo_ids", "Identificador de foto inválido.") from None
    lookup = {row.id: row.filename for row in current}
    if len(set(keep_ids)) != len(keep_ids) or any(photo_id not in lookup for photo_id in keep_ids):
        raise invalid("keep_photo_ids", "Selecione fotos pertencentes ao anúncio, sem repetições.")
    retained = (
        [(photo_id, lookup[photo_id]) for photo_id in keep_ids]
        if changing_photos
        else [tuple(row) for row in current]
    )
    upload_dir, max_bytes, max_photos = _settings()
    if not 1 <= len(retained) + len(photos) <= max_photos:
        raise invalid("photos", f"Envie entre 1 e {max_photos} imagens.")

    blocked = db.scalar(
        select(Rental.id)
        .where(
            Rental.listing_id == listing.id,
            Rental.status == "accepted",
            Rental.end_date >= today_br(),
            or_(Rental.start_date < data.available_from, Rental.end_date > data.available_until),
        )
        .limit(1)
    )
    if blocked is not None:
        raise ApiError(
            status_code=409,
            code="LISTING_HAS_ACTIVE_RENTAL",
            message="A janela não comporta um aluguel aceito.",
        )

    # Stage new files first, then persist database and files with compensation on failure.
    upload_dir.mkdir(parents=True, exist_ok=True)
    moved: list[Path] = []
    try:
        with tempfile.TemporaryDirectory(prefix=".listing-photos-", dir=upload_dir) as tmp:
            staged = []
            for photo in photos:
                content = _read_file(photo.file, max_bytes)
                image_format = _detect_format(content)
                filename = f"{uuid.uuid4()}{_ALLOWED_FORMATS[image_format]}"
                temporary_path = Path(tmp) / filename
                _sanitize_image(content, image_format, temporary_path)
                staged.append((temporary_path, filename))
            for key in changes:
                setattr(listing, key, getattr(data, key))
            listing.updated_at = datetime.now(UTC)
            if tags is not None:
                db.execute(delete(listing_tags).where(listing_tags.c.listing_id == listing.id))
                for tag, name in zip(tags, normalized, strict=True):
                    db.execute(
                        insert(Tag)
                        .values(name=tag.strip(), normalized_name=name)
                        .on_conflict_do_nothing(index_elements=["normalized_name"])
                    )
                    tag_id = db.scalar(select(Tag.id).where(Tag.normalized_name == name))
                    db.execute(insert(listing_tags).values(listing_id=listing.id, tag_id=tag_id))
            if changing_photos:
                db.execute(delete(ListingPhoto).where(ListingPhoto.listing_id == listing.id))
                for position, (photo_id, filename) in enumerate(retained, start=1):
                    db.execute(
                        insert(ListingPhoto).values(
                            id=photo_id, listing_id=listing.id, position=position, filename=filename
                        )
                    )
                for position, (temporary_path, filename) in enumerate(
                    staged, start=len(retained) + 1
                ):
                    db.add(
                        ListingPhoto(listing_id=listing.id, position=position, filename=filename)
                    )
                    destination = upload_dir / filename
                    os.replace(temporary_path, destination)
                    moved.append(destination)
            db.commit()
    except Exception:
        db.rollback()
        for path in moved:
            path.unlink(missing_ok=True)
        raise

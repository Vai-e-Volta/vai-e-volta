from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.errors import ApiError
from app.models import Category, Listing, Tag, User, listing_tags
from app.schemas.listings import CategoryResponse, ListingCreate, ListingCreated
from app.services.listing_photos import store_listing_photos
from app.services.rental_situation import today_br

router = APIRouter(tags=["listings"])


def invalid(field: str, message: str) -> ApiError:
    return ApiError(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Revise os campos informados.",
        fields={field: message},
    )


@router.get("/api/categories", response_model=list[CategoryResponse])
def categories(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[CategoryResponse]:
    return [
        CategoryResponse(id=c.id, name=c.name)
        for c in db.scalars(select(Category).order_by(Category.id))
    ]


@router.post(
    "/api/listings",
    response_model=ListingCreated,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": [
                            "title",
                            "description",
                            "daily_price",
                            "max_days",
                            "available_from",
                            "available_until",
                            "category_id",
                            "photos[]",
                        ],
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "daily_price": {"type": "string"},
                            "max_days": {"type": "integer"},
                            "available_from": {"type": "string", "format": "date"},
                            "available_until": {"type": "string", "format": "date"},
                            "category_id": {"type": "integer"},
                            "pickup_cep": {"type": "string"},
                            "pickup_street": {"type": "string"},
                            "pickup_number": {"type": "string"},
                            "pickup_complement": {"type": "string"},
                            "pickup_neighborhood": {"type": "string"},
                            "pickup_city": {"type": "string"},
                            "pickup_state": {"type": "string"},
                            "tags[]": {"type": "array", "items": {"type": "string"}},
                            "photos[]": {
                                "type": "array",
                                "items": {"type": "string", "format": "binary"},
                            },
                        },
                    }
                }
            },
        }
    },
)
async def create_listing(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ListingCreated:
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "multipart/form-data"
    ):
        raise ApiError(
            status_code=415, code="UNSUPPORTED_MEDIA_TYPE", message="Use multipart/form-data."
        )
    form = await request.form()
    tags = form.getlist("tags[]")
    photos = form.getlist("photos[]")
    scalars = {key: form.get(key) for key in form.keys() if key not in {"tags[]", "photos[]"}}
    if any(len(form.getlist(key)) != 1 for key in scalars):
        raise invalid("body", "Campo repetido.")
    try:
        data = ListingCreate.model_validate(scalars)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from None
    if data.available_from > data.available_until:
        raise invalid("available_until", "A data final deve ser posterior à inicial.")
    if data.available_until < today_br():
        raise invalid("available_until", "A data final não pode estar no passado.")
    if data.max_days > (data.available_until - data.available_from).days + 1:
        raise invalid("max_days", "O prazo excede a janela de disponibilidade.")
    if db.get(Category, data.category_id) is None:
        raise invalid("category_id", "Categoria desconhecida.")
    if len(tags) > 5 or any(
        not isinstance(tag, str) or not tag.strip() or len(tag.strip()) > 30 for tag in tags
    ):
        raise invalid("tags", "Informe até 5 tags de até 30 caracteres.")
    if any(not isinstance(photo, UploadFile) for photo in photos):
        raise invalid("photos", "Envie arquivos de imagem válidos.")
    normalized = [
        db.scalar(select(func.lower(func.public.immutable_unaccent(tag.strip())))) for tag in tags
    ]
    if len(set(normalized)) != len(normalized):
        raise invalid("tags", "Tags duplicadas não são permitidas.")
    values = data.model_dump(exclude_unset=True)
    for field in ("cep", "street", "number", "complement", "neighborhood", "city", "state"):
        values.setdefault(f"pickup_{field}", getattr(user, field))
    listing = Listing(owner_id=user.id, **values)
    db.add(listing)
    db.flush()
    for tag, name in zip(tags, normalized, strict=True):
        db.execute(
            insert(Tag)
            .values(name=tag.strip(), normalized_name=name)
            .on_conflict_do_nothing(index_elements=["normalized_name"])
        )
        tag_id = db.scalar(select(Tag.id).where(Tag.normalized_name == name))
        db.execute(insert(listing_tags).values(listing_id=listing.id, tag_id=tag_id))
    store_listing_photos(db, listing.id, [photo.file for photo in photos])
    return ListingCreated(id=listing.id)

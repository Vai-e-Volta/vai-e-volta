"""Populate a development database with repeatable, fictitious demonstration data."""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_engine
from app.models import Category, Listing, ListingPhoto, Rental, Tag, User, listing_tags
from app.security.registration import registration_security
from app.services.rental_situation import today_br

_NAMESPACE = uuid.UUID("5c0f0d32-3b78-56dd-90d7-8852ff7fef12")
_LISTING_BASE = 8_100_000_000_000_000
_RENTAL_BASE = 8_200_000_000_000_000
_PASSWORD = "Dev@12345"
_USERS = (
    ("ana_silva", "Ana Silva", "ana.silva@exemplo.test", "11144477735", "53991110001", "Centro"),
    (
        "bruno_costa",
        "Bruno Costa",
        "bruno.costa@exemplo.test",
        "12345678909",
        "53991110002",
        "Cassino",
    ),
    (
        "carla_souza",
        "Carla Souza",
        "carla.souza@exemplo.test",
        "24681357928",
        "53991110003",
        "Cidade Nova",
    ),
    (
        "diego_lima",
        "Diego Lima",
        "diego.lima@exemplo.test",
        "13579246828",
        "53991110004",
        "Parque Marinha",
    ),
    (
        "elisa_rocha",
        "Elisa Rocha",
        "elisa.rocha@exemplo.test",
        "98765432100",
        "53991110005",
        "Centro",
    ),
)
_LISTINGS = (
    ("Furadeira de impacto", "Ferramentas", "obra"),
    ("Parafusadeira elétrica", "Ferramentas", "reforma"),
    ("Serra tico-tico", "Ferramentas", "marcenaria"),
    ("Lavadora de alta pressão", "Casa e jardim", "limpeza"),
    ("Escada dobrável", "Casa e jardim", "reforma"),
    ("Projetor portátil", "Eletrônicos", "apresentação"),
    ("Câmera fotográfica", "Eletrônicos", "fotografia"),
    ("Caixa de som", "Eletrônicos", "música"),
    ("Barraca para camping", "Esportes e lazer", "camping"),
    ("Bicicleta de passeio", "Esportes e lazer", "passeio"),
    ("Kit de jardinagem", "Casa e jardim", "jardinagem"),
    ("Mesa dobrável", "Festas e jogos", "eventos"),
    ("Jogo de tabuleiro", "Festas e jogos", "jogos"),
    ("Tripé para câmera", "Equipamentos", "fotografia"),
    ("Caixa térmica", "Esportes e lazer", "camping"),
)


def _user_id(username: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, f"user:{username}")


def _photo_name(index: int) -> str:
    return f"{uuid.uuid5(_NAMESPACE, f'photo:{index}')}.png"


def _create_demo_image(path: Path, title: str, index: int) -> None:
    """Create a clearly labeled illustrative image without external assets."""
    colors = ((38, 88, 101), (75, 67, 112), (88, 89, 52), (114, 66, 50))
    image = Image.new("RGB", (640, 480), colors[index % len(colors)])
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((45, 55, 595, 425), radius=28, fill=(238, 241, 237))
    draw.rounded_rectangle((70, 80, 570, 315), radius=18, fill=(199, 212, 211))
    draw.text((95, 140), "VAI E VOLTA", fill=(35, 57, 59), font=ImageFont.load_default(size=32))
    draw.text((95, 205), title, fill=(35, 57, 59), font=ImageFont.load_default(size=24))
    draw.text(
        (70, 355), "IMAGEM DE DEMONSTRAÇÃO", fill=(61, 74, 72), font=ImageFont.load_default(size=20)
    )
    # Do not leave a truncated final image if encoding or the process fails.
    with tempfile.NamedTemporaryFile(
        prefix=".seed-", suffix=".png", dir=path.parent, delete=False
    ) as file:
        temporary_path = Path(file.name)
    try:
        image.save(temporary_path, format="PNG")
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def seed_demo(session: Session, now: datetime | None = None) -> None:
    """Create missing demo data once without changing existing records."""
    if settings.APP_ENV != "dev":
        raise RuntimeError("Dados de demonstração só podem ser criados em APP_ENV=dev")
    instant = now or datetime.now(UTC)
    today = today_br(instant)
    upload_dir = Path(settings.UPLOAD_DIR)
    created_paths: list[Path] = []
    try:
        # Prevent concurrent seed runs from creating duplicate data or files.
        session.execute(text("SELECT pg_advisory_xact_lock(418060901)"))
        category_ids = dict(session.execute(select(Category.name, Category.id)).all())
        if any(category not in category_ids for _, category, _ in _LISTINGS):
            raise RuntimeError("Categorias ausentes; aplique as migrações antes do seed")

        users: dict[str, User] = {}
        for username, full_name, email, cpf, phone, neighborhood in _USERS:
            user_id = _user_id(username)
            user = session.get(User, user_id)
            if user is None:
                user = User(
                    id=user_id,
                    full_name=full_name,
                    username=username,
                    email=email,
                    cpf=cpf,
                    phone=phone,
                    password_hash=registration_security.hash_password(_PASSWORD),
                    cep="96200000",
                    street="Rua Exemplo",
                    number="100",
                    complement=None,
                    neighborhood=neighborhood,
                    city="Rio Grande",
                    state="RS",
                    deleted_at=instant - timedelta(days=10) if username == "elisa_rocha" else None,
                    purge_after=instant + timedelta(days=355)
                    if username == "elisa_rocha"
                    else None,
                )
                session.add(user)
            users[username] = user
        session.flush()
        upload_dir.mkdir(parents=True, exist_ok=True)
        seeded_listings: list[Listing] = []
        for index, (title, category, tag_name) in enumerate(_LISTINGS):
            listing_id = _LISTING_BASE + index
            listing = session.get(Listing, listing_id)
            if listing is None:
                owner = users["ana_silva" if index % 2 == 0 else "bruno_costa"]
                listing = Listing(
                    id=listing_id,
                    owner_id=owner.id,
                    category_id=category_ids[category],
                    title=title,
                    description=f"{title} para demonstração do Vai e Volta.",
                    daily_price=Decimal(10 + index * 5),
                    max_days=30,
                    available_from=today - timedelta(days=120),
                    available_until=today + timedelta(days=120),
                    pickup_cep=owner.cep,
                    pickup_street=owner.street,
                    pickup_number=owner.number,
                    pickup_complement=owner.complement,
                    pickup_neighborhood=owner.neighborhood,
                    pickup_city=owner.city,
                    pickup_state=owner.state,
                )
                session.add(listing)
                session.flush()
                normalized = session.scalar(
                    select(text("lower(public.immutable_unaccent(:tag))")).params(tag=tag_name)
                )
                session.execute(
                    insert(Tag)
                    .values(name=tag_name, normalized_name=normalized)
                    .on_conflict_do_nothing(index_elements=["normalized_name"])
                )
                tag_id = session.scalar(select(Tag.id).where(Tag.normalized_name == normalized))
                session.execute(insert(listing_tags).values(listing_id=listing_id, tag_id=tag_id))
                filename = _photo_name(index)
                session.add(ListingPhoto(listing_id=listing_id, position=1, filename=filename))
            else:
                # Do not change existing listings, even if a developer edited them.
                expected_owner = users["ana_silva" if index % 2 == 0 else "bruno_costa"]
                if listing.owner_id != expected_owner.id:
                    raise RuntimeError("Um identificador de anúncio de demonstração já está em uso")
                filename = session.scalar(
                    select(ListingPhoto.filename).where(
                        ListingPhoto.listing_id == listing_id, ListingPhoto.position == 1
                    )
                )
            if filename == _photo_name(index):
                path = upload_dir / filename
                if not path.exists():
                    _create_demo_image(path, title, index)
                    created_paths.append(path)
            seeded_listings.append(listing)
        session.flush()

        scenarios = (
            ("carla_souza", "pending", 5, 7),
            ("diego_lima", "accepted", 3, 6),
            ("carla_souza", "accepted", -1, 2),
            ("carla_souza", "accepted", -9, -5),
            ("elisa_rocha", "completed", -20, -17),
        )
        for index, (username, rental_status, start_offset, end_offset) in enumerate(scenarios):
            rental_id = _RENTAL_BASE + index
            if session.get(Rental, rental_id) is not None:
                continue
            listing = seeded_listings[index]
            start, end = today + timedelta(days=start_offset), today + timedelta(days=end_offset)
            price = listing.daily_price
            photo_names = list(
                session.scalars(
                    select(ListingPhoto.filename)
                    .where(ListingPhoto.listing_id == listing.id)
                    .order_by(ListingPhoto.position)
                )
            )
            tag_names = list(
                session.scalars(
                    select(Tag.name)
                    .join(listing_tags, listing_tags.c.tag_id == Tag.id)
                    .where(listing_tags.c.listing_id == listing.id)
                    .order_by(Tag.name)
                )
            )
            category_name = session.scalar(
                select(Category.name).where(Category.id == listing.category_id)
            )
            snapshot = {
                "title": listing.title,
                "description": listing.description,
                "daily_price": str(price),
                "max_days": listing.max_days,
                "category_id": listing.category_id,
                "category": category_name,
                "tags": tag_names,
                "photos": photo_names,
                "pickup_cep": listing.pickup_cep,
                "pickup_street": listing.pickup_street,
                "pickup_number": listing.pickup_number,
                "pickup_complement": listing.pickup_complement,
                "pickup_neighborhood": listing.pickup_neighborhood,
                "pickup_city": listing.pickup_city,
                "pickup_state": listing.pickup_state,
            }
            created_at = instant - (
                timedelta(hours=1)
                if rental_status == "pending"
                else timedelta(days=max(1, -start_offset + 2))
            )
            session.add(
                Rental(
                    id=rental_id,
                    listing_id=listing.id,
                    renter_id=users[username].id,
                    start_date=start,
                    end_date=end,
                    status=rental_status,
                    daily_price_snapshot=price,
                    estimated_total=price * ((end - start).days + 1),
                    listing_snapshot=snapshot,
                    created_at=created_at,
                    expires_at=created_at + timedelta(hours=48),
                    returned_on=end if rental_status == "completed" else None,
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        for path in created_paths:
            path.unlink(missing_ok=True)
        raise


def main() -> None:
    if settings.APP_ENV != "dev":
        raise SystemExit("Dados de demonstração só podem ser criados em APP_ENV=dev")
    with Session(get_engine(), expire_on_commit=False) as session:
        seed_demo(session)
    print("Dados de demonstração disponíveis.")


if __name__ == "__main__":
    main()

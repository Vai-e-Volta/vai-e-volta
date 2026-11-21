from __future__ import annotations

import os
import tempfile
import uuid
import warnings
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.models import ListingPhoto

_ALLOWED_FORMATS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}

_SIGNATURES = {
    "JPEG": lambda data: data.startswith(b"\xff\xd8\xff"),
    "PNG": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "WEBP": lambda data: len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP",
}


def _settings() -> tuple[Path, int, int]:
    upload_dir = Path(os.environ.get("UPLOAD_DIR", "/data/uploads"))
    max_upload_mb = int(os.environ.get("MAX_UPLOAD_MB", "5"))
    max_photos = int(os.environ.get("MAX_PHOTOS", "5"))

    if max_upload_mb < 1 or not 1 <= max_photos <= 5:
        raise RuntimeError("Configuração inválida para upload de fotos.")

    return upload_dir, max_upload_mb * 1024 * 1024, max_photos


def _read_file(file: BinaryIO, max_bytes: int) -> bytes:
    file.seek(0)
    content = file.read(max_bytes + 1)

    if len(content) > max_bytes:
        raise ApiError(
            status_code=413,
            code="FILE_TOO_LARGE",
            message="Uma das imagens excede o tamanho máximo permitido.",
            fields={},
        )

    return content


def _detect_format(content: bytes) -> str:
    for image_format, signature_check in _SIGNATURES.items():
        if signature_check(content):
            return image_format

    raise ApiError(
        status_code=415,
        code="UNSUPPORTED_MEDIA",
        message="Formato de imagem não suportado. Use JPEG, PNG ou WebP.",
        fields={},
    )


def _sanitize_image(content: bytes, expected_format: str, destination: Path) -> None:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            with Image.open(BytesIO(content)) as image:
                if image.format != expected_format:
                    raise ValueError("Assinatura e formato divergentes.")

                image.verify()

            with Image.open(BytesIO(content)) as image:
                if image.format != expected_format:
                    raise ValueError("Assinatura e formato divergentes.")

                image.load()
                image = ImageOps.exif_transpose(image)

                if expected_format == "JPEG":
                    image = image.convert("RGB")
                elif expected_format == "WEBP":
                    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

                image.save(destination, format=expected_format)

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        raise ApiError(
            status_code=415,
            code="UNSUPPORTED_MEDIA",
            message="O arquivo enviado não contém uma imagem válida.",
            fields={},
        ) from error


def store_listing_photos(
    db: Session,
    listing_id: int,
    files: Sequence[BinaryIO],
) -> list[ListingPhoto]:
    """Validate, sanitize and persist listing photos, with filesystem compensation."""
    upload_dir, max_bytes, max_photos = _settings()

    if not 1 <= len(files) <= max_photos:
        raise ApiError(
            status_code=422,
            code="VALIDATION_ERROR",
            message=f"Envie entre 1 e {max_photos} imagens.",
            fields={"photos": f"Envie entre 1 e {max_photos} imagens."},
        )

    upload_dir.mkdir(parents=True, exist_ok=True)
    final_paths: list[Path] = []
    photos: list[ListingPhoto] = []

    try:
        with tempfile.TemporaryDirectory(prefix=".listing-photos-", dir=upload_dir) as temp_dir:
            temporary_dir = Path(temp_dir)

            for position, file in enumerate(files, start=1):
                content = _read_file(file, max_bytes)
                image_format = _detect_format(content)
                filename = f"{uuid.uuid4()}{_ALLOWED_FORMATS[image_format]}"
                temporary_path = temporary_dir / filename

                _sanitize_image(content, image_format, temporary_path)

                photos.append(
                    ListingPhoto(
                        listing_id=listing_id,
                        position=position,
                        filename=filename,
                    )
                )

            db.add_all(photos)
            db.flush()

            for photo in photos:
                temporary_path = temporary_dir / photo.filename
                final_path = upload_dir / photo.filename
                os.replace(temporary_path, final_path)
                final_paths.append(final_path)

            db.commit()

    except Exception:
        db.rollback()

        for path in final_paths:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

        raise

    return photos

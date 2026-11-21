from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.errors import ApiError
from app.services.listing_photos import store_listing_photos


def _image_file(image_format: str, **save_options: Any) -> BytesIO:
    """Create a small valid image in memory."""
    image = Image.new("RGB", (10, 10), color="red")
    file = BytesIO()
    image.save(file, format=image_format, **save_options)
    file.seek(0)
    return file


def test_stores_supported_formats_and_preserves_photo_order(
    db: Connection,
    insert_listing: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listing_id = insert_listing()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))

    files = [
        _image_file("JPEG"),
        _image_file("PNG"),
        _image_file("WEBP"),
    ]

    with Session(bind=db, expire_on_commit=False) as session:
        photos = store_listing_photos(session, listing_id, files)

    assert len(photos) == 3
    assert [photo.position for photo in photos] == [1, 2, 3]

    expected_extensions = [".jpg", ".png", ".webp"]
    for photo, extension in zip(photos, expected_extensions, strict=True):
        assert Path(photo.filename).suffix == extension
        assert (tmp_path / photo.filename).is_file()

    rows = db.execute(
        text(
            "SELECT position, filename FROM listing_photos "
            "WHERE listing_id = :listing_id ORDER BY position"
        ),
        {"listing_id": listing_id},
    ).all()

    assert [row.position for row in rows] == [1, 2, 3]
    assert [row.filename for row in rows] == [photo.filename for photo in photos]


def test_removes_exif_metadata_from_stored_photo(
    db: Connection,
    insert_listing: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listing_id = insert_listing()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))

    image = Image.new("RGB", (10, 10), color="red")
    exif = Image.Exif()
    exif[270] = "Metadados de teste"

    source_file = BytesIO()
    image.save(source_file, format="JPEG", exif=exif)
    source_file.seek(0)

    with Session(bind=db, expire_on_commit=False) as session:
        photos = store_listing_photos(session, listing_id, [source_file])

    stored_path = tmp_path / photos[0].filename

    with Image.open(stored_path) as stored_image:
        assert stored_image.getexif() == {}


@pytest.mark.parametrize("photo_count", [0, 6])
def test_rejects_invalid_photo_count(
    db: Connection,
    insert_listing: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    photo_count: int,
) -> None:
    listing_id = insert_listing()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))

    files = [_image_file("JPEG") for _ in range(photo_count)]

    with Session(bind=db, expire_on_commit=False) as session:
        with pytest.raises(ApiError) as error:
            store_listing_photos(session, listing_id, files)

    assert error.value.status_code == 422
    assert error.value.code == "VALIDATION_ERROR"
    assert list(tmp_path.iterdir()) == []


def test_rejects_unsupported_file_content(
    db: Connection,
    insert_listing: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listing_id = insert_listing()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))

    invalid_file = BytesIO(b"this is not an image")

    with Session(bind=db, expire_on_commit=False) as session:
        with pytest.raises(ApiError) as error:
            store_listing_photos(session, listing_id, [invalid_file])

    assert error.value.status_code == 415
    assert error.value.code == "UNSUPPORTED_MEDIA"
    assert list(tmp_path.iterdir()) == []


def test_rejects_file_with_valid_signature_but_invalid_image_content(
    db: Connection,
    insert_listing: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listing_id = insert_listing()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))

    invalid_file = BytesIO(b"\xff\xd8\xff" + b"not a valid JPEG image")

    with Session(bind=db, expire_on_commit=False) as session:
        with pytest.raises(ApiError) as error:
            store_listing_photos(session, listing_id, [invalid_file])

    assert error.value.status_code == 415
    assert error.value.code == "UNSUPPORTED_MEDIA"
    assert list(tmp_path.iterdir()) == []


def test_rejects_file_above_configured_size_limit(
    db: Connection,
    insert_listing: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listing_id = insert_listing()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")

    oversized_file = BytesIO(b"\xff\xd8\xff" + b"x" * (1024 * 1024))

    with Session(bind=db, expire_on_commit=False) as session:
        with pytest.raises(ApiError) as error:
            store_listing_photos(session, listing_id, [oversized_file])

    assert error.value.status_code == 413
    assert error.value.code == "FILE_TOO_LARGE"
    assert list(tmp_path.iterdir()) == []


def test_removes_moved_files_when_database_commit_fails(
    db: Connection,
    insert_listing: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listing_id = insert_listing()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))

    def fail_commit(session: Session) -> None:
        raise RuntimeError("Simulated database commit failure")

    monkeypatch.setattr(Session, "commit", fail_commit)

    with Session(
        bind=db,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ) as session:
        with pytest.raises(RuntimeError, match="Simulated database commit failure"):
            store_listing_photos(session, listing_id, [_image_file("JPEG")])

    assert list(tmp_path.iterdir()) == []

    photo_count = db.execute(
        text("SELECT COUNT(*) FROM listing_photos WHERE listing_id = :listing_id"),
        {"listing_id": listing_id},
    ).scalar_one()

    assert photo_count == 0


def test_removes_already_moved_files_when_file_move_fails(
    db: Connection,
    insert_listing: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.listing_photos as listing_photos_service

    listing_id = insert_listing()
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))

    original_replace = listing_photos_service.os.replace
    calls = 0

    def fail_second_replace(source: Any, destination: Any) -> None:
        nonlocal calls
        calls += 1

        if calls == 2:
            raise OSError("Falha simulada na movimentação.")

        original_replace(source, destination)

    monkeypatch.setattr(listing_photos_service.os, "replace", fail_second_replace)

    with Session(
        bind=db,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ) as session:
        with pytest.raises(OSError, match="Falha simulada na movimentação"):
            store_listing_photos(
                session,
                listing_id,
                [_image_file("JPEG"), _image_file("PNG")],
            )

    assert calls == 2
    assert list(tmp_path.iterdir()) == []

    rows = db.execute(
        text("SELECT id FROM listing_photos WHERE listing_id = :listing_id"),
        {"listing_id": listing_id},
    ).all()

    assert rows == []

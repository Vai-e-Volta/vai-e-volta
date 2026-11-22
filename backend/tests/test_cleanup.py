from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.worker.tasks import cleanup


def test_cleanup_preserves_referenced_photos_and_recent_files(
    db: Connection, insert_listing, insert_rental, monkeypatch, tmp_path: Path
) -> None:
    now = datetime.now(UTC)
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    names = [f"{uuid.uuid4()}.png" for _ in range(7)]
    old_time = (now - timedelta(days=2)).timestamp()
    for name in names:
        path = tmp_path / name
        path.write_bytes(b"fixture")
        os.utime(path, (old_time, old_time))
    os.utime(tmp_path / names[5], (now.timestamp(), now.timestamp()))
    (tmp_path / "not-an-upload.txt").write_text("keep", encoding="utf-8")

    listing = insert_listing()
    db.execute(
        text("INSERT INTO listing_photos (listing_id, position, filename) VALUES (:id, 1, :name)"),
        {"id": listing, "name": names[0]},
    )
    insert_rental(listing_id=listing, listing_snapshot=json.dumps({"photos": [names[1]]}))
    insert_rental(
        listing_id=listing,
        status="accepted",
        listing_snapshot=json.dumps({"photos": [{"filename": names[2]}]}),
    )
    insert_rental(
        listing_id=insert_listing(),
        status="completed",
        listing_snapshot=json.dumps({"photos": [names[3]]}),
    )
    db.execute(
        text(
            "INSERT INTO login_attempts (identifier_hash, attempted_at, success) "
            "VALUES (:hash, :time, false)"
        ),
        [
            {"hash": "a" * 64, "time": now - timedelta(days=2)},
            {"hash": "b" * 64, "time": now - timedelta(hours=1)},
        ],
    )

    with Session(bind=db) as session:
        cleanup(session, now)
        cleanup(session, now)
        session.flush()
        assert (
            db.scalar(
                text("SELECT count(*) FROM login_attempts WHERE identifier_hash = :h"),
                {"h": "a" * 64},
            )
            == 0
        )
        assert (
            db.scalar(
                text("SELECT count(*) FROM login_attempts WHERE identifier_hash = :h"),
                {"h": "b" * 64},
            )
            == 1
        )
    for index in (0, 1, 2, 5):
        assert (tmp_path / names[index]).exists()
    for index in (3, 4, 6):
        assert not (tmp_path / names[index]).exists()
    assert (tmp_path / "not-an-upload.txt").exists()

"""Tasks of the worker.

Each task module registers its functions in ``app.worker.registry.registry`` and is imported
here, so the scheduler sees every task. Upcoming tasks: H018-2 (expire proposals), H023-3
(calendar notices), H005-4 (anonymization) and H006-5 (cleanup).
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.models import ListingPhoto, LoginAttempt, Rental
from app.worker.registry import registry


@registry.register("heartbeat", seconds=30)
def heartbeat(session: Session, _now: datetime) -> None:
    """Checks the database connection; the runner refreshes the heartbeat file afterwards."""
    session.execute(text("SELECT 1"))


_PHOTO_FILENAME = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(?:jpg|png|webp)$"
)


def _snapshot_strings(value: Any) -> set[str]:
    """Conservatively retain every string in a stored snapshot, including nested photos."""
    if isinstance(value, str):
        return {value}
    if isinstance(value, list):
        return set().union(*(_snapshot_strings(item) for item in value))
    if isinstance(value, dict):
        return set().union(*(_snapshot_strings(item) for item in value.values()))
    return set()


@registry.register("cleanup", hours=24)
def cleanup(session: Session, now: datetime) -> None:
    """Remove old login attempts and orphaned, fully written listing photos."""
    session.execute(delete(LoginAttempt).where(LoginAttempt.attempted_at < now - timedelta(days=1)))
    upload_dir = Path(os.environ.get("UPLOAD_DIR", "/data/uploads"))
    if not upload_dir.is_dir():
        return

    # Prevent committed photo or rental references from changing while checking the files.
    session.execute(text("LOCK TABLE listing_photos, rentals IN SHARE MODE"))
    referenced = set(session.scalars(select(ListingPhoto.filename)))
    for snapshot in session.scalars(
        select(Rental.listing_snapshot).where(Rental.status.in_(("pending", "accepted")))
    ):
        referenced.update(_snapshot_strings(snapshot))

    cutoff = (now - timedelta(days=1)).timestamp()
    for path in upload_dir.iterdir():
        if not _PHOTO_FILENAME.fullmatch(path.name) or path.name in referenced:
            continue
        try:
            # A grace period protects files created by another still-running upload.
            if path.is_file() and not path.is_symlink() and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except FileNotFoundError:
            continue

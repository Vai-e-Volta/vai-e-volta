"""Container healthcheck: fails when the heartbeat is missing or older than 120 seconds."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from app.worker.runner import HEARTBEAT_PATH

MAX_AGE_SECONDS = 120


def is_healthy(path: Path = HEARTBEAT_PATH, *, now: float | None = None) -> bool:
    try:
        modified = path.stat().st_mtime
    except FileNotFoundError:
        return False
    return ((time.time() if now is None else now) - modified) <= MAX_AGE_SECONDS


if __name__ == "__main__":
    sys.exit(0 if is_healthy() else 1)

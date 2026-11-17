"""Runs one cycle of a task with a PostgreSQL advisory lock and updates the heartbeat."""

from __future__ import annotations

import hashlib
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.worker.registry import Job

logger = logging.getLogger("app.worker")

HEARTBEAT_PATH = Path("/tmp/worker_heartbeat")
Clock = Callable[[], datetime]


class RunStatus(StrEnum):
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


def utc_now() -> datetime:
    return datetime.now(UTC)


def advisory_lock_key(job_name: str) -> int:
    """Stable signed 64-bit key for ``pg_try_advisory_lock``, derived from the job name."""
    digest = hashlib.sha256(f"vai-e-volta:worker:{job_name}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def touch_heartbeat(path: Path = HEARTBEAT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def run_job(
    job: Job,
    engine: Engine,
    *,
    clock: Clock = utc_now,
    heartbeat_path: Path = HEARTBEAT_PATH,
) -> RunStatus:
    """Run one cycle of ``job``.

    The cycle is skipped when another instance holds the advisory lock of the job, so two
    workers never run the same task at the same time. The task runs in a single
    transaction: on error it is rolled back, logged, and the next cycle tries again.
    """
    started = time.monotonic()
    key = advisory_lock_key(job.name)
    status = RunStatus.SKIPPED
    try:
        with engine.connect() as connection:
            acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key})
            connection.commit()
            if not acquired:
                logger.info(
                    "job skipped: lock held by another instance",
                    extra={"job": job.name, "status": RunStatus.SKIPPED.value},
                )
                return RunStatus.SKIPPED
            try:
                with Session(bind=connection) as session:
                    try:
                        job.function(session, clock())
                        session.commit()
                        status = RunStatus.COMPLETED
                    except Exception as error:
                        session.rollback()
                        status = RunStatus.FAILED
                        logger.error(
                            "job failed",
                            extra={
                                "job": job.name,
                                "status": status.value,
                                "error": type(error).__name__,
                            },
                        )
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
                connection.commit()
    except Exception as error:
        status = RunStatus.FAILED
        logger.error(
            "job cycle failed",
            extra={"job": job.name, "status": status.value, "error": type(error).__name__},
        )
        return status
    finally:
        touch_heartbeat(heartbeat_path)

    if status is RunStatus.COMPLETED:
        logger.info(
            "job completed",
            extra={
                "job": job.name,
                "status": status.value,
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )
    return status

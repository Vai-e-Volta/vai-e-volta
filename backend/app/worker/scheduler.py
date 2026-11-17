from __future__ import annotations

from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import Engine

from app.worker.registry import JobRegistry
from app.worker.runner import HEARTBEAT_PATH, run_job, utc_now


def build_scheduler(
    registry: JobRegistry,
    engine: Engine,
    *,
    heartbeat_path: Path = HEARTBEAT_PATH,
) -> BlockingScheduler:
    """Schedule every registered task, starting now; one running instance per task."""
    scheduler = BlockingScheduler(timezone="UTC")
    for job in registry:
        scheduler.add_job(
            run_job,
            trigger=IntervalTrigger(seconds=job.interval_seconds, timezone="UTC"),
            args=[job, engine],
            kwargs={"heartbeat_path": heartbeat_path},
            id=job.name,
            name=job.name,
            max_instances=1,
            coalesce=True,
            next_run_time=utc_now(),
        )
    return scheduler

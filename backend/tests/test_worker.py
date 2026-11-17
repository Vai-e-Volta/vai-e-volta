"""H018-1: worker base (advisory lock, heartbeat, registry, JSON logs)."""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.migrations import upgrade_database
from app.worker import tasks
from app.worker.healthcheck import MAX_AGE_SECONDS, is_healthy
from app.worker.logging import JsonFormatter
from app.worker.registry import JobRegistry, registry
from app.worker.runner import RunStatus, advisory_lock_key, run_job
from app.worker.scheduler import build_scheduler

FROZEN_NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


@pytest.fixture
def engine() -> Generator[Engine, None, None]:
    upgrade_database()
    engine = create_engine(os.environ["DATABASE_URL"])
    yield engine
    engine.dispose()


@pytest.fixture
def heartbeat(tmp_path: Path) -> Path:
    return tmp_path / "worker_heartbeat"


def _registry_with(function, name: str = "test_job") -> JobRegistry:
    test_registry = JobRegistry()
    test_registry.register(name, minutes=1)(function)
    return test_registry


def test_JOB_lock_skips_cycle_when_another_instance_holds_it(
    engine: Engine, heartbeat: Path
) -> None:
    calls: list[datetime] = []
    job = _registry_with(lambda _session, now: calls.append(now)).get("test_job")

    with engine.connect() as other_instance:
        assert other_instance.scalar(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": advisory_lock_key(job.name)}
        )
        try:
            status = run_job(job, engine, clock=lambda: FROZEN_NOW, heartbeat_path=heartbeat)
        finally:
            other_instance.execute(
                text("SELECT pg_advisory_unlock(:k)"), {"k": advisory_lock_key(job.name)}
            )
            other_instance.commit()

    assert status is RunStatus.SKIPPED
    assert calls == []
    assert heartbeat.exists()

    assert run_job(job, engine, clock=lambda: FROZEN_NOW, heartbeat_path=heartbeat) is (
        RunStatus.COMPLETED
    )
    assert calls == [FROZEN_NOW]


def test_JOB_lock_is_released_after_success_and_failure(engine: Engine, heartbeat: Path) -> None:
    def failing(_session: Session, _now: datetime) -> None:
        raise RuntimeError("boom")

    for function, expected in (
        (lambda _s, _n: None, RunStatus.COMPLETED),
        (failing, RunStatus.FAILED),
    ):
        job = _registry_with(function).get("test_job")
        assert run_job(job, engine, heartbeat_path=heartbeat) is expected
        with engine.connect() as connection:
            key = advisory_lock_key(job.name)
            assert connection.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": key})
            connection.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
            connection.commit()


def test_JOB_failed_cycle_is_rolled_back(engine: Engine, heartbeat: Path) -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE IF NOT EXISTS worker_test_marks (value int)"))
        connection.execute(text("DELETE FROM worker_test_marks"))

    def writes_then_fails(session: Session, _now: datetime) -> None:
        session.execute(text("INSERT INTO worker_test_marks VALUES (1)"))
        raise RuntimeError("boom")

    def writes(session: Session, _now: datetime) -> None:
        session.execute(text("INSERT INTO worker_test_marks VALUES (2)"))

    try:
        assert (
            run_job(
                _registry_with(writes_then_fails).get("test_job"), engine, heartbeat_path=heartbeat
            )
            is RunStatus.FAILED
        )
        assert (
            run_job(_registry_with(writes).get("test_job"), engine, heartbeat_path=heartbeat)
            is RunStatus.COMPLETED
        )
        with engine.connect() as connection:
            assert list(connection.scalars(text("SELECT value FROM worker_test_marks"))) == [2]
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE worker_test_marks"))


def test_JOB_heartbeat_healthcheck(heartbeat: Path) -> None:
    assert not is_healthy(heartbeat)
    heartbeat.touch()
    now = heartbeat.stat().st_mtime
    assert is_healthy(heartbeat, now=now + MAX_AGE_SECONDS)
    assert not is_healthy(heartbeat, now=now + MAX_AGE_SECONDS + 1)


def test_JOB_heartbeat_task_runs_and_refreshes_file(engine: Engine, heartbeat: Path) -> None:
    assert run_job(registry.get("heartbeat"), engine, heartbeat_path=heartbeat) is (
        RunStatus.COMPLETED
    )
    assert is_healthy(heartbeat)


def test_JOB_registry_rejects_duplicates_and_invalid_intervals() -> None:
    test_registry = JobRegistry()
    test_registry.register("a", seconds=10)(lambda _s, _n: None)
    with pytest.raises(ValueError):
        test_registry.register("a", seconds=10)
    with pytest.raises(ValueError):
        test_registry.register("b")
    assert test_registry.get("a").interval_seconds == 10
    assert len(test_registry) == 1


def test_JOB_scheduler_registers_every_task_once(engine: Engine, heartbeat: Path) -> None:
    assert tasks.heartbeat is registry.get("heartbeat").function
    scheduler = build_scheduler(registry, engine, heartbeat_path=heartbeat)
    scheduled = {job.id: job for job in scheduler.get_jobs()}
    assert set(scheduled) == {job.name for job in registry}
    assert all(job.max_instances == 1 and job.coalesce for job in scheduled.values())


def test_JOB_logs_are_json_with_job_fields() -> None:
    record = logging.LogRecord("app.worker", logging.INFO, __file__, 1, "job completed", None, None)
    record.job = "expire_proposals"
    record.status = "completed"
    record.duration_ms = 12
    entry = json.loads(JsonFormatter().format(record))
    assert entry["level"] == "INFO"
    assert entry["message"] == "job completed"
    assert entry["job"] == "expire_proposals"
    assert entry["duration_ms"] == 12

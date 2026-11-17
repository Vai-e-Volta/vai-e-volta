"""Registry of scheduled tasks.

Every task must be idempotent: running it twice (or again after a failure) gives the same
result. A task receives the database session and the current instant (UTC), so tests can
freeze the clock.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

JobFunction = Callable[[Session, datetime], None]


@dataclass(frozen=True)
class Job:
    name: str
    function: JobFunction
    interval_seconds: int


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def register(
        self,
        name: str,
        *,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
    ) -> Callable[[JobFunction], JobFunction]:
        """Decorator that registers ``function`` to run every given interval."""
        interval = seconds + minutes * 60 + hours * 3600
        if interval <= 0:
            raise ValueError("the interval of a job must be positive")
        if name in self._jobs:
            raise ValueError(f"job already registered: {name}")

        def decorator(function: JobFunction) -> JobFunction:
            self._jobs[name] = Job(name=name, function=function, interval_seconds=interval)
            return function

        return decorator

    def __iter__(self) -> Iterator[Job]:
        return iter(self._jobs.values())

    def __len__(self) -> int:
        return len(self._jobs)

    def get(self, name: str) -> Job:
        return self._jobs[name]


# Registry used by the worker process. Task modules register themselves here and are
# imported in ``app.worker.tasks``.
registry = JobRegistry()

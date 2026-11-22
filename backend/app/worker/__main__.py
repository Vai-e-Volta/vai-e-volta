"""Entry point of the worker container: ``python -m app.worker``."""

from __future__ import annotations

import logging
import os

from app.db import get_engine
from app.worker import (
    cleanup,  # noqa: F401  (registers the cleanup job)
    tasks,  # noqa: F401  (registers the tasks)
)
from app.worker.logging import configure_logging
from app.worker.registry import registry
from app.worker.scheduler import build_scheduler


def main() -> None:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    logger = logging.getLogger("app.worker")
    scheduler = build_scheduler(registry, get_engine())
    logger.info("worker started", extra={"status": "started"})
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("worker stopped", extra={"status": "stopped"})


if __name__ == "__main__":
    main()

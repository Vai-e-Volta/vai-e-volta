"""JSON logs for the worker. Never log personal data, tokens or request bodies (section 8.6)."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

# Extra fields that may be attached to a log record with ``extra={...}``.
EXTRA_FIELDS = ("job", "status", "duration_ms", "error")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in EXTRA_FIELDS:
            if hasattr(record, field):
                entry[field] = getattr(record, field)
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # The scheduler logs every execution at INFO; the runner already logs one line per task.
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

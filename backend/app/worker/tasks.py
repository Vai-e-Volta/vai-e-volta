"""Tasks of the worker.

Each task module registers its functions in ``app.worker.registry.registry`` and is imported
here, so the scheduler sees every task. Upcoming tasks: H018-2 (expire proposals), H023-3
(calendar notices), H005-4 (anonymization) and H006-5 (cleanup).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.worker.registry import registry


@registry.register("heartbeat", seconds=30)
def heartbeat(session: Session, _now: datetime) -> None:
    """Checks the database connection; the runner refreshes the heartbeat file afterwards."""
    session.execute(text("SELECT 1"))

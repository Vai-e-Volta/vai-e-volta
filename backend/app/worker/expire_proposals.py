"""Worker task that expires pending proposals every minute (RN-47, H018-2)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.services.proposal_expiry import expire_pending_proposals
from app.worker.registry import registry


@registry.register("expire_proposals", minutes=1)
def expire_proposals(session: Session, now: datetime) -> None:
    """``pending`` with ``expires_at`` reached or ``start_date`` before today → ``expired``."""
    expire_pending_proposals(session, now)

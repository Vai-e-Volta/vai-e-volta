"""Verificação de saúde da API e do banco."""

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)


def check_database(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.warning("health_database_check_failed")
        return False
    return True


def get_health(db: Session) -> HealthResponse:
    if check_database(db):
        return HealthResponse(status="ok", database="ok")
    return HealthResponse(status="degraded", database="error")

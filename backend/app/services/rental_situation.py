"""Single source of truth for the rental situation shown in the UI (RN-65)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Sao_Paulo")


def today_br(now: datetime | None = None) -> date:
    """Return the current calendar date in the application's Brazilian timezone."""
    instant = now or datetime.now(UTC)
    if instant.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return instant.astimezone(LOCAL_TZ).date()


def rental_situation(
    status: str,
    start_date: date,
    end_date: date,
    expires_at: datetime,
    *,
    now: datetime | None = None,
) -> str:
    """Compute the user-facing rental situation from stored state and the current time."""
    instant = now or datetime.now(UTC)
    if instant.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    today = today_br(instant)

    if status == "pending":
        if expires_at > instant and start_date >= today:
            return "Aguardando"
        return "Expirado"
    if status == "accepted":
        if start_date > today:
            return "Reservado"
        if end_date >= today:
            return "Em andamento"
        return "Atrasado"

    situations = {
        "completed": "Concluído",
        "canceled": "Cancelado",
        "rejected": "Recusado",
        "expired": "Expirado",
    }
    try:
        return situations[status]
    except KeyError:
        raise ValueError(f"Unsupported rental status: {status}") from None

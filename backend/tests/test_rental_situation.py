from datetime import UTC, date, datetime, timedelta

import pytest

from app.services.rental_situation import rental_situation, today_br

TODAY = date(2026, 11, 18)
NOW = datetime(2026, 11, 18, 15, tzinfo=UTC)
FUTURE_EXPIRY = NOW + timedelta(hours=1)


def test_today_br_uses_sao_paulo_calendar_date() -> None:
    instant = datetime(2026, 11, 19, 2, tzinfo=UTC)
    assert today_br(instant) == date(2026, 11, 18)


@pytest.mark.parametrize(
    ("status", "start_date", "end_date", "expires_at", "expected"),
    [
        ("pending", TODAY, TODAY + timedelta(days=2), FUTURE_EXPIRY, "Aguardando"),
        (
            "pending",
            TODAY,
            TODAY + timedelta(days=2),
            NOW - timedelta(seconds=1),
            "Expirado",
        ),
        (
            "pending",
            TODAY - timedelta(days=1),
            TODAY + timedelta(days=2),
            FUTURE_EXPIRY,
            "Expirado",
        ),
        (
            "accepted",
            TODAY + timedelta(days=1),
            TODAY + timedelta(days=3),
            FUTURE_EXPIRY,
            "Reservado",
        ),
        ("accepted", TODAY, TODAY, FUTURE_EXPIRY, "Em andamento"),
        (
            "accepted",
            TODAY - timedelta(days=3),
            TODAY - timedelta(days=1),
            FUTURE_EXPIRY,
            "Atrasado",
        ),
        ("completed", TODAY, TODAY, FUTURE_EXPIRY, "Concluído"),
        ("canceled", TODAY, TODAY, FUTURE_EXPIRY, "Cancelado"),
        ("rejected", TODAY, TODAY, FUTURE_EXPIRY, "Recusado"),
        ("expired", TODAY, TODAY, FUTURE_EXPIRY, "Expirado"),
    ],
)
def test_rental_situation_matches_business_states(
    status: str,
    start_date: date,
    end_date: date,
    expires_at: datetime,
    expected: str,
) -> None:
    assert rental_situation(status, start_date, end_date, expires_at, now=NOW) == expected


def test_rental_situation_rejects_unknown_database_status() -> None:
    with pytest.raises(ValueError, match="Unsupported rental status"):
        rental_situation("unknown", TODAY, TODAY, FUTURE_EXPIRY, now=NOW)

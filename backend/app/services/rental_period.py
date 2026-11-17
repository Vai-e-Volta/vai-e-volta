"""Rental period arithmetic shared by the API and the worker."""

from __future__ import annotations

from datetime import date


def rental_days(start_date: date, end_date: date) -> int:
    """Return the rental duration in days; both ends are inclusive (RN-36).

    A one-day rental has ``start_date == end_date``.
    """
    if start_date > end_date:
        raise ValueError("start_date must not be after end_date")
    return (end_date - start_date).days + 1

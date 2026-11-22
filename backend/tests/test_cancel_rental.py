from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_return_request import return_context as return_context

from app.db import get_engine
from app.main import app
from app.models import Rental
from app.services.rental_situation import today_br


@pytest.mark.parametrize(
    "state,offset,expected,code",
    [
        ("pending", 0, 204, None),
        ("pending", -1, 204, None),
        ("accepted", 1, 204, None),
        ("accepted", 0, 409, "CANCEL_NOT_ALLOWED"),
        ("accepted", -1, 409, "CANCEL_NOT_ALLOWED"),
        ("rejected", 1, 409, "INVALID_STATE"),
        ("expired", 1, 409, "INVALID_STATE"),
        ("canceled", 1, 409, "INVALID_STATE"),
        ("completed", 1, 409, "INVALID_STATE"),
    ],
)
def test_cancel_state_rules(return_context, state, offset, expected, code):
    ctx = return_context
    rental_id = ctx["rental_id"]
    with Session(get_engine()) as session:
        rental = session.get(Rental, rental_id)
        rental.status = state
        rental.start_date = today_br() + timedelta(days=offset)
        session.commit()
    response = ctx["renter"].post(f"/api/rentals/{rental_id}/cancel")
    assert response.status_code == expected
    if code:
        assert response.json()["error"]["code"] == code
    with Session(get_engine()) as session:
        rental = session.get(Rental, rental_id)
        assert rental.status == ("canceled" if expected == 204 else state)
        assert (rental.canceled_at is not None) == (expected == 204)
    if expected == 204:
        repeated = ctx["renter"].post(f"/api/rentals/{rental_id}/cancel")
        assert repeated.status_code == 409


@pytest.mark.parametrize("role", ["owner", "outsider"])
def test_only_renter_may_cancel_accepted_rental(return_context, role):
    ctx = return_context
    with Session(get_engine()) as session:
        rental = session.get(Rental, ctx["rental_id"])
        rental.start_date = today_br() + timedelta(days=1)
        session.commit()
    response = ctx[role].post(f"/api/rentals/{ctx['rental_id']}/cancel")
    assert response.status_code == 403
    with Session(get_engine()) as session:
        assert (
            session.scalar(select(Rental.status).where(Rental.id == ctx["rental_id"])) == "accepted"
        )


def test_unknown_rental_and_anonymous_session(return_context):
    assert return_context["renter"].post("/api/rentals/999999999/cancel").status_code == 404
    with TestClient(app) as anonymous:
        assert (
            anonymous.post(f"/api/rentals/{return_context['rental_id']}/cancel").status_code == 401
        )


def test_cancel_releases_period_for_another_accepted_rental(return_context):
    ctx = return_context
    with Session(get_engine()) as session:
        rental = session.get(Rental, ctx["rental_id"])
        rental.start_date = today_br() + timedelta(days=1)
        session.commit()
    assert ctx["renter"].post(f"/api/rentals/{ctx['rental_id']}/cancel").status_code == 204
    with Session(get_engine()) as session:
        rental = session.get(Rental, ctx["rental_id"])
        replacement = Rental(
            listing_id=rental.listing_id,
            renter_id=rental.renter_id,
            start_date=rental.start_date,
            end_date=rental.end_date,
            status="accepted",
            daily_price_snapshot=rental.daily_price_snapshot,
            estimated_total=rental.estimated_total,
            listing_snapshot=rental.listing_snapshot,
            expires_at=rental.expires_at,
        )
        session.add(replacement)
        session.commit()
        session.delete(replacement)
        session.commit()

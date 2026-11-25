"""H022-2: serviço interno `create_notification`, usado pelas demais tarefas (RN-68)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import Connection, func, select
from sqlalchemy.orm import Session

from app.models import Notification
from app.services.notifications import PERSONAL_DATA_KEYS, create_notification

InsertRow = Callable[..., Any]


def _count(session: Session, user_id: Any, notification_type: str | None = None) -> int:
    statement = select(func.count(Notification.id)).where(Notification.user_id == user_id)
    if notification_type:
        statement = statement.where(Notification.type == notification_type)
    return session.scalar(statement) or 0


def test_create_notification_adds_an_unread_notice_to_the_callers_transaction(
    db: Connection, insert_user: InsertRow
) -> None:
    user_id = insert_user()
    session = Session(bind=db)
    nested = session.begin_nested()

    notification = create_notification(
        session, user_id, "proposal_received", None, {"listing_id": 7, "listing_title": "Serra"}
    )

    assert notification is not None
    assert notification.id is not None
    assert notification.user_id == user_id
    assert notification.type == "proposal_received"
    assert notification.rental_id is None
    assert notification.payload == {"listing_id": 7, "listing_title": "Serra"}
    assert notification.read_at is None
    assert _count(session, user_id) == 1
    # A função não faz commit: desfazer a transação de quem chama desfaz o aviso também.
    nested.rollback()
    assert _count(session, user_id) == 0


def test_create_notification_links_the_rental_and_never_deduplicates_api_types(
    db: Connection, insert_user: InsertRow, insert_rental: InsertRow
) -> None:
    user_id = insert_user()
    rental_id = insert_rental()
    session = Session(bind=db)

    first = create_notification(session, user_id, "proposal_accepted", rental_id, {"x": 1})
    second = create_notification(session, user_id, "proposal_accepted", rental_id, {"x": 1})

    assert first is not None and second is not None
    assert first.id != second.id
    assert first.rental_id == rental_id
    assert _count(session, user_id, "proposal_accepted") == 2


def test_create_notification_is_idempotent_for_worker_types(
    db: Connection, insert_user: InsertRow, insert_rental: InsertRow
) -> None:
    renter_id, owner_id = insert_user(), insert_user()
    rental_id = insert_rental(renter_id=renter_id)
    session = Session(bind=db)
    payload = {"rental_id": rental_id, "role": "renter"}

    first = create_notification(session, renter_id, "rental_starting", rental_id, payload)
    again = create_notification(session, renter_id, "rental_starting", rental_id, payload)
    other_party = create_notification(session, owner_id, "rental_starting", rental_id, payload)
    other_type = create_notification(session, renter_id, "return_due", rental_id, payload)

    assert first is not None
    assert again is None
    assert other_party is not None
    assert other_type is not None
    assert _count(session, renter_id, "rental_starting") == 1
    assert _count(session, owner_id, "rental_starting") == 1
    assert _count(session, renter_id, "return_due") == 1


@pytest.mark.parametrize("key", sorted(PERSONAL_DATA_KEYS))
def test_create_notification_refuses_personal_data_in_the_payload(
    db: Connection, insert_user: InsertRow, key: str
) -> None:
    user_id = insert_user()
    session = Session(bind=db)

    with pytest.raises(ValueError, match="personal data"):
        create_notification(session, user_id, "proposal_received", None, {key: "valor"})

    assert _count(session, user_id) == 0


def test_create_notification_refuses_unknown_type_non_object_payload_and_missing_rental(
    db: Connection, insert_user: InsertRow
) -> None:
    user_id = insert_user()
    session = Session(bind=db)
    not_an_object: Any = ["lista"]

    with pytest.raises(ValueError, match="Unknown notification type"):
        create_notification(session, user_id, "outro_tipo", None, {})
    with pytest.raises(ValueError, match="JSON object"):
        create_notification(session, user_id, "proposal_received", None, not_an_object)
    with pytest.raises(ValueError, match="needs a rental_id"):
        create_notification(session, user_id, "rental_overdue", None, {})

    assert _count(session, user_id) == 0

"""H022-2: caixa de avisos da API (F-46, F-47, F-52; RN-68) · API-NTF-01.

Só o dono do aviso lê ou altera; o estado lido/não lido (`read_at`) alimenta o indicador do sino.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.api.routes.auth import get_db
from app.db import get_engine
from app.main import app
from app.migrations import upgrade_database
from app.models import Notification, User
from app.security.session import create_session_token
from app.services.feed import _encode_cursor
from app.services.notifications import create_notification

ITEM_KEYS = {"id", "type", "rental_id", "payload", "created_at", "read_at"}


@dataclass
class InboxWorld:
    client: TestClient
    user_id: uuid.UUID
    other_id: uuid.UUID

    def notify(
        self,
        user_id: uuid.UUID,
        count: int = 1,
        notification_type: str = "proposal_received",
        payload: dict[str, Any] | None = None,
    ) -> list[int]:
        """Cria `count` avisos em uma única transação (todos com o mesmo created_at)."""
        with Session(get_engine()) as session:
            created = [
                create_notification(
                    session, user_id, notification_type, None, payload or {"listing_id": index}
                )
                for index in range(count)
            ]
            session.commit()
            return [notification.id for notification in created if notification is not None]

    def request(self, user_id: uuid.UUID, method: str, path: str, **kwargs: Any) -> Any:
        self.client.cookies.set("vv_session", create_session_token(user_id, 0))
        return self.client.request(method, path, **kwargs)

    def inbox(self, user_id: uuid.UUID, **params: Any) -> dict[str, Any]:
        response = self.request(user_id, "GET", "/api/notifications", params=params)
        assert response.status_code == 200, response.text
        return response.json()

    def unread(self, user_id: uuid.UUID) -> int:
        response = self.request(user_id, "GET", "/api/notifications/unread-count")
        assert response.status_code == 200, response.text
        return response.json()["count"]


def _make_user(user_id: uuid.UUID, prefix: str) -> User:
    suffix = f"{user_id.int % 10**11:011d}"
    return User(
        id=user_id,
        full_name="Pessoa de Teste",
        username=f"{prefix}_{suffix}",
        email=f"{prefix}-{suffix}@example.invalid",
        cpf=suffix,
        phone="51999990000",
        password_hash="test-only-hash",
        cep="96200000",
        street="Rua de Teste",
        number="1",
        neighborhood="Centro",
        city="Rio Grande",
        state="RS",
    )


@pytest.fixture
def world() -> Generator[InboxWorld, None, None]:
    upgrade_database()
    engine = get_engine()
    user_id, other_id = uuid.uuid4(), uuid.uuid4()

    def override_db() -> Generator[Session, None, None]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with Session(engine) as session:
            session.add_all([_make_user(user_id, "aviso"), _make_user(other_id, "outro")])
            session.commit()
        with TestClient(app) as client:
            yield InboxWorld(client, user_id, other_id)
    finally:
        app.dependency_overrides.pop(get_db, None)
        with Session(engine) as session:
            ids = (user_id, other_id)
            session.execute(delete(Notification).where(Notification.user_id.in_(ids)))
            session.execute(delete(User).where(User.id.in_(ids)))
            session.commit()
        engine.dispose()


def test_API_NTF_01_lists_only_my_notices_newest_first(world: InboxWorld) -> None:
    first = world.notify(world.user_id, payload={"listing_id": 1, "listing_title": "Furadeira"})[0]
    second = world.notify(world.user_id, notification_type="proposal_accepted")[0]
    third = world.notify(world.user_id)[0]
    others = world.notify(world.other_id)

    mine = world.inbox(world.user_id)

    assert [item["id"] for item in mine["items"]] == [third, second, first]
    assert mine["total"] == 3
    assert mine["next_cursor"] is None
    assert all(set(item) == ITEM_KEYS for item in mine["items"])
    assert all(item["read_at"] is None for item in mine["items"])
    assert mine["items"][1]["type"] == "proposal_accepted"
    assert mine["items"][2]["payload"] == {"listing_id": 1, "listing_title": "Furadeira"}
    # Os avisos de outra pessoa nunca aparecem, e ela só vê os dela.
    theirs = world.inbox(world.other_id)
    assert [item["id"] for item in theirs["items"]] == others
    assert theirs["total"] == 1


def test_API_NTF_01_cursor_follows_the_order_without_repeats_or_gaps(world: InboxWorld) -> None:
    # Sete avisos na mesma transação têm o mesmo created_at: o desempate por id é que ordena.
    mine = world.notify(world.user_id, count=7)
    world.notify(world.other_id, count=2)

    pages = []
    params: dict[str, Any] = {"limit": 3}
    while True:
        page = world.inbox(world.user_id, **params)
        pages.append(page)
        if page["next_cursor"] is None:
            break
        params["cursor"] = page["next_cursor"]

    ids = [item["id"] for page in pages for item in page["items"]]
    assert ids == sorted(mine, reverse=True)
    assert [len(page["items"]) for page in pages] == [3, 3, 1]
    assert all(page["total"] == 7 for page in pages)


def test_API_NTF_01_rejects_malformed_cursor_and_limits(world: InboxWorld) -> None:
    world.notify(world.user_id)
    too_big = _encode_cursor(datetime.now(UTC), 2**63)

    for cursor in ("abc", too_big):
        response = world.request(
            world.user_id, "GET", "/api/notifications", params={"cursor": cursor}
        )
        assert response.status_code == 400, cursor
        assert response.json()["error"]["code"] == "INVALID_CURSOR"
    for limit in (0, 51):
        response = world.request(
            world.user_id, "GET", "/api/notifications", params={"limit": limit}
        )
        assert response.status_code == 422, limit


def test_API_NTF_01_unread_count_follows_the_read_state_and_new_notices(
    world: InboxWorld,
) -> None:
    mine = world.notify(world.user_id, count=3)
    world.notify(world.other_id, count=2)
    assert world.unread(world.user_id) == 3

    read_one = world.request(world.user_id, "POST", f"/api/notifications/{mine[0]}/read")
    assert read_one.status_code == 204
    assert world.unread(world.user_id) == 2

    read_all = world.request(world.user_id, "POST", "/api/notifications/read-all")
    assert read_all.status_code == 204
    assert world.unread(world.user_id) == 0

    world.notify(world.user_id)
    assert world.unread(world.user_id) == 1
    # O indicador da outra pessoa não é afetado por nada disso.
    assert world.unread(world.other_id) == 2


def test_API_NTF_01_reading_twice_is_accepted_and_keeps_the_first_read_time(
    world: InboxWorld,
) -> None:
    notice = world.notify(world.user_id)[0]

    first = world.request(world.user_id, "POST", f"/api/notifications/{notice}/read")
    read_at = world.inbox(world.user_id)["items"][0]["read_at"]
    second = world.request(world.user_id, "POST", f"/api/notifications/{notice}/read")

    assert first.status_code == second.status_code == 204
    assert read_at is not None
    assert world.inbox(world.user_id)["items"][0]["read_at"] == read_at
    assert world.unread(world.user_id) == 0


def test_API_NTF_01_only_the_owner_reads_a_notice(world: InboxWorld) -> None:
    notice = world.notify(world.user_id)[0]

    stranger = world.request(world.other_id, "POST", f"/api/notifications/{notice}/read")
    missing = world.request(world.user_id, "POST", "/api/notifications/999999999/read")

    assert stranger.status_code == 403
    assert stranger.json()["error"]["code"] == "FORBIDDEN"
    assert world.inbox(world.user_id)["items"][0]["read_at"] is None
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOTIFICATION_NOT_FOUND"
    for bad_id in (0, 2**63):
        response = world.request(world.user_id, "POST", f"/api/notifications/{bad_id}/read")
        assert response.status_code == 422, bad_id


def test_API_NTF_01_read_all_only_touches_my_unread_notices(world: InboxWorld) -> None:
    already_read, *unread = world.notify(world.user_id, count=3)
    other = world.notify(world.other_id)[0]
    world.request(world.user_id, "POST", f"/api/notifications/{already_read}/read")
    before = {item["id"]: item["read_at"] for item in world.inbox(world.user_id)["items"]}

    assert world.request(world.user_id, "POST", "/api/notifications/read-all").status_code == 204

    after = {item["id"]: item["read_at"] for item in world.inbox(world.user_id)["items"]}
    assert all(read_at is not None for read_at in after.values())
    assert after[already_read] == before[already_read]
    assert set(after) == {already_read, *unread}
    # Os avisos de outra pessoa continuam como estavam.
    assert world.inbox(world.other_id)["items"][0]["id"] == other
    assert world.unread(world.other_id) == 1
    # Repetir não muda nada.
    assert world.request(world.user_id, "POST", "/api/notifications/read-all").status_code == 204
    assert {item["id"]: item["read_at"] for item in world.inbox(world.user_id)["items"]} == after


def test_API_NTF_01_requires_login(world: InboxWorld) -> None:
    notice = world.notify(world.user_id)[0]
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/notifications").status_code == 401
        assert anonymous.get("/api/notifications/unread-count").status_code == 401
        assert anonymous.post("/api/notifications/read-all").status_code == 401
        assert anonymous.post(f"/api/notifications/{notice}/read").status_code == 401
    assert world.unread(world.user_id) == 1

from datetime import UTC, datetime, timedelta

from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.worker.tasks import anonymize_accounts


def test_anonymizes_only_expired_deleted_accounts_and_is_idempotent(db: Connection, insert_user):
    now = datetime(2026, 11, 22, 12, tzinfo=UTC)
    first, second, not_due, active = (insert_user() for _ in range(4))
    db.execute(
        text("UPDATE users SET deleted_at = :deleted, purge_after = :expiry WHERE id = ANY(:ids)"),
        {
            "deleted": now - timedelta(days=366),
            "expiry": now - timedelta(seconds=1),
            "ids": [first, second],
        },
    )
    db.execute(
        text("UPDATE users SET deleted_at = :deleted, purge_after = :expiry WHERE id = :id"),
        {"deleted": now - timedelta(days=365), "expiry": now, "id": not_due},
    )
    db.execute(
        text("UPDATE users SET purge_after = :expiry WHERE id = :id"),
        {"expiry": now - timedelta(days=1), "id": active},
    )
    with Session(bind=db) as session:
        anonymize_accounts(session, now)
        session.flush()
        before = db.execute(
            text(
                "SELECT id, username, email, cpf, phone, password_hash, cep, street, state, "
                "anonymized_at, token_version FROM users WHERE id = ANY(:ids) ORDER BY id"
            ),
            {"ids": [first, second]},
        ).all()
        anonymize_accounts(session, now + timedelta(seconds=1))
        session.flush()
        after = db.execute(
            text(
                "SELECT id, username, email, cpf, phone, password_hash, cep, street, state, "
                "anonymized_at, token_version FROM users WHERE id = ANY(:ids) ORDER BY id"
            ),
            {"ids": [first, second]},
        ).all()
    assert before == after
    assert len({row.cpf for row in before}) == 2
    for row in before:
        assert row.username.startswith("deleted-") and len(row.username) == 18
        assert row.email == f"anon-{row.id}@invalid"
        assert row.cpf.startswith("x") and len(row.cpf) == 11
        assert row.phone == "00000000000" and row.password_hash == "!"
        assert row.cep == row.street == row.state == ""
        assert row.anonymized_at == now and row.token_version == 1
    assert db.scalar(text("SELECT anonymized_at FROM users WHERE id = :id"), {"id": active}) is None
    assert db.scalar(
        text("SELECT anonymized_at FROM users WHERE id = :id"), {"id": not_due}
    ) == now + timedelta(seconds=1)

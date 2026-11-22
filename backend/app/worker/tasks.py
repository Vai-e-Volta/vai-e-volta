"""Tasks of the worker.

Each task module registers its functions in ``app.worker.registry.registry`` and is imported
here, so the scheduler sees every task. Upcoming tasks: H018-2 (expire proposals), H023-3
(calendar notices), H005-4 (anonymization) and H006-5 (cleanup).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import User
from app.worker.registry import registry


@registry.register("heartbeat", seconds=30)
def heartbeat(session: Session, _now: datetime) -> None:
    """Checks the database connection; the runner refreshes the heartbeat file afterwards."""
    session.execute(text("SELECT 1"))


@registry.register("anonymize_accounts", hours=24)
def anonymize_accounts(session: Session, now: datetime) -> None:
    """Replace expired deleted accounts with inert, unique identifiers."""
    users = session.scalars(
        select(User)
        .where(
            User.deleted_at.is_not(None),
            User.purge_after < now,
            User.anonymized_at.is_(None),
        )
        .with_for_update(skip_locked=True)
    )
    for user in users:
        number = session.scalar(text("SELECT nextval('anonymized_user_number')"))
        identifier = f"{number:010d}"
        user.username = f"deleted-{identifier}"
        user.email = f"anon-{user.id}@invalid"
        user.full_name = "Usuário excluído"
        user.cpf = f"x{identifier}"
        user.phone = "00000000000"
        user.password_hash = "!"
        user.cep = user.street = user.number = user.neighborhood = user.city = user.state = ""
        user.complement = None
        user.anonymized_at = now
        user.token_version += 1

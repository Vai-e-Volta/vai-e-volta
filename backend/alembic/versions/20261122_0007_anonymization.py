"""Allow inert account identifiers and addresses after anonymization.

Revision ID: 20261122_0007
Revises: 20261118_0006
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261122_0007"
down_revision: str | None = "20261118_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD = {
    "username_format": "username::text ~ '^[a-z][a-z0-9_]{2,29}$'",
    "cpf_format": "cpf ~ '^[0-9]{11}$'",
    "cep_format": "cep ~ '^[0-9]{8}$'",
    "state_format": "state ~ '^[A-Z]{2}$'",
}
_NEW = {
    "username_format": "(anonymized_at IS NULL AND username::text ~ '^[a-z][a-z0-9_]{2,29}$') "
    "OR (anonymized_at IS NOT NULL AND username::text ~ '^deleted-[0-9]{10}$')",
    "cpf_format": "(anonymized_at IS NULL AND cpf ~ '^[0-9]{11}$') "
    "OR (anonymized_at IS NOT NULL AND cpf ~ '^x[0-9]{10}$')",
    "cep_format": "(anonymized_at IS NULL AND cep ~ '^[0-9]{8}$') "
    "OR (anonymized_at IS NOT NULL AND cep = '')",
    "state_format": "(anonymized_at IS NULL AND state ~ '^[A-Z]{2}$') "
    "OR (anonymized_at IS NOT NULL AND state = '')",
}


def _replace(constraints: dict[str, str]) -> None:
    for suffix, condition in constraints.items():
        name = f"ck_users_{suffix}"
        op.drop_constraint(name, "users", type_="check")
        op.create_check_constraint(name, "users", condition)


def upgrade() -> None:
    op.execute(
        "CREATE SEQUENCE anonymized_user_number AS bigint MINVALUE 1 MAXVALUE 9999999999 NO CYCLE"
    )
    _replace(_NEW)


def downgrade() -> None:
    count = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM users WHERE anonymized_at IS NOT NULL")
    )
    if count:
        raise RuntimeError("Cannot downgrade while anonymized accounts exist")
    _replace(_OLD)
    op.execute("DROP SEQUENCE anonymized_user_number")

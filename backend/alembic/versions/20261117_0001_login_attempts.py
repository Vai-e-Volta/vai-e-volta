"""Create the login_attempts table used by the login lockout (RN-14).

Revision ID: 20261117_0001
Revises: 20261109_0001
Create Date: 2026-11-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261117_0001"
down_revision: str | None = "20261109_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("identifier_hash", sa.Text(), nullable=False),
        sa.Column(
            "attempted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "identifier_hash ~ '^[0-9a-f]{64}$'",
            name="ck_login_attempts_identifier_hash_sha256",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_login_attempts"),
    )
    op.create_index(
        "ix_login_attempts_identifier_hash_attempted_at",
        "login_attempts",
        ["identifier_hash", "attempted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_login_attempts_identifier_hash_attempted_at", table_name="login_attempts")
    op.drop_table("login_attempts")

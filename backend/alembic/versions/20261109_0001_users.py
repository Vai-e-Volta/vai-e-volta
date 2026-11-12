"""Create the users table for registration and authentication.

Revision ID: 20261109_0001
Revises: 20261022_0001
Create Date: 2026-11-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261109_0001"
down_revision: str | None = "20261022_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("username", postgresql.CITEXT(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("cpf", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("cep", sa.Text(), nullable=False),
        sa.Column("street", sa.Text(), nullable=False),
        sa.Column("number", sa.Text(), nullable=False),
        sa.Column("complement", sa.Text(), nullable=True),
        sa.Column("neighborhood", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("token_version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purge_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "char_length(username) BETWEEN 3 AND 30", name="ck_users_username_length"
        ),
        sa.CheckConstraint(
            "username::text ~ '^[a-z][a-z0-9_]{2,29}$'", name="ck_users_username_format"
        ),
        sa.CheckConstraint("char_length(email) BETWEEN 1 AND 254", name="ck_users_email_length"),
        sa.CheckConstraint("cpf ~ '^[0-9]{11}$'", name="ck_users_cpf_format"),
        sa.CheckConstraint("phone ~ '^[0-9]{11}$'", name="ck_users_phone_format"),
        sa.CheckConstraint("cep ~ '^[0-9]{8}$'", name="ck_users_cep_format"),
        sa.CheckConstraint("state ~ '^[A-Z]{2}$'", name="ck_users_state_format"),
        sa.CheckConstraint("token_version >= 0", name="ck_users_token_version_nonnegative"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("cpf", name="uq_users_cpf"),
    )


def downgrade() -> None:
    op.drop_table("users")

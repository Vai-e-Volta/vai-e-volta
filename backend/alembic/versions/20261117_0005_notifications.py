"""Create the notifications table (RN-68).

Revision ID: 20261117_0005
Revises: 20261117_0004
Create Date: 2026-11-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261117_0005"
down_revision: str | None = "20261117_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TYPES_CHECK = (
    "type IN ('proposal_received', 'proposal_accepted', 'proposal_rejected', "
    "'proposal_expired', 'rental_starting', 'return_due', 'rental_overdue', "
    "'return_requested', 'rental_completed', 'rental_canceled')"
)
# Personal data never goes into the payload (section 5 of the technical document).
PAYLOAD_PII_CHECK = (
    "NOT (payload ?| ARRAY['email', 'cpf', 'phone', 'full_name', 'address', 'cep', "
    "'street', 'number', 'complement', 'neighborhood'])"
)
WORKER_TYPES = "type IN ('rental_starting', 'return_due', 'rental_overdue')"


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("rental_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(TYPES_CHECK, name="ck_notifications_type"),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'", name="ck_notifications_payload_object"
        ),
        sa.CheckConstraint(PAYLOAD_PII_CHECK, name="ck_notifications_payload_no_personal_data"),
        sa.CheckConstraint(
            f"NOT ({WORKER_TYPES}) OR rental_id IS NOT NULL",
            name="ck_notifications_worker_types_have_rental",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_notifications_user_id_users"),
        sa.ForeignKeyConstraint(
            ["rental_id"], ["rentals.id"], name="fk_notifications_rental_id_rentals"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
    )
    op.create_index(
        "ix_notifications_user_id_created_at_id",
        "notifications",
        ["user_id", "created_at", "id"],
    )
    # Makes the calendar jobs idempotent: one notice per user, type and rental (H023-3).
    op.create_index(
        "uq_notifications_worker_user_type_rental",
        "notifications",
        ["user_id", "type", "rental_id"],
        unique=True,
        postgresql_where=sa.text(WORKER_TYPES),
    )


def downgrade() -> None:
    op.drop_index("uq_notifications_worker_user_type_rental", table_name="notifications")
    op.drop_index("ix_notifications_user_id_created_at_id", table_name="notifications")
    op.drop_table("notifications")

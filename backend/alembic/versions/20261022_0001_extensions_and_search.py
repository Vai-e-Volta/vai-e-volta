"""Install PostgreSQL extensions required by the application.

Revision ID: 20261022_0001
Revises:
Create Date: 2026-10-22
"""

from __future__ import annotations

from alembic import op

revision = "20261022_0001"
down_revision = None
branch_labels = None
depends_on = None

_EXTENSIONS = ("citext", "pg_trgm", "unaccent", "btree_gist")


def upgrade() -> None:
    for extension in _EXTENSIONS:
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {extension} WITH SCHEMA public")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.immutable_unaccent(text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        STRICT
        PARALLEL SAFE
        AS $$
            SELECT public.unaccent('public.unaccent'::regdictionary, $1)
        $$
        """
    )


def downgrade() -> None:
    # Extensions can predate this revision or be used by later schema objects.
    # Keep them installed; removing the application-owned wrapper is safe.
    op.execute("DROP FUNCTION IF EXISTS public.immutable_unaccent(text)")

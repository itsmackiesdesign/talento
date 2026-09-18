"""add configurable status transition reasons

Revision ID: c2e4f6a8b135
Revises: b7c9d1e3f524
Create Date: 2026-09-08 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c2e4f6a8b135"
down_revision: str | None = "b7c9d1e3f524"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "application_statuses",
        sa.Column("requires_reason", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "application_statuses",
        sa.Column(
            "reasons",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.execute(
        "UPDATE application_statuses SET requires_reason = true WHERE system_key = 'rejected'"
    )

    op.add_column("application_status_history", sa.Column("reason", sa.Text()))
    op.add_column(
        "application_status_history",
        sa.Column("reason_is_other", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("application_status_history", "reason_is_other")
    op.drop_column("application_status_history", "reason")
    op.drop_column("application_statuses", "reasons")
    op.drop_column("application_statuses", "requires_reason")

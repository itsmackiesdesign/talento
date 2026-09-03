"""add tenant-configurable application status colors

Revision ID: b7c9d1e3f524
Revises: a9d1e3f5b724
Create Date: 2026-09-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b7c9d1e3f524"
down_revision: str | None = "a9d1e3f5b724"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "application_statuses",
        sa.Column(
            "color",
            sa.String(length=7),
            nullable=False,
            server_default="#3b82f6",
        ),
    )
    # Preserve the palette the UI previously assigned by column position so the migration
    # itself does not visually change existing pipelines.
    op.execute(
        """
        UPDATE application_statuses
           SET color = CASE
               WHEN system_key = 'new' THEN '#3b82f6'
               WHEN system_key = 'hired' THEN '#10b981'
               WHEN system_key = 'rejected' THEN '#ef4444'
               ELSE (ARRAY[
                   '#3b82f6', '#8b5cf6', '#f59e0b', '#06b6d4',
                   '#10b981', '#ef4444', '#ec4899', '#84cc16'
               ])[mod(sort_order, 8) + 1]
           END
        """
    )
    op.create_check_constraint(
        "ck_application_status_color",
        "application_statuses",
        "color ~ '^#[0-9A-Fa-f]{6}$'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_application_status_color", "application_statuses", type_="check")
    op.drop_column("application_statuses", "color")

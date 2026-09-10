"""add recruiter context to application status history

Revision ID: d4b8e1f2a307
Revises: d3a7f5c9e206
Create Date: 2026-09-10 16:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4b8e1f2a307"
down_revision: str | None = "d3a7f5c9e206"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("application_status_history", sa.Column("reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("application_status_history", "reason")

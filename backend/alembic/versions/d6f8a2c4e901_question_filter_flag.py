"""add opt-in application filter flag to questions

Revision ID: d6f8a2c4e901
Revises: b5e7f9a1c234
Create Date: 2026-08-27 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d6f8a2c4e901"
down_revision: str | None = "b5e7f9a1c234"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("is_filterable", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("questions", "is_filterable")

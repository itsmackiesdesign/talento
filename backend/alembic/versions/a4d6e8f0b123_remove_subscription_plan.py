"""remove legacy free/pro/business subscription plan

Revision ID: a4d6e8f0b123
Revises: f7b2c4d8e901
Create Date: 2026-08-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a4d6e8f0b123"
down_revision: str | None = "f7b2c4d8e901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("companies", "plan")


def downgrade() -> None:
    op.add_column(
        "companies",
        sa.Column("plan", sa.String(length=20), nullable=False, server_default="free"),
    )

"""send platform notifications to tenant groups

Revision ID: a9d1e3f5b724
Revises: f8c0d2e4a613
Create Date: 2026-08-31 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a9d1e3f5b724"
down_revision: str | None = "f8c0d2e4a613"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("notification_chat_id", sa.BigInteger()))
    op.add_column("companies", sa.Column("notification_chat_title", sa.Text()))
    op.create_unique_constraint(
        "uq_companies_notification_chat_id", "companies", ["notification_chat_id"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_companies_notification_chat_id", "companies", type_="unique"
    )
    op.drop_column("companies", "notification_chat_title")
    op.drop_column("companies", "notification_chat_id")

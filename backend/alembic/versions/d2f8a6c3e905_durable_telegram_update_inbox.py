"""persist Telegram updates before webhook acknowledgement

Revision ID: d2f8a6c3e905
Revises: c1d4e7f9a203
Create Date: 2026-09-10 14:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d2f8a6c3e905"
down_revision: str | None = "c1d4e7f9a203"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_update_inbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("dedupe_key", sa.String(length=160), nullable=False),
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("source IN ('tenant','platform')", name="ck_telegram_inbox_source"),
        sa.CheckConstraint(
            "status IN ('pending','processing','processed','failed')",
            name="ck_telegram_inbox_status",
        ),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dedupe_key"),
    )
    op.create_index(
        "ix_telegram_inbox_status_available",
        "telegram_update_inbox",
        ["status", "available_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_telegram_inbox_status_available", table_name="telegram_update_inbox")
    op.drop_table("telegram_update_inbox")

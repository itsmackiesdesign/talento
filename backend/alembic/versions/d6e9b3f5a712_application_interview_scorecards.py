"""add immutable interview scorecards

Revision ID: d6e9b3f5a712
Revises: d5c9f2a3b408
Create Date: 2026-09-10 18:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d6e9b3f5a712"
down_revision: str | None = "d5c9f2a3b408"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_interview_scorecards",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("interview_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("recommendation", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_interview_scorecard_rating"),
        sa.CheckConstraint(
            "recommendation IN ('strong_yes', 'yes', 'no', 'strong_no')",
            name="ck_interview_scorecard_recommendation",
        ),
        sa.ForeignKeyConstraint(["interview_id"], ["application_interviews.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("interview_id"),
    )


def downgrade() -> None:
    op.drop_table("application_interview_scorecards")

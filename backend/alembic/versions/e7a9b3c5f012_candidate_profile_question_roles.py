"""add semantic candidate profile roles to questions

Revision ID: e7a9b3c5f012
Revises: d6f8a2c4e901
Create Date: 2026-08-27 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e7a9b3c5f012"
down_revision: str | None = "d6f8a2c4e901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("profile_field", sa.String(length=30)))
    op.create_check_constraint(
        "ck_question_profile_field",
        "questions",
        "profile_field IS NULL OR profile_field IN ('candidate_name','candidate_photo')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_question_profile_field", "questions", type_="check")
    op.drop_column("questions", "profile_field")

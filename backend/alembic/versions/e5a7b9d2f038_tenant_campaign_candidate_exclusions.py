"""add tenant-controlled candidate exclusions to vacancy campaigns

Revision ID: e5a7b9d2f038
Revises: d4f6a8c1e927
Create Date: 2026-09-09 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e5a7b9d2f038"
down_revision: str | None = "d4f6a8c1e927"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "vacancy_campaigns",
        sa.Column(
            "excluded_candidate_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("vacancy_campaigns", "excluded_candidate_ids")

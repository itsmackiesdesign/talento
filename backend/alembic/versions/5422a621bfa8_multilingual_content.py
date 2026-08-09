"""multilingual content

Adds per-language content to bots, branches, vacancies and questions, the set of languages
a company publishes in, and the candidate's remembered language.

Revision ID: 5422a621bfa8
Revises: 1186454d8484
Create Date: 2026-08-03 00:33:16.315440
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '5422a621bfa8'
down_revision: Union[str, None] = '1186454d8484'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    # Translation maps default to an empty object so application code never has to
    # distinguish "no translations yet" from NULL.
    for table in ("bots", "branches", "vacancies", "questions"):
        op.add_column(
            table,
            sa.Column("translations", JSONB, nullable=True, server_default=sa.text("'{}'::jsonb")),
        )

    op.add_column("candidates", sa.Column("language", sa.String(length=5), nullable=True))

    # Added nullable first, backfilled, then made NOT NULL — adding a NOT NULL column with
    # no default would fail outright against existing companies.
    op.add_column("companies", sa.Column("enabled_languages", JSONB, nullable=True))
    op.execute(
        """
        UPDATE companies
           SET enabled_languages = jsonb_build_array(COALESCE(default_language, 'ru'))
         WHERE enabled_languages IS NULL
        """
    )
    op.alter_column(
        "companies",
        "enabled_languages",
        nullable=False,
        server_default=sa.text("'[\"ru\"]'::jsonb"),
    )


def downgrade() -> None:
    op.drop_column("companies", "enabled_languages")
    op.drop_column("candidates", "language")
    for table in ("questions", "vacancies", "branches", "bots"):
        op.drop_column(table, "translations")

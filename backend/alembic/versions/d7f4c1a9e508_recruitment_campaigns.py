"""add recruitment campaign attribution

Revision ID: d7f4c1a9e508
Revises: d6e9b3f5a712
Create Date: 2026-09-10 19:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d7f4c1a9e508"
down_revision: str | None = "d6e9b3f5a712"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recruitment_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vacancy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("code", sa.String(length=24), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_recruitment_campaign_code"),
        sa.UniqueConstraint("id", "company_id", name="uq_recruitment_campaign_company"),
    )
    op.create_index(
        "ix_recruitment_campaigns_company_vacancy",
        "recruitment_campaigns",
        ["company_id", "vacancy_id", "is_active"],
    )
    op.add_column("applications", sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_application_campaign_company",
        "applications",
        "recruitment_campaigns",
        ["campaign_id", "company_id"],
        ["id", "company_id"],
    )
    op.create_index("ix_applications_campaign", "applications", ["company_id", "campaign_id"])


def downgrade() -> None:
    op.drop_index("ix_applications_campaign", table_name="applications")
    op.drop_constraint("fk_application_campaign_company", "applications", type_="foreignkey")
    op.drop_column("applications", "campaign_id")
    op.drop_index("ix_recruitment_campaigns_company_vacancy", table_name="recruitment_campaigns")
    op.drop_table("recruitment_campaigns")

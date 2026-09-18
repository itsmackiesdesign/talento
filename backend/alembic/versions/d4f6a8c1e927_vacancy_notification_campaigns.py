"""add vacancy notification campaigns and tenant candidate audiences

Revision ID: d4f6a8c1e927
Revises: c2e4f6a8b135
Create Date: 2026-09-09 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d4f6a8c1e927"
down_revision: str | None = "c2e4f6a8b135"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(length=5)),
        sa.Column("notifications_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "last_interaction_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "candidate_id", name="uq_company_candidate"),
    )
    op.create_index(
        "ix_company_candidates_company_active",
        "company_candidates",
        ["company_id", "notifications_enabled"],
    )
    # Preserve every existing tenant/candidate relationship before tracking all future bot
    # interactions in middleware.
    op.execute(
        """
        INSERT INTO company_candidates
            (id, company_id, candidate_id, language, notifications_enabled,
             last_interaction_at, created_at)
        SELECT gen_random_uuid(), a.company_id, a.candidate_id, c.language, true,
               max(a.created_at), min(a.created_at)
        FROM applications a
        JOIN candidates c ON c.id = a.candidate_id
        GROUP BY a.company_id, a.candidate_id, c.language
        ON CONFLICT (company_id, candidate_id) DO NOTHING
        """
    )

    op.create_table(
        "vacancy_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vacancy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True)),
        sa.Column("intro_text", sa.Text(), server_default="", nullable=False),
        sa.Column("audience_type", sa.String(length=30), nullable=False),
        sa.Column("source_vacancy_ids", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("source_status_ids", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("branch_ids", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("languages", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("exclude_applied", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("exclude_rejected", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("total_recipients", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sent_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("blocked_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "audience_type IN ('everyone','selected_vacancies','selected_statuses')",
            name="ck_vacancy_campaign_audience",
        ),
        sa.CheckConstraint(
            "status IN ('scheduled','queued','sending','completed','failed','cancelled')",
            name="ck_vacancy_campaign_status",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_vacancy_campaigns_company_created",
        "vacancy_campaigns",
        ["company_id", "created_at"],
    )

    op.create_table(
        "vacancy_campaign_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("language", sa.String(length=5)),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending','sent','blocked','failed')",
            name="ck_campaign_recipient_status",
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["vacancy_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "candidate_id", name="uq_campaign_recipient"),
    )
    op.create_index(
        "ix_campaign_recipients_campaign_status",
        "vacancy_campaign_recipients",
        ["campaign_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_campaign_recipients_campaign_status", table_name="vacancy_campaign_recipients"
    )
    op.drop_table("vacancy_campaign_recipients")
    op.drop_index("ix_vacancy_campaigns_company_created", table_name="vacancy_campaigns")
    op.drop_table("vacancy_campaigns")
    op.drop_index("ix_company_candidates_company_active", table_name="company_candidates")
    op.drop_table("company_candidates")

"""platform admin, tenant suspension, and audit log

Revision ID: e3f1a7c9b204
Revises: c48c74980ce4
Create Date: 2026-08-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e3f1a7c9b204"
down_revision: str | None = "c48c74980ce4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "companies",
        sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("companies", sa.Column("suspension_reason", sa.Text()))
    op.add_column(
        "companies", sa.Column("suspended_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "companies", sa.Column("suspended_by_user_id", postgresql.UUID(as_uuid=True))
    )
    op.create_foreign_key(
        "fk_companies_suspended_by_user",
        "companies",
        "users",
        ["suspended_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "admin_audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "target_company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
        ),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_admin_audit_created", "admin_audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_admin_audit_created", table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
    op.drop_constraint(
        "fk_companies_suspended_by_user", "companies", type_="foreignkey"
    )
    op.drop_column("companies", "suspended_by_user_id")
    op.drop_column("companies", "suspended_at")
    op.drop_column("companies", "suspension_reason")
    op.drop_column("companies", "is_suspended")
    op.drop_column("users", "is_platform_admin")

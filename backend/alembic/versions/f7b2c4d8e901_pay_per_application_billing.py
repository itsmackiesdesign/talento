"""pay-per-application billing and balance ledger

Revision ID: f7b2c4d8e901
Revises: e3f1a7c9b204
Create Date: 2026-08-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f7b2c4d8e901"
down_revision: str | None = "e3f1a7c9b204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column(
            "billing_mode",
            sa.String(length=30),
            nullable=False,
            server_default="unlimited",
        ),
    )
    op.add_column(
        "companies",
        sa.Column("balance_uzs", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "companies",
        sa.Column(
            "application_price_uzs",
            sa.BigInteger(),
            nullable=False,
            server_default="2000",
        ),
    )
    op.create_check_constraint(
        "ck_company_billing_mode",
        "companies",
        "billing_mode IN ('unlimited','pay_per_application')",
    )
    op.create_check_constraint(
        "ck_company_balance_nonnegative", "companies", "balance_uzs >= 0"
    )
    op.create_check_constraint(
        "ck_company_application_price_positive",
        "companies",
        "application_price_uzs > 0",
    )

    op.create_table(
        "balance_transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount_uzs", sa.BigInteger(), nullable=False),
        sa.Column("balance_after_uzs", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("applications.id", ondelete="SET NULL"),
            unique=True,
        ),
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "kind IN ('top_up','application_charge')",
            name="ck_balance_transaction_kind",
        ),
        sa.CheckConstraint("amount_uzs <> 0", name="ck_balance_transaction_nonzero"),
        sa.CheckConstraint(
            "balance_after_uzs >= 0", name="ck_balance_after_nonnegative"
        ),
    )
    op.create_index(
        "ix_balance_transactions_company_created",
        "balance_transactions",
        ["company_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_balance_transactions_company_created", table_name="balance_transactions"
    )
    op.drop_table("balance_transactions")
    op.drop_constraint(
        "ck_company_application_price_positive", "companies", type_="check"
    )
    op.drop_constraint("ck_company_balance_nonnegative", "companies", type_="check")
    op.drop_constraint("ck_company_billing_mode", "companies", type_="check")
    op.drop_column("companies", "application_price_uzs")
    op.drop_column("companies", "balance_uzs")
    op.drop_column("companies", "billing_mode")

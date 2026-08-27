"""default new tenants to pay-per-application with welcome bonus

Revision ID: b5e7f9a1c234
Revises: a4d6e8f0b123
Create Date: 2026-08-26 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b5e7f9a1c234"
down_revision: str | None = "a4d6e8f0b123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Server defaults cover companies inserted outside the API. Existing rows are not
    # updated: the product requirement applies only to tenants created after this release.
    op.alter_column(
        "companies", "billing_mode", server_default="pay_per_application"
    )
    op.alter_column("companies", "balance_uzs", server_default="20000")
    op.drop_constraint("ck_balance_transaction_kind", "balance_transactions", type_="check")
    op.create_check_constraint(
        "ck_balance_transaction_kind",
        "balance_transactions",
        "kind IN ('signup_bonus','top_up','application_charge')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_balance_transaction_kind", "balance_transactions", type_="check")
    op.execute(
        "UPDATE balance_transactions SET kind = 'top_up' WHERE kind = 'signup_bonus'"
    )
    op.create_check_constraint(
        "ck_balance_transaction_kind",
        "balance_transactions",
        "kind IN ('top_up','application_charge')",
    )
    op.alter_column("companies", "balance_uzs", server_default="0")
    op.alter_column("companies", "billing_mode", server_default="unlimited")

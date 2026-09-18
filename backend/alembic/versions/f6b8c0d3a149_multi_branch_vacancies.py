"""allow vacancies to belong to multiple branches

Revision ID: f6b8c0d3a149
Revises: e5a7b9d2f038
Create Date: 2026-09-18 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f6b8c0d3a149"
down_revision: str | None = "e5a7b9d2f038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vacancy_branches",
        sa.Column("vacancy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("vacancy_id", "branch_id"),
    )
    op.create_index(
        "ix_vacancy_branches_branch", "vacancy_branches", ["branch_id", "vacancy_id"]
    )
    op.execute(
        """
        INSERT INTO vacancy_branches (vacancy_id, branch_id)
        SELECT id, branch_id FROM vacancies WHERE branch_id IS NOT NULL
        """
    )

    op.add_column(
        "applications",
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_applications_branch_id",
        "applications",
        "branches",
        ["branch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_applications_branch_id", "applications", ["branch_id"])
    op.execute(
        """
        UPDATE applications AS a
        SET branch_id = v.branch_id
        FROM vacancies AS v
        WHERE a.vacancy_id = v.id AND v.branch_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_applications_branch_id", table_name="applications")
    op.drop_constraint("fk_applications_branch_id", "applications", type_="foreignkey")
    op.drop_column("applications", "branch_id")
    op.drop_index("ix_vacancy_branches_branch", table_name="vacancy_branches")
    op.drop_table("vacancy_branches")

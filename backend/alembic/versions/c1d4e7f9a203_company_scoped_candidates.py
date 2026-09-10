"""scope candidates to companies and snapshot application contacts

Revision ID: c1d4e7f9a203
Revises: b7c9d1e3f524
Create Date: 2026-09-10 05:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1d4e7f9a203"
down_revision: str | None = "b7c9d1e3f524"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("company_id", sa.UUID(), nullable=True))
    op.add_column(
        "applications",
        sa.Column("candidate_name", sa.Text(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("candidate_telegram_user_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("candidate_username", sa.Text(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("candidate_phone", sa.Text(), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("candidate_language", sa.String(length=5), nullable=True),
    )

    # Tenant copies temporarily share the same Telegram id with their legacy source row.
    # PostgreSQL DDL is transactional, so a later failure restores this constraint too.
    op.drop_constraint("candidates_telegram_user_id_key", "candidates", type_="unique")

    # Preserve exactly what the recruiter could see before the migration. Applications
    # become historical records; later candidate refreshes must not rewrite these values.
    op.execute(
        """
        UPDATE applications AS application
           SET candidate_name = candidate.first_name,
               candidate_telegram_user_id = candidate.telegram_user_id,
               candidate_username = candidate.telegram_username,
               candidate_phone = candidate.phone,
               candidate_language = candidate.language
          FROM candidates AS candidate
         WHERE candidate.id = application.candidate_id
        """
    )

    # The legacy row was global. Clone it once for each company that actually owns an
    # application, then point that company's applications at its own candidate row.
    op.execute(
        """
        CREATE TEMPORARY TABLE candidate_company_map ON COMMIT DROP AS
        SELECT gen_random_uuid() AS new_candidate_id,
               candidate.id AS old_candidate_id,
               application_company.company_id,
               candidate.telegram_user_id,
               candidate.telegram_username,
               candidate.first_name,
               candidate.phone,
               candidate.language,
               candidate.created_at
          FROM candidates AS candidate
          JOIN (
                SELECT DISTINCT candidate_id, company_id
                  FROM applications
               ) AS application_company
            ON application_company.candidate_id = candidate.id
        """
    )
    op.execute(
        """
        INSERT INTO candidates (
            id, company_id, telegram_user_id, telegram_username,
            first_name, phone, language, created_at
        )
        SELECT new_candidate_id, company_id, telegram_user_id, telegram_username,
               first_name, phone, language, created_at
          FROM candidate_company_map
        """
    )
    op.execute(
        """
        UPDATE applications AS application
           SET candidate_id = mapping.new_candidate_id
          FROM candidate_company_map AS mapping
         WHERE application.candidate_id = mapping.old_candidate_id
           AND application.company_id = mapping.company_id
        """
    )
    op.execute(
        """
        DELETE FROM candidates AS candidate
         WHERE NOT EXISTS (
               SELECT 1
                 FROM applications AS application
                WHERE application.candidate_id = candidate.id
         )
        """
    )

    op.alter_column("candidates", "company_id", nullable=False)
    op.alter_column("applications", "candidate_name", nullable=False)
    op.alter_column("applications", "candidate_telegram_user_id", nullable=False)

    op.drop_constraint("applications_candidate_id_fkey", "applications", type_="foreignkey")
    op.create_foreign_key(
        "fk_candidates_company_id_companies",
        "candidates",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        "uq_candidate_company_telegram",
        "candidates",
        ["company_id", "telegram_user_id"],
    )
    op.create_unique_constraint(
        "uq_candidate_id_company",
        "candidates",
        ["id", "company_id"],
    )
    op.create_index(
        "ix_candidates_company_created",
        "candidates",
        ["company_id", "created_at"],
    )
    op.create_foreign_key(
        "fk_application_candidate_company",
        "applications",
        "candidates",
        ["candidate_id", "company_id"],
        ["id", "company_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_application_candidate_company", "applications", type_="foreignkey"
    )

    # Restore the old platform-global identity by choosing one stable row per Telegram id
    # and rewiring all applications before deleting the tenant-specific duplicates.
    op.execute(
        """
        CREATE TEMPORARY TABLE candidate_merge_map ON COMMIT DROP AS
        SELECT id AS old_candidate_id,
               first_value(id) OVER (
                   PARTITION BY telegram_user_id
                   ORDER BY created_at, id
               ) AS keeper_candidate_id
          FROM candidates
        """
    )
    op.execute(
        """
        UPDATE applications AS application
           SET candidate_id = mapping.keeper_candidate_id
          FROM candidate_merge_map AS mapping
         WHERE application.candidate_id = mapping.old_candidate_id
        """
    )
    op.execute(
        """
        DELETE FROM candidates AS candidate
         USING candidate_merge_map AS mapping
         WHERE candidate.id = mapping.old_candidate_id
           AND mapping.old_candidate_id <> mapping.keeper_candidate_id
        """
    )

    op.drop_index("ix_candidates_company_created", table_name="candidates")
    op.drop_constraint("uq_candidate_id_company", "candidates", type_="unique")
    op.drop_constraint("uq_candidate_company_telegram", "candidates", type_="unique")
    op.drop_constraint(
        "fk_candidates_company_id_companies", "candidates", type_="foreignkey"
    )
    op.drop_column("candidates", "company_id")
    op.create_unique_constraint(
        "candidates_telegram_user_id_key", "candidates", ["telegram_user_id"]
    )
    op.create_foreign_key(
        "applications_candidate_id_fkey",
        "applications",
        "candidates",
        ["candidate_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_column("applications", "candidate_language")
    op.drop_column("applications", "candidate_phone")
    op.drop_column("applications", "candidate_username")
    op.drop_column("applications", "candidate_telegram_user_id")
    op.drop_column("applications", "candidate_name")

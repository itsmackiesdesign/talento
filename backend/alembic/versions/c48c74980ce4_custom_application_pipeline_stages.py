"""custom application pipeline stages

Replaces the fixed 6-value application status enum with a per-company, HR-editable
pipeline: ``application_statuses`` rows, three of them (new/hired/rejected) flagged
``system_key`` and locked against edit/delete by the API. Every existing company is
seeded with the same 6 stages it already had, in the same order, with the same
ru/uz/en wording — so nothing changes for anyone until they touch Settings.

``applications.status`` (a bare string) becomes ``status_id`` (a real FK); history
gains matching ``*_status_id`` columns plus label snapshots so a later status
deletion never leaves history unreadable.

Revision ID: c48c74980ce4
Revises: 6a9ca6ab2c3f
Create Date: 2026-08-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c48c74980ce4'
down_revision: Union[str, None] = '6a9ca6ab2c3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSONB = postgresql.JSONB(astext_type=sa.Text())

# (legacy key, system_key or None, notify_candidate default, ru, uz, en)
# notify_candidate mirrors the exact set workers/tasks.py used to hardcode
# (NOTIFIABLE = {"interview", "offer", "hired", "rejected"}) so the upgrade is a no-op
# in behaviour until an HR opens Settings and changes something.
DEFAULT_STAGES = [
    ("new", "new", False, "Новая", "Yangi", "New"),
    ("viewed", None, False, "Просмотрена", "Ko‘rilgan", "Viewed"),
    ("interview", None, True, "Интервью", "Suhbat", "Interview"),
    ("offer", None, True, "Оффер", "Taklif", "Offer"),
    ("hired", "hired", True, "Принят", "Qabul qilingan", "Hired"),
    ("rejected", "rejected", True, "Отклонена", "Rad etilgan", "Rejected"),
]


def upgrade() -> None:
    op.create_table(
        "application_statuses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("system_key", sa.String(length=20), nullable=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("translations", JSONB, nullable=True, server_default=sa.text("'{}'::jsonb")),
        sa.Column("notify_candidate", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Only used during this migration's own backfill below, dropped before it ends —
        # going forward a status has no stable string key, only its id and (for the three
        # system rows) system_key.
        sa.Column("legacy_key", sa.String(length=20), nullable=True),
    )
    op.create_unique_constraint(
        "uq_status_company_system_key", "application_statuses", ["company_id", "system_key"]
    )
    op.create_index(
        "ix_application_statuses_company_sort",
        "application_statuses",
        ["company_id", "sort_order"],
    )

    conn = op.get_bind()
    company_ids = [row[0] for row in conn.execute(sa.text("SELECT id FROM companies"))]

    insert_stage = sa.text(
        """
        INSERT INTO application_statuses
            (id, company_id, system_key, label, translations, notify_candidate,
             sort_order, legacy_key)
        VALUES
            (gen_random_uuid(), :company_id, :system_key, :ru, :translations,
             :notify_candidate, :sort_order, :legacy_key)
        """
    )
    for company_id in company_ids:
        for index, (legacy_key, system_key, notify, ru, uz, en) in enumerate(DEFAULT_STAGES):
            conn.execute(
                insert_stage,
                {
                    "company_id": company_id,
                    "system_key": system_key,
                    "ru": ru,
                    "translations": f'{{"uz": {{"label": "{uz}"}}, "en": {{"label": "{en}"}}}}',
                    "notify_candidate": notify,
                    "sort_order": index,
                    "legacy_key": legacy_key,
                },
            )

    # --- applications.status (text) -> applications.status_id (FK) ---------------------
    op.add_column("applications", sa.Column("status_id", postgresql.UUID(as_uuid=True)))
    op.execute(
        """
        UPDATE applications a
           SET status_id = s.id
          FROM application_statuses s
         WHERE s.company_id = a.company_id AND s.legacy_key = a.status
        """
    )
    op.alter_column("applications", "status_id", nullable=False)
    op.drop_constraint("ck_application_status", "applications", type_="check")
    op.drop_column("applications", "status")
    op.create_foreign_key(
        "fk_applications_status_id",
        "applications",
        "application_statuses",
        ["status_id"],
        ["id"],
    )

    # --- application_status_history: add FKs + label snapshots -------------------------
    op.add_column(
        "application_status_history", sa.Column("from_status_id", postgresql.UUID(as_uuid=True))
    )
    op.add_column(
        "application_status_history", sa.Column("to_status_id", postgresql.UUID(as_uuid=True))
    )
    op.add_column("application_status_history", sa.Column("from_status_label", sa.Text()))
    op.add_column("application_status_history", sa.Column("to_status_label", sa.Text()))
    op.execute(
        """
        UPDATE application_status_history h
           SET from_status_id = s.id, from_status_label = s.label
          FROM applications a, application_statuses s
         WHERE h.application_id = a.id
           AND s.company_id = a.company_id AND s.legacy_key = h.from_status
        """
    )
    op.execute(
        """
        UPDATE application_status_history h
           SET to_status_id = s.id, to_status_label = s.label
          FROM applications a, application_statuses s
         WHERE h.application_id = a.id
           AND s.company_id = a.company_id AND s.legacy_key = h.to_status
        """
    )
    op.alter_column("application_status_history", "to_status_label", nullable=False)
    op.drop_column("application_status_history", "from_status")
    op.drop_column("application_status_history", "to_status")
    op.create_foreign_key(
        "fk_history_from_status_id",
        "application_status_history",
        "application_statuses",
        ["from_status_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_history_to_status_id",
        "application_status_history",
        "application_statuses",
        ["to_status_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_column("application_statuses", "legacy_key")


def downgrade() -> None:
    # The legacy 6-value enum cannot represent whatever custom stages HR created in the
    # meantime, so a downgrade collapses every application onto its status's system_key
    # where one exists, or 'new' otherwise — lossy, but the alternative (refusing to
    # downgrade at all) leaves no way back once this migration has run.
    op.add_column("application_status_history", sa.Column("from_status", sa.String(length=20)))
    op.add_column(
        "application_status_history",
        sa.Column("to_status", sa.String(length=20), nullable=False, server_default="new"),
    )
    op.execute(
        """
        UPDATE application_status_history h
           SET from_status = COALESCE(s.system_key, NULL)
          FROM application_statuses s
         WHERE s.id = h.from_status_id
        """
    )
    op.execute(
        """
        UPDATE application_status_history h
           SET to_status = COALESCE(s.system_key, 'new')
          FROM application_statuses s
         WHERE s.id = h.to_status_id
        """
    )
    op.alter_column("application_status_history", "to_status", server_default=None)
    op.drop_constraint(
        "fk_history_from_status_id", "application_status_history", type_="foreignkey"
    )
    op.drop_constraint("fk_history_to_status_id", "application_status_history", type_="foreignkey")
    op.drop_column("application_status_history", "from_status_id")
    op.drop_column("application_status_history", "to_status_id")
    op.drop_column("application_status_history", "from_status_label")
    op.drop_column("application_status_history", "to_status_label")

    op.add_column(
        "applications",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
    )
    op.execute(
        """
        UPDATE applications a
           SET status = COALESCE(s.system_key, 'new')
          FROM application_statuses s
         WHERE s.id = a.status_id
        """
    )
    op.alter_column("applications", "status", server_default=None)
    op.create_check_constraint(
        "ck_application_status",
        "applications",
        "status IN ('new','viewed','interview','offer','hired','rejected')",
    )
    op.drop_constraint("fk_applications_status_id", "applications", type_="foreignkey")
    op.drop_column("applications", "status_id")

    op.drop_table("application_statuses")

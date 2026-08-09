"""add datetime question type

No new column: the mask ('date' / 'datetime' / 'time') lives in the existing
``questions.validation`` JSONB, alongside min/max for number questions. Only the CHECK
constraint needs widening to accept the new type value.

Revision ID: 6a9ca6ab2c3f
Revises: 3922d40ec968
Create Date: 2026-08-08 01:56:29.369906
"""

from typing import Sequence, Union

from alembic import op

revision: str = '6a9ca6ab2c3f'
down_revision: Union[str, None] = '3922d40ec968'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_TYPES = "'short_text','long_text','single_choice','multi_choice','number','phone','file'"
NEW_TYPES = OLD_TYPES + ",'datetime'"


def upgrade() -> None:
    # Postgres has no ALTER on a CHECK constraint's expression — drop and recreate.
    op.drop_constraint("ck_question_type", "questions", type_="check")
    op.create_check_constraint("ck_question_type", "questions", f"type IN ({NEW_TYPES})")


def downgrade() -> None:
    # Any existing 'datetime' rows would violate the narrower constraint being restored;
    # that is the correct behavior — a downgrade should fail loudly rather than silently
    # delete or reinterpret candidate-authored questions.
    op.drop_constraint("ck_question_type", "questions", type_="check")
    op.create_check_constraint("ck_question_type", "questions", f"type IN ({OLD_TYPES})")

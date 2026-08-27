"""Relabelling a company's content when its default (base) language changes.

The base language is not just a label — for every translatable model (see app/core/i18n.py)
it is *where the content actually lives*: the base column holds that language's text
directly, and every other language sits in the row's ``translations`` JSONB map. Flipping
``Company.default_language`` alone leaves that mapping stale: the new base tab starts
reading the old base column (the wrong language), while any content that *was* already
translated into the new language sits in ``translations[new_lang]`` where no tab looks for
it anymore — it appears to have vanished, and a naive save from the confused "base" tab would
overwrite and permanently lose it.

``swap_default_language`` relabels every row in place instead: the old base column's content
moves into ``translations[old_lang]``, and ``translations[new_lang]`` (if any) moves into the
base column — so each language tab shows exactly, and only, what was actually authored under
that language.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApplicationStatus, Bot, Branch, News, Question, Vacancy

# Mirrors the `# {lang: {...}}` comment on each model's `translations` column.
_TRANSLATABLE_FIELDS: dict[type, tuple[str, ...]] = {
    Bot: ("welcome_message", "about_text", "after_apply_message", "contacts_text"),
    Branch: ("name", "city", "address"),
    Vacancy: ("title", "description", "city", "employment_type"),
    Question: ("text", "options"),
    News: ("title", "content"),
    ApplicationStatus: ("label",),
}

# Fields where blanking an untranslated slot would break the live bot, not just look empty —
# a choice question with no options can't render its keyboard. These keep the old base value
# instead of going blank when the new language was never translated, trading tab purity for
# not breaking candidates mid-flight.
_KEEP_OLD_ON_MISSING: dict[type, tuple[str, ...]] = {Question: ("options",)}


def _empty_like(value: Any) -> Any:
    if value is None or isinstance(value, list):
        return None if value is None else []
    return ""


def _swap_row(row: Any, old_lang: str, new_lang: str) -> None:
    fields = _TRANSLATABLE_FIELDS.get(type(row))
    if not fields:
        return
    keep_old_on_missing = _KEEP_OLD_ON_MISSING.get(type(row), ())

    translations = dict(row.translations or {})
    old_entry = dict(translations.get(old_lang) or {})
    new_entry = translations.get(new_lang) or {}

    for field in fields:
        old_value = getattr(row, field)
        # Nothing to preserve if the old base value was never actually filled in.
        if old_value:
            old_entry[field] = old_value
        if field in new_entry:
            setattr(row, field, new_entry[field])
        elif field not in keep_old_on_missing:
            setattr(row, field, _empty_like(old_value))
        # else: leave the column holding the old value — the deliberate fallback above.

    translations.pop(new_lang, None)
    if old_entry:
        translations[old_lang] = old_entry
    else:
        translations.pop(old_lang, None)
    row.translations = translations


async def swap_default_language(
    db: AsyncSession, company_id: UUID, old_lang: str, new_lang: str
) -> None:
    """Relabel every translatable row owned by ``company_id`` from ``old_lang`` to ``new_lang``.

    Call this *before* the ``Company.default_language`` column itself is updated, within the
    same transaction — the caller commits both together.
    """
    if old_lang == new_lang:
        return

    bot = await db.scalar(select(Bot).where(Bot.company_id == company_id))
    if bot:
        _swap_row(bot, old_lang, new_lang)
        # The candidate-facing fallback language (app/workers/tasks.py) is set from
        # `company.default_language` once at bot-connect time and never kept in sync
        # otherwise — update it here so it doesn't silently drift from the new default.
        bot.language = new_lang

    for model in (Branch, Vacancy, Question, News, ApplicationStatus):
        rows = (await db.scalars(select(model).where(model.company_id == company_id))).all()
        for row in rows:
            _swap_row(row, old_lang, new_lang)

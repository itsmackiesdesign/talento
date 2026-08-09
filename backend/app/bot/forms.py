"""Question assembly, answer validation and card/summary rendering for the bot."""

import re
import uuid
from datetime import datetime as dt
from html import escape
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.fsm import QuestionSnapshot
from app.bot.markup import to_telegram_html
from app.bot.texts import t
from app.core.i18n import localized, localized_options
from app.models import ApplicationStatus, Branch, Question, Vacancy

SHORT_TEXT_MAX = 200
LONG_TEXT_MAX = 2000

_PHONE_CLEAN = re.compile(r"[\s\-()]+")
_PHONE_VALID = re.compile(r"^\+?[1-9]\d{7,14}$")

# mask -> (strict input pattern, strptime/strftime format, format spec, example).
#
# The format spec ("MM.DD.YYYY") is shown to the candidate as-is in every language — like a
# date picker's placeholder text, it is a technical token rather than a sentence, so only the
# surrounding sentence in texts.py is translated, not "MM"/"DD"/"YYYY" themselves.
#
# The regex is checked before strptime so "8.2.1999" (missing zero-padding) is rejected with
# the same clear error as "13.45.1999" — strptime alone would silently accept the former.
_DATETIME_MASKS: dict[str, tuple[re.Pattern, str, str, str]] = {
    "date": (re.compile(r"^\d{2}\.\d{2}\.\d{4}$"), "%m.%d.%Y", "MM.DD.YYYY", "08.02.1999"),
    "datetime": (
        re.compile(r"^\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}$"),
        "%m.%d.%Y %H:%M",
        "MM.DD.YYYY HH:mm",
        "08.02.1999 10:08",
    ),
    "time": (re.compile(r"^\d{2}:\d{2}$"), "%H:%M", "HH:mm", "10:08"),
}


async def get_system_status(
    db: AsyncSession, company_id: uuid.UUID, system_key: str
) -> ApplicationStatus:
    """One of the three pipeline stages every company is seeded with — see
    ``ApplicationStatus`` and ``companies.py``'s ``DEFAULT_APPLICATION_STAGES``."""
    row = await db.scalar(
        select(ApplicationStatus).where(
            ApplicationStatus.company_id == company_id,
            ApplicationStatus.system_key == system_key,
        )
    )
    if row is None:
        raise RuntimeError(f"company {company_id} is missing system status '{system_key}'")
    return row


async def collect_questions(
    db: AsyncSession, company_id: uuid.UUID, vacancy_id: uuid.UUID, lang: str | None = None
) -> list[QuestionSnapshot]:
    """Company-wide questions first, then the vacancy's own — each by ``sort_order``.

    Snapshots carry both the wording shown to the candidate (in ``lang``) and the base
    wording that gets written into the application.
    """
    rows = (
        await db.scalars(
            select(Question)
            .where(
                Question.company_id == company_id,
                (Question.vacancy_id.is_(None)) | (Question.vacancy_id == vacancy_id),
            )
            # NULLs first puts company-wide questions ahead of vacancy-specific ones.
            .order_by(Question.vacancy_id.nullsfirst(), Question.sort_order, Question.created_at)
        )
    ).all()
    return [
        QuestionSnapshot(
            id=q.id.hex,
            # Converted once here, not at send time — the bot then only ever prints a
            # string it does not need to think about, whichever screen shows it.
            text=to_telegram_html(localized(q, "text", lang)),
            type=q.type,
            options=localized_options(q, lang),
            is_required=q.is_required,
            validation=q.validation,
            base_text=q.text,
            base_options=q.options,
        )
        for q in rows
    ]


class ValidationError(Exception):
    def __init__(self, key: str, **kwargs: Any):
        super().__init__(key)
        self.key = key
        self.kwargs = kwargs


def validate_text_answer(question: QuestionSnapshot, raw: str) -> str:
    """Validate a free-text/number/phone answer, returning the value to store.

    Raises ``ValidationError`` carrying an i18n key so the caller can re-ask in the
    candidate's language.
    """
    value = (raw or "").strip()

    if question.type == "short_text":
        if len(value) > SHORT_TEXT_MAX:
            raise ValidationError("err_too_long", max=SHORT_TEXT_MAX)
        return value

    if question.type == "long_text":
        if len(value) > LONG_TEXT_MAX:
            raise ValidationError("err_too_long", max=LONG_TEXT_MAX)
        return value

    if question.type == "number":
        normalised = value.replace(",", ".")
        try:
            number = float(normalised)
        except ValueError:
            raise ValidationError("err_not_number") from None
        rules = question.validation or {}
        lo, hi = rules.get("min"), rules.get("max")
        if lo is not None and number < float(lo):
            raise ValidationError("err_min", min=lo)
        if hi is not None and number > float(hi):
            raise ValidationError("err_max", max=hi)
        return str(int(number)) if number.is_integer() else str(number)

    if question.type == "phone":
        cleaned = _PHONE_CLEAN.sub("", value)
        if not _PHONE_VALID.match(cleaned):
            raise ValidationError("err_phone")
        return cleaned if cleaned.startswith("+") else f"+{cleaned}"

    if question.type == "datetime":
        mask = (question.validation or {}).get("mask", "date")
        pattern, fmt, spec, example = _DATETIME_MASKS.get(mask, _DATETIME_MASKS["date"])
        # The regex catches shape mistakes (missing zero-padding, wrong separators) before
        # strptime is asked to catch calendar mistakes (day 32, month 13, hour 25) — one
        # error message either way, but the two failure modes are genuinely different bugs
        # a candidate might make, so both are checked rather than relying on strptime alone
        # (which would silently accept "8.2.1999" as if it were "08.02.1999").
        if not pattern.match(value):
            raise ValidationError("err_datetime_format", format=spec, example=example)
        try:
            parsed = dt.strptime(value, fmt)
        except ValueError:
            raise ValidationError("err_datetime_format", format=spec, example=example) from None
        return parsed.strftime(fmt)

    # single_choice / multi_choice / file arrive through their own paths, never as free text.
    raise ValidationError("err_use_buttons")


def datetime_format_spec(mask: str) -> str:
    """The technical format token shown as a hint under the question ("MM.DD.YYYY")."""
    return _DATETIME_MASKS.get(mask, _DATETIME_MASKS["date"])[2]


def datetime_example(mask: str) -> str:
    return _DATETIME_MASKS.get(mask, _DATETIME_MASKS["date"])[3]


def format_salary(lang: str, vacancy: Vacancy) -> str | None:
    frm, to, cur = vacancy.salary_from, vacancy.salary_to, vacancy.currency
    fmt = lambda n: f"{n:,}".replace(",", " ")  # noqa: E731
    if frm and to:
        return t(lang, "salary_from_to", frm=fmt(frm), to=fmt(to), cur=cur)
    if frm:
        return t(lang, "salary_from", frm=fmt(frm), cur=cur)
    if to:
        return t(lang, "salary_to", to=fmt(to), cur=cur)
    return None


def render_vacancy_card(lang: str, vacancy: Vacancy, branch: Branch | None) -> str:
    """Every company-authored field goes through ``localized`` and falls back per field, so a
    vacancy translated only halfway still renders — the untranslated lines just stay in the
    base language rather than disappearing."""
    title = localized(vacancy, "title", lang)
    description = localized(vacancy, "description", lang)
    city = localized(vacancy, "city", lang)
    employment_type = localized(vacancy, "employment_type", lang)

    lines = [f"<b>{escape(title)}</b>", ""]

    if branch is not None:
        branch_name = localized(branch, "name", lang)
        branch_address = localized(branch, "address", lang)
        lines.append(f"🏢 <b>{t(lang, 'field_branch')}:</b> {escape(branch_name)}")
        if branch_address:
            lines.append(f"📍 <b>{t(lang, 'field_address')}:</b> {escape(branch_address)}")
    if city:
        lines.append(f"🌆 <b>{t(lang, 'field_city')}:</b> {escape(city)}")
    if employment_type:
        lines.append(
            f"🕒 <b>{t(lang, 'field_employment')}:</b> {escape(employment_type)}"
        )
    salary = format_salary(lang, vacancy)
    if salary:
        lines.append(f"💰 <b>{t(lang, 'field_salary')}:</b> {escape(salary)}")

    if description:
        lines += ["", to_telegram_html(description)]
    return "\n".join(lines)


def answer_display(answer: dict[str, Any] | None, lang: str) -> str:
    """What to echo back to the candidate.

    Prefers ``display`` — the wording they actually tapped — over ``value``, which holds the
    base-language equivalent destined for the panel. Confirming a form in Uzbek should not
    replay the answers in Russian.
    """
    if answer is None or answer.get("skipped"):
        return t(lang, "answer_skipped")
    value = answer.get("display", answer.get("value"))
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def render_summary(lang: str, questions: list[QuestionSnapshot], answers: dict) -> str:
    lines = [f"<b>{t(lang, 'summary_title')}</b>", ""]
    for i, q in enumerate(questions, start=1):
        shown = answer_display(answers.get(q.id), lang)
        # q.text is pre-rendered Telegram HTML (see collect_questions) — escaping it here
        # would print literal tags instead of the formatting the HR chose. No forced <b>:
        # the HR controls emphasis themselves via the toolbar.
        lines.append(f"{i}. {q.text}\n{escape(shown)}")
    return "\n\n".join(["\n".join(lines[:2]), *lines[2:]]) if len(lines) > 2 else "\n".join(lines)


def build_answers_payload(questions: list[QuestionSnapshot], answers: dict) -> list[dict]:
    """The immutable record written to ``applications.answers``."""
    payload = []
    for q in questions:
        stored = answers.get(q.id) or {}
        payload.append(
            {
                "question_id": q.id,
                "question_text": q.canonical_text(),
                "type": q.type,
                "answer": None if stored.get("skipped") else stored.get("value"),
                "skipped": bool(stored.get("skipped")),
            }
        )
    return payload

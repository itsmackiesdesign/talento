"""Application-form question builder.

Questions with ``vacancy_id IS NULL`` are company-wide and are asked before the
vacancy-specific ones; see ``app/bot/forms.py`` for how the two sets are merged.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import CurrentCompany, get_owned_or_404
from app.core.i18n import clean_translations
from app.models import Question, Vacancy
from app.schemas import QuestionCreate, QuestionOut, QuestionUpdate, ReorderRequest

router = APIRouter(prefix="/questions", tags=["questions"])

TRANSLATABLE = ("text", "options")

DB = Annotated[AsyncSession, Depends(get_db)]


def _clean_question_translations(
    translations: dict | None, base_options: list[str] | None, enabled_languages: list[str]
) -> dict:
    """Clean translations and reject choice lists that don't line up with the base options.

    A candidate answers by option *index*, and the stored answer is always the base wording.
    A translated list of a different length would therefore silently record the wrong
    option, so a mismatch is a hard 422 rather than a quiet fallback.
    """
    cleaned = clean_translations(translations, TRANSLATABLE, enabled_languages)
    expected = len(base_options or [])
    for lang, fields in cleaned.items():
        options = fields.get("options")
        if options is None:
            continue
        if not expected:
            # Not a choice question — a translated options list is meaningless here.
            fields.pop("options", None)
        elif len(options) != expected:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Translation '{lang}' has {len(options)} options but the question has "
                f"{expected}. Translate every option, in the same order.",
            )
    return cleaned


@router.get("", response_model=list[QuestionOut])
async def list_questions(
    company: CurrentCompany,
    db: DB,
    vacancy_id: Annotated[
        str | None,
        Query(
            description=(
                "UUID to list that vacancy's own questions, 'null' for company-wide ones, "
                "or omit to list everything."
            )
        ),
    ] = None,
) -> list[QuestionOut]:
    stmt = select(Question).where(Question.company_id == company.id)
    if vacancy_id is not None:
        if vacancy_id.lower() in ("null", "none"):
            stmt = stmt.where(Question.vacancy_id.is_(None))
        else:
            try:
                stmt = stmt.where(Question.vacancy_id == uuid.UUID(vacancy_id))
            except ValueError:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "vacancy_id must be a UUID or 'null'"
                ) from None
    questions = (
        await db.scalars(stmt.order_by(Question.sort_order, Question.created_at))
    ).all()
    return [QuestionOut.model_validate(q) for q in questions]


@router.post("", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
async def create_question(
    payload: QuestionCreate, company: CurrentCompany, db: DB
) -> QuestionOut:
    if payload.vacancy_id is not None:
        await get_owned_or_404(db, Vacancy, payload.vacancy_id, company.id)

    # Order is scoped to the set the question belongs to, so company-wide and
    # vacancy-specific questions each number from zero.
    scope = (
        Question.vacancy_id.is_(None)
        if payload.vacancy_id is None
        else Question.vacancy_id == payload.vacancy_id
    )
    next_order = (
        await db.scalar(
            select(func.coalesce(func.max(Question.sort_order), -1) + 1).where(
                Question.company_id == company.id, scope
            )
        )
    ) or 0

    data = payload.model_dump()
    data["translations"] = _clean_question_translations(
        data.get("translations"), data.get("options"), company.enabled_languages
    )
    question = Question(company_id=company.id, sort_order=next_order, **data)
    db.add(question)
    await db.commit()
    await db.refresh(question)
    return QuestionOut.model_validate(question)


@router.patch("/{question_id}", response_model=QuestionOut)
async def update_question(
    question_id: uuid.UUID, payload: QuestionUpdate, company: CurrentCompany, db: DB
) -> QuestionOut:
    question = await get_owned_or_404(db, Question, question_id, company.id)
    data = payload.model_dump(exclude_unset=True)

    # Re-validate through the create schema so type/options/validation stay consistent
    # even when only one of them is being patched. Pydantic's own ValidationError must be
    # caught here: left alone it becomes an unhandled 500 instead of the 422 a client
    # sending a bad mask/options/min-max combination on PATCH should see.
    try:
        merged = QuestionCreate(
            text=data.get("text", question.text),
            type=data.get("type", question.type),
            options=data.get("options", question.options),
            is_required=data.get("is_required", question.is_required),
            validation=data.get("validation", question.validation),
            vacancy_id=question.vacancy_id,
        )
    except PydanticValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "; ".join(e["msg"] for e in exc.errors())
        ) from exc
    question.text = merged.text
    question.type = merged.type
    question.options = merged.options
    question.is_required = merged.is_required
    question.validation = merged.validation

    # Re-check translations against whatever the options are *after* this patch: changing
    # the base options must not leave stale translations of the old list behind.
    incoming = data.get("translations", question.translations)
    question.translations = _clean_question_translations(
        incoming, merged.options, company.enabled_languages
    )

    await db.commit()
    await db.refresh(question)
    return QuestionOut.model_validate(question)


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(question_id: uuid.UUID, company: CurrentCompany, db: DB) -> None:
    question = await get_owned_or_404(db, Question, question_id, company.id)
    await db.delete(question)
    await db.commit()


@router.post("/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_questions(payload: ReorderRequest, company: CurrentCompany, db: DB) -> None:
    owned = set(
        (await db.scalars(select(Question.id).where(Question.company_id == company.id))).all()
    )
    unknown = [i for i in payload.ids if i not in owned]
    if unknown:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Unknown question ids: {', '.join(map(str, unknown))}"
        )
    for index, qid in enumerate(payload.ids):
        await db.execute(update(Question).where(Question.id == qid).values(sort_order=index))
    await db.commit()

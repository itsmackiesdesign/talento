"""Vacancy CRUD, ordering, and duplication into another branch."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_db
from app.core.deps import CurrentCompany, get_owned_or_404
from app.core.i18n import clean_translations
from app.models import Application, Bot, Branch, Question, Vacancy, vacancy_branches
from app.schemas import (
    ReorderRequest,
    VacancyCreate,
    VacancyDuplicate,
    VacancyOut,
    VacancyUpdate,
)

router = APIRouter(prefix="/vacancies", tags=["vacancies"])

TRANSLATABLE = ("title", "description", "city", "employment_type")

DB = Annotated[AsyncSession, Depends(get_db)]


async def _decorate(
    db: AsyncSession, company_id: uuid.UUID, vacancies: list[Vacancy]
) -> list[VacancyOut]:
    """Attach branch name, application count and the bot deep link."""
    if not vacancies:
        return []
    branch_rows = (
        await db.execute(
            select(vacancy_branches.c.vacancy_id, Branch.id, Branch.name)
            .join(Branch, Branch.id == vacancy_branches.c.branch_id)
            .where(
                vacancy_branches.c.vacancy_id.in_([vacancy.id for vacancy in vacancies]),
                Branch.company_id == company_id,
            )
            .order_by(Branch.sort_order, Branch.created_at)
        )
    ).all()
    branches_by_vacancy: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = {}
    for vacancy_id, branch_id, branch_name in branch_rows:
        branches_by_vacancy.setdefault(vacancy_id, []).append((branch_id, branch_name))
    counts = dict(
        (
            await db.execute(
                select(Application.vacancy_id, func.count(Application.id))
                .where(Application.company_id == company_id)
                .group_by(Application.vacancy_id)
            )
        ).all()
    )
    bot_username = await db.scalar(select(Bot.bot_username).where(Bot.company_id == company_id))

    result = []
    for v in vacancies:
        out = VacancyOut.model_validate(v)
        assigned = branches_by_vacancy.get(v.id, [])
        out.branch_ids = [branch_id for branch_id, _name in assigned]
        out.branch_names = [name for _branch_id, name in assigned]
        # Singular fields keep older clients working and represent the first branch in the
        # tenant's branch order.
        out.branch_id = out.branch_ids[0] if out.branch_ids else None
        out.branch_name = out.branch_names[0] if out.branch_names else None
        out.application_count = counts.get(v.id, 0)
        # Deep link for job ads, channels and QR codes (spec §3.1).
        out.deep_link = (
            f"https://t.me/{bot_username}?start=vacancy_{v.id.hex}" if bot_username else None
        )
        result.append(out)
    return result


async def _validate_branches(
    db: AsyncSession, company_id: uuid.UUID, branch_ids: list[uuid.UUID]
) -> list[uuid.UUID]:
    branch_ids = list(dict.fromkeys(branch_ids))
    if not branch_ids:
        return []
    owned = set(
        await db.scalars(
            select(Branch.id).where(Branch.company_id == company_id, Branch.id.in_(branch_ids))
        )
    )
    if owned != set(branch_ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or more branches not found")
    return branch_ids


async def _replace_branches(
    db: AsyncSession, vacancy: Vacancy, branch_ids: list[uuid.UUID]
) -> None:
    await db.execute(
        delete(vacancy_branches).where(vacancy_branches.c.vacancy_id == vacancy.id)
    )
    if branch_ids:
        await db.execute(
            insert(vacancy_branches),
            [{"vacancy_id": vacancy.id, "branch_id": branch_id} for branch_id in branch_ids],
        )
    vacancy.branch_id = branch_ids[0] if branch_ids else None


@router.get("", response_model=list[VacancyOut])
async def list_vacancies(
    company: CurrentCompany,
    db: DB,
    branch_id: Annotated[str | None, Query(description="UUID, or 'null' for general")] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[VacancyOut]:
    stmt = select(Vacancy).where(Vacancy.company_id == company.id)
    if branch_id is not None:
        if branch_id.lower() in ("null", "none"):
            stmt = stmt.where(
                ~select(vacancy_branches.c.vacancy_id)
                .where(vacancy_branches.c.vacancy_id == Vacancy.id)
                .exists()
            )
        else:
            try:
                parsed_branch_id = uuid.UUID(branch_id)
                stmt = stmt.where(
                    select(vacancy_branches.c.vacancy_id)
                    .where(
                        vacancy_branches.c.vacancy_id == Vacancy.id,
                        vacancy_branches.c.branch_id == parsed_branch_id,
                    )
                    .exists()
                )
            except ValueError:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "branch_id must be a UUID or 'null'"
                ) from None
    if status_filter:
        stmt = stmt.where(Vacancy.status == status_filter)

    vacancies = list(
        (await db.scalars(stmt.order_by(Vacancy.sort_order, Vacancy.created_at))).all()
    )
    return await _decorate(db, company.id, vacancies)


@router.post("", response_model=VacancyOut, status_code=status.HTTP_201_CREATED)
async def create_vacancy(payload: VacancyCreate, company: CurrentCompany, db: DB) -> VacancyOut:
    requested_ids = (
        payload.branch_ids
        if "branch_ids" in payload.model_fields_set
        else ([payload.branch_id] if payload.branch_id else [])
    )
    branch_ids = await _validate_branches(db, company.id, requested_ids)
    next_order = (
        await db.scalar(
            select(func.coalesce(func.max(Vacancy.sort_order), -1) + 1).where(
                Vacancy.company_id == company.id
            )
        )
    ) or 0
    data = payload.model_dump()
    data.pop("branch_ids", None)
    data.pop("branch_id", None)
    data["translations"] = clean_translations(
        data.get("translations"), TRANSLATABLE, company.enabled_languages
    )
    vacancy = Vacancy(company_id=company.id, sort_order=next_order, **data)
    db.add(vacancy)
    await db.flush()
    await _replace_branches(db, vacancy, branch_ids)
    await db.commit()
    await db.refresh(vacancy)
    return (await _decorate(db, company.id, [vacancy]))[0]


@router.get("/{vacancy_id}", response_model=VacancyOut)
async def get_vacancy(vacancy_id: uuid.UUID, company: CurrentCompany, db: DB) -> VacancyOut:
    vacancy = await get_owned_or_404(db, Vacancy, vacancy_id, company.id)
    return (await _decorate(db, company.id, [vacancy]))[0]


@router.patch("/{vacancy_id}", response_model=VacancyOut)
async def update_vacancy(
    vacancy_id: uuid.UUID, payload: VacancyUpdate, company: CurrentCompany, db: DB
) -> VacancyOut:
    vacancy = await get_owned_or_404(db, Vacancy, vacancy_id, company.id)
    data = payload.model_dump(exclude_unset=True)
    clear_branch = data.pop("clear_branch", False)
    requested_ids: list[uuid.UUID] | None = None
    if "branch_ids" in data:
        requested_ids = data.pop("branch_ids") or []
        data.pop("branch_id", None)
    elif "branch_id" in data:
        branch_id = data.pop("branch_id")
        requested_ids = [branch_id] if branch_id else []
    elif clear_branch:
        requested_ids = []

    if requested_ids is not None:
        requested_ids = await _validate_branches(db, company.id, requested_ids)
    if "translations" in data:
        data["translations"] = clean_translations(
            data["translations"], TRANSLATABLE, company.enabled_languages
        )
    for field, value in data.items():
        setattr(vacancy, field, value)
    if requested_ids is not None:
        await _replace_branches(db, vacancy, requested_ids)

    await db.commit()
    await db.refresh(vacancy)
    return (await _decorate(db, company.id, [vacancy]))[0]


@router.delete("/{vacancy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vacancy(vacancy_id: uuid.UUID, company: CurrentCompany, db: DB) -> None:
    vacancy = await get_owned_or_404(db, Vacancy, vacancy_id, company.id)
    await db.delete(vacancy)
    await db.commit()


@router.post(
    "/{vacancy_id}/duplicate", response_model=VacancyOut, status_code=status.HTTP_201_CREATED
)
async def duplicate_vacancy(
    vacancy_id: uuid.UUID, payload: VacancyDuplicate, company: CurrentCompany, db: DB
) -> VacancyOut:
    """Copy a vacancy — with its vacancy-specific questions — into another branch.

    This is how the spec expects "one role across several branches" to be modelled: separate
    vacancy rows, so applications and their branch attribution stay unambiguous.
    """
    source = await db.get(
        Vacancy, vacancy_id, options=[selectinload(Vacancy.questions)]
    )
    if source is None or source.company_id != company.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vacancy not found")
    requested_ids = (
        payload.branch_ids
        if "branch_ids" in payload.model_fields_set and payload.branch_ids is not None
        else ([payload.branch_id] if payload.branch_id else [])
    )
    branch_ids = await _validate_branches(db, company.id, requested_ids)

    next_order = (
        await db.scalar(
            select(func.coalesce(func.max(Vacancy.sort_order), -1) + 1).where(
                Vacancy.company_id == company.id
            )
        )
    ) or 0
    copy = Vacancy(
        company_id=company.id,
        branch_id=branch_ids[0] if branch_ids else None,
        title=payload.title or source.title,
        description=source.description,
        city=source.city,
        employment_type=source.employment_type,
        salary_from=source.salary_from,
        salary_to=source.salary_to,
        currency=source.currency,
        translations=dict(source.translations or {}),
        # Copies start as drafts so a half-configured duplicate never goes live in the bot.
        status="draft",
        sort_order=next_order,
    )
    db.add(copy)
    await db.flush()
    await _replace_branches(db, copy, branch_ids)

    for q in sorted(source.questions, key=lambda q: q.sort_order):
        db.add(
            Question(
                company_id=company.id,
                vacancy_id=copy.id,
                text=q.text,
                type=q.type,
                options=q.options,
                is_required=q.is_required,
                is_filterable=q.is_filterable,
                profile_field=q.profile_field,
                validation=q.validation,
                translations=dict(q.translations or {}),
                sort_order=q.sort_order,
            )
        )

    await db.commit()
    await db.refresh(copy)
    return (await _decorate(db, company.id, [copy]))[0]


@router.post("/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_vacancies(payload: ReorderRequest, company: CurrentCompany, db: DB) -> None:
    owned = set(
        (await db.scalars(select(Vacancy.id).where(Vacancy.company_id == company.id))).all()
    )
    unknown = [i for i in payload.ids if i not in owned]
    if unknown:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Unknown vacancy ids: {', '.join(map(str, unknown))}"
        )
    for index, vid in enumerate(payload.ids):
        await db.execute(update(Vacancy).where(Vacancy.id == vid).values(sort_order=index))
    await db.commit()

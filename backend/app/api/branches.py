"""Branch CRUD, ordering, and deletion with vacancy reassignment."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import CurrentCompany, get_owned_or_404
from app.core.i18n import clean_translations
from app.models import Branch, Vacancy
from app.schemas import BranchCreate, BranchOut, BranchUpdate, ReorderRequest

router = APIRouter(prefix="/branches", tags=["branches"])

TRANSLATABLE = ("name", "city", "address")

DB = Annotated[AsyncSession, Depends(get_db)]


async def _active_vacancy_counts(db: AsyncSession, company_id: uuid.UUID) -> dict:
    rows = await db.execute(
        select(Vacancy.branch_id, func.count(Vacancy.id))
        .where(Vacancy.company_id == company_id, Vacancy.status == "active")
        .group_by(Vacancy.branch_id)
    )
    return dict(rows.all())


def _to_out(branch: Branch, counts: dict) -> BranchOut:
    out = BranchOut.model_validate(branch)
    out.active_vacancy_count = counts.get(branch.id, 0)
    return out


async def _sync_branches_enabled(db: AsyncSession, company) -> None:
    """Branch mode turns itself on with the first active branch (spec §3.1).

    It is never turned off automatically — an HR who hides every branch temporarily should
    not silently lose the mode along with the branch grouping in the bot.
    """
    if company.branches_enabled:
        return
    exists = await db.scalar(
        select(Branch.id)
        .where(Branch.company_id == company.id, Branch.is_active.is_(True))
        .limit(1)
    )
    if exists is not None:
        company.branches_enabled = True


@router.get("", response_model=list[BranchOut])
async def list_branches(company: CurrentCompany, db: DB) -> list[BranchOut]:
    branches = (
        await db.scalars(
            select(Branch)
            .where(Branch.company_id == company.id)
            .order_by(Branch.sort_order, Branch.created_at)
        )
    ).all()
    counts = await _active_vacancy_counts(db, company.id)
    return [_to_out(b, counts) for b in branches]


@router.post("", response_model=BranchOut, status_code=status.HTTP_201_CREATED)
async def create_branch(payload: BranchCreate, company: CurrentCompany, db: DB) -> BranchOut:
    next_order = (
        await db.scalar(
            select(func.coalesce(func.max(Branch.sort_order), -1) + 1).where(
                Branch.company_id == company.id
            )
        )
    ) or 0
    data = payload.model_dump()
    data["translations"] = clean_translations(
        data.get("translations"), TRANSLATABLE, company.enabled_languages
    )
    branch = Branch(company_id=company.id, sort_order=next_order, **data)
    db.add(branch)
    await db.flush()
    await _sync_branches_enabled(db, company)
    await db.commit()
    await db.refresh(branch)
    return _to_out(branch, {})


@router.patch("/{branch_id}", response_model=BranchOut)
async def update_branch(
    branch_id: uuid.UUID, payload: BranchUpdate, company: CurrentCompany, db: DB
) -> BranchOut:
    branch = await get_owned_or_404(db, Branch, branch_id, company.id)
    data = payload.model_dump(exclude_unset=True)

    # The pair validator only sees this request, so a patch touching one coordinate could
    # otherwise leave the row half-set and unable to render a pin.
    if ("latitude" in data) != ("longitude" in data):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Update latitude and longitude together",
        )

    if "translations" in data:
        data["translations"] = clean_translations(
            data["translations"], TRANSLATABLE, company.enabled_languages
        )
    for field, value in data.items():
        setattr(branch, field, value)
    await db.flush()
    await _sync_branches_enabled(db, company)
    await db.commit()
    await db.refresh(branch)
    counts = await _active_vacancy_counts(db, company.id)
    return _to_out(branch, counts)


@router.delete("/{branch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_branch(
    branch_id: uuid.UUID,
    company: CurrentCompany,
    db: DB,
    move_vacancies_to: Annotated[
        str | None,
        Query(
            description=(
                "Target branch id to move this branch's vacancies to, or 'null' / omitted "
                "to detach them (they become general vacancies)."
            )
        ),
    ] = None,
) -> None:
    branch = await get_owned_or_404(db, Branch, branch_id, company.id)

    target_id: uuid.UUID | None = None
    if move_vacancies_to and move_vacancies_to.lower() not in ("null", "none", ""):
        try:
            target_id = uuid.UUID(move_vacancies_to)
        except ValueError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "move_vacancies_to must be a UUID or 'null'"
            ) from None
        if target_id == branch_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Cannot move vacancies into the branch being deleted"
            )
        # Verifying the target belongs to the same company stops a crafted request from
        # pushing vacancies into another tenant's branch.
        await get_owned_or_404(db, Branch, target_id, company.id)

    await db.execute(
        update(Vacancy)
        .where(Vacancy.company_id == company.id, Vacancy.branch_id == branch_id)
        .values(branch_id=target_id)
    )
    await db.delete(branch)
    await db.commit()


@router.post("/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_branches(payload: ReorderRequest, company: CurrentCompany, db: DB) -> None:
    owned = set(
        (
            await db.scalars(select(Branch.id).where(Branch.company_id == company.id))
        ).all()
    )
    unknown = [i for i in payload.ids if i not in owned]
    if unknown:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Unknown branch ids: {', '.join(map(str, unknown))}"
        )
    for index, branch_id in enumerate(payload.ids):
        await db.execute(
            update(Branch).where(Branch.id == branch_id).values(sort_order=index)
        )
    await db.commit()

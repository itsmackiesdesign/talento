"""The HR's own kanban pipeline: CRUD, reordering, and deletion with reassignment.

'new' / 'hired' / 'rejected' are seeded once per company (see ``companies.py``) and are
system steps — every endpoint here rejects an attempt to edit, delete or reorder one.
Everything else is the HR's own stage, freely editable, and deletable once no application
still sits in it (or after the caller says where those applications should go instead).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import CurrentCompany, get_owned_or_404
from app.core.i18n import clean_translations
from app.models import Application, ApplicationStatus
from app.schemas import (
    ApplicationStatusCreate,
    ApplicationStatusOut,
    ApplicationStatusUpdate,
    ReorderRequest,
)

router = APIRouter(prefix="/application-statuses", tags=["application-statuses"])

TRANSLATABLE = ("label",)

DB = Annotated[AsyncSession, Depends(get_db)]


async def _application_counts(db: AsyncSession, company_id: uuid.UUID) -> dict:
    rows = await db.execute(
        select(Application.status_id, func.count(Application.id))
        .where(Application.company_id == company_id)
        .group_by(Application.status_id)
    )
    return dict(rows.all())


def _to_out(row: ApplicationStatus, counts: dict) -> ApplicationStatusOut:
    out = ApplicationStatusOut.model_validate(row)
    out.application_count = counts.get(row.id, 0)
    return out


def _require_custom(row: ApplicationStatus) -> None:
    if row.is_system:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "System steps (Новая / Принят / Отклонена) can't be edited, reordered or deleted",
        )


@router.get("", response_model=list[ApplicationStatusOut])
async def list_statuses(company: CurrentCompany, db: DB) -> list[ApplicationStatusOut]:
    rows = (
        await db.scalars(
            select(ApplicationStatus).where(ApplicationStatus.company_id == company.id)
        )
    ).all()

    by_key = {r.system_key: r for r in rows if r.is_system}
    customs = sorted(
        (r for r in rows if not r.is_system), key=lambda r: (r.sort_order, r.created_at)
    )
    # Fixed shape: the intake step first, freely-ordered custom stages in the middle, the
    # two terminal outcomes last — see ApplicationStatus's docstring for why this is a
    # query-time arrangement rather than sort_order values system rows actually use.
    ordered = [by_key["new"], *customs, by_key["hired"], by_key["rejected"]]

    counts = await _application_counts(db, company.id)
    return [_to_out(r, counts) for r in ordered]


@router.post("", response_model=ApplicationStatusOut, status_code=status.HTTP_201_CREATED)
async def create_status(
    payload: ApplicationStatusCreate, company: CurrentCompany, db: DB
) -> ApplicationStatusOut:
    next_order = (
        await db.scalar(
            select(func.coalesce(func.max(ApplicationStatus.sort_order), -1) + 1).where(
                ApplicationStatus.company_id == company.id,
                ApplicationStatus.system_key.is_(None),
            )
        )
    ) or 0
    row = ApplicationStatus(
        company_id=company.id,
        label=payload.label.strip(),
        translations=clean_translations(
            payload.translations, TRANSLATABLE, company.enabled_languages
        ),
        notify_candidate=payload.notify_candidate,
        sort_order=next_order,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_out(row, {})


@router.patch("/{status_id}", response_model=ApplicationStatusOut)
async def update_status(
    status_id: uuid.UUID, payload: ApplicationStatusUpdate, company: CurrentCompany, db: DB
) -> ApplicationStatusOut:
    row = await get_owned_or_404(db, ApplicationStatus, status_id, company.id)
    _require_custom(row)

    data = payload.model_dump(exclude_unset=True)
    if "label" in data:
        data["label"] = data["label"].strip()
    if "translations" in data:
        data["translations"] = clean_translations(
            data["translations"], TRANSLATABLE, company.enabled_languages
        )
    for field, value in data.items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)

    counts = await _application_counts(db, company.id)
    return _to_out(row, counts)


@router.delete("/{status_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_status(
    status_id: uuid.UUID,
    company: CurrentCompany,
    db: DB,
    move_applications_to: Annotated[
        uuid.UUID | None,
        Query(description="Required if any application is currently in this step."),
    ] = None,
) -> None:
    row = await get_owned_or_404(db, ApplicationStatus, status_id, company.id)
    _require_custom(row)

    in_use = await db.scalar(
        select(func.count(Application.id)).where(Application.status_id == status_id)
    )
    if in_use:
        if move_applications_to is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "This step has applications in it — specify move_applications_to",
            )
        if move_applications_to == status_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Cannot move applications into the step being deleted"
            )
        # Confirms the target exists and belongs to this company before anything is written.
        await get_owned_or_404(db, ApplicationStatus, move_applications_to, company.id)
        await db.execute(
            update(Application)
            .where(Application.company_id == company.id, Application.status_id == status_id)
            .values(status_id=move_applications_to)
        )

    await db.delete(row)
    await db.commit()


@router.post("/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_statuses(payload: ReorderRequest, company: CurrentCompany, db: DB) -> None:
    """Reorders the company's custom stages only — ``ids`` must be exactly that set, since
    the three system stages have no independent position to receive (see ``list_statuses``).
    """
    ids = payload.ids

    owned = set(
        (
            await db.scalars(
                select(ApplicationStatus.id).where(
                    ApplicationStatus.company_id == company.id,
                    ApplicationStatus.system_key.is_(None),
                )
            )
        ).all()
    )
    if set(ids) != owned:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "ids must be exactly this company's custom steps, none more or fewer",
        )
    for index, status_row_id in enumerate(ids):
        await db.execute(
            update(ApplicationStatus)
            .where(ApplicationStatus.id == status_row_id)
            .values(sort_order=index)
        )
    await db.commit()

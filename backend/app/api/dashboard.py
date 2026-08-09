"""Dashboard aggregates for the panel's landing page."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import CurrentCompany
from app.models import Application, ApplicationStatus, Branch, Vacancy
from app.schemas import BranchStat, DailyPoint, DashboardStats, VacancyStat

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("/stats", response_model=DashboardStats)
async def stats(
    company: CurrentCompany,
    db: DB,
    days: Annotated[int, Query(ge=1, le=365, description="Window for the daily chart")] = 30,
) -> DashboardStats:
    now = datetime.now(UTC)
    since_7 = now - timedelta(days=7)
    since_window = now - timedelta(days=days)
    scoped = Application.company_id == company.id

    total = await db.scalar(select(func.count(Application.id)).where(scoped)) or 0
    last_7 = (
        await db.scalar(
            select(func.count(Application.id)).where(scoped, Application.created_at >= since_7)
        )
        or 0
    )
    last_30 = (
        await db.scalar(
            select(func.count(Application.id)).where(
                scoped, Application.created_at >= now - timedelta(days=30)
            )
        )
        or 0
    )
    active_vacancies = (
        await db.scalar(
            select(func.count(Vacancy.id)).where(
                Vacancy.company_id == company.id, Vacancy.status == "active"
            )
        )
        or 0
    )

    counts_by_status_id = dict(
        (
            await db.execute(
                select(Application.status_id, func.count(Application.id))
                .where(scoped)
                .group_by(Application.status_id)
            )
        ).all()
    )
    # Every current stage gets a key, zero-count ones included, same as the fixed 6-value
    # enum used to — the chart drops zero bars itself (see Dashboard.tsx).
    status_ids = (
        await db.scalars(
            select(ApplicationStatus.id).where(ApplicationStatus.company_id == company.id)
        )
    ).all()
    by_status = {str(sid): counts_by_status_id.get(sid, 0) for sid in status_ids}

    by_vacancy = (
        await db.execute(
            select(Vacancy.id, Vacancy.title, func.count(Application.id))
            .join(Application, Application.vacancy_id == Vacancy.id)
            .where(scoped)
            .group_by(Vacancy.id, Vacancy.title)
            .order_by(func.count(Application.id).desc())
            .limit(10)
        )
    ).all()

    by_branch = (
        await db.execute(
            select(Branch.id, Branch.name, func.count(Application.id))
            .select_from(Application)
            .join(Vacancy, Vacancy.id == Application.vacancy_id)
            .outerjoin(Branch, Branch.id == Vacancy.branch_id)
            .where(scoped)
            .group_by(Branch.id, Branch.name)
            .order_by(func.count(Application.id).desc())
        )
    ).all()

    daily_rows = dict(
        (
            await db.execute(
                select(
                    func.date(Application.created_at).label("day"),
                    func.count(Application.id),
                )
                .where(scoped, Application.created_at >= since_window)
                .group_by("day")
            )
        ).all()
    )
    # Fill the gaps so the chart draws a continuous line rather than skipping quiet days.
    daily = []
    for offset in range(days, -1, -1):
        day = (now - timedelta(days=offset)).date()
        daily.append(DailyPoint(date=day.isoformat(), count=daily_rows.get(day, 0)))

    return DashboardStats(
        applications_7d=last_7,
        applications_30d=last_30,
        applications_total=total,
        active_vacancies=active_vacancies,
        by_status=by_status,
        by_vacancy=[VacancyStat(vacancy_id=i, title=t, count=c) for i, t, c in by_vacancy],
        by_branch=[
            BranchStat(branch_id=i, name=n or "Без филиала", count=c) for i, n, c in by_branch
        ],
        daily=daily,
    )

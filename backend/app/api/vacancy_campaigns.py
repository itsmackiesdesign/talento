"""Create, estimate and inspect vacancy push-notification campaigns."""

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import CurrentCompany, CurrentUser, get_owned_or_404
from app.models import (
    Bot,
    Candidate,
    CompanyCandidate,
    Vacancy,
    VacancyCampaign,
    VacancyCampaignRecipient,
)
from app.schemas import (
    CampaignCandidateOut,
    VacancyCampaignCreate,
    VacancyCampaignEstimate,
    VacancyCampaignOut,
    VacancyCampaignTarget,
)
from app.services.campaigns import (
    audience_query,
    campaign_target_values,
    validate_campaign_target,
)

router = APIRouter(tags=["vacancy-campaigns"])
DB = Annotated[AsyncSession, Depends(get_db)]


async def _validated_vacancy_and_bot(
    db: AsyncSession, company_id: uuid.UUID, vacancy_id: uuid.UUID
) -> tuple[Vacancy, Bot]:
    vacancy = await get_owned_or_404(db, Vacancy, vacancy_id, company_id)
    if vacancy.status != "active":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only active vacancies can be sent")
    bot = await db.scalar(select(Bot).where(Bot.company_id == company_id, Bot.is_active.is_(True)))
    if bot is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Connect an active bot first")
    return vacancy, bot


async def _validate_target(
    db: AsyncSession, company_id: uuid.UUID, target: VacancyCampaignTarget
) -> None:
    try:
        await validate_campaign_target(db, company_id, target)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None


@router.post(
    "/vacancies/{vacancy_id}/campaigns/estimate",
    response_model=VacancyCampaignEstimate,
)
async def estimate_campaign(
    vacancy_id: uuid.UUID,
    payload: VacancyCampaignTarget,
    company: CurrentCompany,
    db: DB,
) -> VacancyCampaignEstimate:
    await _validated_vacancy_and_bot(db, company.id, vacancy_id)
    await _validate_target(db, company.id, payload)
    recipients = audience_query(company.id, vacancy_id, payload).subquery()
    count = await db.scalar(select(func.count()).select_from(recipients)) or 0
    return VacancyCampaignEstimate(count=count)


def _enqueue_campaign(campaign_id: uuid.UUID, scheduled_at: datetime | None) -> None:
    from app.workers.tasks import send_vacancy_campaign

    if scheduled_at is None:
        send_vacancy_campaign.delay(str(campaign_id))
    else:
        send_vacancy_campaign.apply_async(args=[str(campaign_id)], eta=scheduled_at)


@router.post(
    "/vacancies/{vacancy_id}/campaigns",
    response_model=VacancyCampaignOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_campaign(
    vacancy_id: uuid.UUID,
    payload: VacancyCampaignCreate,
    background: BackgroundTasks,
    company: CurrentCompany,
    user: CurrentUser,
    db: DB,
) -> VacancyCampaignOut:
    await _validated_vacancy_and_bot(db, company.id, vacancy_id)
    await _validate_target(db, company.id, payload)

    scheduled_at = payload.scheduled_at
    now = datetime.now(UTC)
    if scheduled_at is not None and scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=UTC)
    if scheduled_at is not None and scheduled_at <= now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Scheduled time must be in the future")

    rows = list((await db.execute(audience_query(company.id, vacancy_id, payload))).all())
    campaign = VacancyCampaign(
        company_id=company.id,
        vacancy_id=vacancy_id,
        created_by_user_id=user.id,
        intro_text=payload.intro_text.strip(),
        status="scheduled" if scheduled_at else "queued",
        scheduled_at=scheduled_at,
        total_recipients=len(rows),
        **campaign_target_values(payload),
    )
    db.add(campaign)
    await db.flush()
    db.add_all(
        [
            VacancyCampaignRecipient(
                campaign_id=campaign.id,
                candidate_id=candidate_id,
                telegram_user_id=telegram_user_id,
                language=language,
            )
            for candidate_id, telegram_user_id, language in rows
        ]
    )
    await db.commit()
    await db.refresh(campaign)
    background.add_task(
        asyncio.to_thread,
        _enqueue_campaign,
        campaign.id,
        scheduled_at,
    )
    return VacancyCampaignOut.model_validate(campaign)


@router.get("/vacancy-campaigns", response_model=list[VacancyCampaignOut])
async def list_campaigns(company: CurrentCompany, db: DB) -> list[VacancyCampaignOut]:
    rows = await db.scalars(
        select(VacancyCampaign)
        .where(VacancyCampaign.company_id == company.id)
        .order_by(VacancyCampaign.created_at.desc())
        .limit(100)
    )
    return [VacancyCampaignOut.model_validate(row) for row in rows]


@router.get("/vacancy-campaigns/candidates", response_model=list[CampaignCandidateOut])
async def list_campaign_candidates(
    company: CurrentCompany,
    db: DB,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> list[CampaignCandidateOut]:
    """Tenant-owned Telegram contacts available for explicit campaign exclusion."""

    stmt = (
        select(Candidate)
        .join(CompanyCandidate, CompanyCandidate.candidate_id == Candidate.id)
        .where(
            CompanyCandidate.company_id == company.id,
            CompanyCandidate.notifications_enabled.is_(True),
        )
    )
    if search and (term := search.strip()):
        pattern = f"%{term}%"
        stmt = stmt.where(
            or_(Candidate.first_name.ilike(pattern), Candidate.telegram_username.ilike(pattern))
        )
    rows = await db.scalars(stmt.order_by(Candidate.first_name, Candidate.created_at).limit(100))
    return [CampaignCandidateOut.model_validate(row) for row in rows]


@router.get("/vacancy-campaigns/{campaign_id}", response_model=VacancyCampaignOut)
async def get_campaign(
    campaign_id: uuid.UUID, company: CurrentCompany, db: DB
) -> VacancyCampaignOut:
    row = await get_owned_or_404(db, VacancyCampaign, campaign_id, company.id)
    return VacancyCampaignOut.model_validate(row)

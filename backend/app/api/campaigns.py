"""Telegram acquisition campaigns and source attribution."""

import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import CurrentCompany, get_owned_or_404
from app.models import Application, Bot, RecruitmentCampaign, Vacancy
from app.schemas import RecruitmentCampaignCreate, RecruitmentCampaignOut, RecruitmentCampaignUpdate

router = APIRouter(prefix="/campaigns", tags=["campaigns"])
DB = Annotated[AsyncSession, Depends(get_db)]


def _new_code() -> str:
    # Telegram's start payload limit is 64 bytes; `campaign_` + this token stays compact.
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(12))


async def _decorate(
    db: AsyncSession, company_id: uuid.UUID, rows: list[RecruitmentCampaign]
) -> list[RecruitmentCampaignOut]:
    if not rows:
        return []
    counts = dict(
        (
            await db.execute(
                select(Application.campaign_id, func.count(Application.id))
                .where(
                    Application.company_id == company_id,
                    Application.campaign_id.in_([row.id for row in rows]),
                )
                .group_by(Application.campaign_id)
            )
        ).all()
    )
    username = await db.scalar(select(Bot.bot_username).where(Bot.company_id == company_id))
    return [
        RecruitmentCampaignOut(
            id=row.id,
            vacancy_id=row.vacancy_id,
            name=row.name,
            source=row.source,
            code=row.code,
            is_active=row.is_active,
            deep_link=f"https://t.me/{username}?start=campaign_{row.code}" if username else None,
            applications_count=counts.get(row.id, 0),
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("", response_model=list[RecruitmentCampaignOut])
async def list_campaigns(
    company: CurrentCompany,
    db: DB,
    vacancy_id: uuid.UUID | None = Query(default=None),
) -> list[RecruitmentCampaignOut]:
    stmt = select(RecruitmentCampaign).where(RecruitmentCampaign.company_id == company.id)
    if vacancy_id is not None:
        stmt = stmt.where(RecruitmentCampaign.vacancy_id == vacancy_id)
    rows = list((await db.scalars(stmt.order_by(RecruitmentCampaign.created_at.desc()))).all())
    return await _decorate(db, company.id, rows)


@router.post("", response_model=RecruitmentCampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: RecruitmentCampaignCreate, company: CurrentCompany, db: DB
) -> RecruitmentCampaignOut:
    await get_owned_or_404(db, Vacancy, payload.vacancy_id, company.id)
    campaign = RecruitmentCampaign(
        company_id=company.id,
        vacancy_id=payload.vacancy_id,
        name=payload.name.strip(),
        source=payload.source.strip() if payload.source and payload.source.strip() else None,
        code=_new_code(),
    )
    db.add(campaign)
    try:
        await db.commit()
    except IntegrityError:
        # A token collision is extremely unlikely, but never return a broken attribution link.
        await db.rollback()
        campaign.code = _new_code()
        db.add(campaign)
        await db.commit()
    await db.refresh(campaign)
    return (await _decorate(db, company.id, [campaign]))[0]


@router.patch("/{campaign_id}", response_model=RecruitmentCampaignOut)
async def update_campaign(
    campaign_id: uuid.UUID,
    payload: RecruitmentCampaignUpdate,
    company: CurrentCompany,
    db: DB,
) -> RecruitmentCampaignOut:
    campaign = await get_owned_or_404(db, RecruitmentCampaign, campaign_id, company.id)
    campaign.is_active = payload.is_active
    await db.commit()
    await db.refresh(campaign)
    return (await _decorate(db, company.id, [campaign]))[0]

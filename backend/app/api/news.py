"""Company announcements shown under the bot's "📰 News" menu item."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import CurrentCompany, get_owned_or_404
from app.core.i18n import clean_translations
from app.models import News
from app.schemas import NewsCreate, NewsOut, NewsUpdate, ReorderRequest

router = APIRouter(prefix="/news", tags=["news"])

TRANSLATABLE = ("title", "content")

DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=list[NewsOut])
async def list_news(company: CurrentCompany, db: DB) -> list[NewsOut]:
    items = (
        await db.scalars(
            select(News)
            .where(News.company_id == company.id)
            .order_by(News.sort_order, News.created_at.desc())
        )
    ).all()
    return [NewsOut.model_validate(n) for n in items]


@router.post("", response_model=NewsOut, status_code=status.HTTP_201_CREATED)
async def create_news(payload: NewsCreate, company: CurrentCompany, db: DB) -> NewsOut:
    next_order = (
        await db.scalar(
            select(func.coalesce(func.max(News.sort_order), -1) + 1).where(
                News.company_id == company.id
            )
        )
    ) or 0
    data = payload.model_dump()
    data["translations"] = clean_translations(
        data.get("translations"), TRANSLATABLE, company.enabled_languages
    )
    item = News(company_id=company.id, sort_order=next_order, **data)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return NewsOut.model_validate(item)


@router.patch("/{news_id}", response_model=NewsOut)
async def update_news(
    news_id: uuid.UUID, payload: NewsUpdate, company: CurrentCompany, db: DB
) -> NewsOut:
    item = await get_owned_or_404(db, News, news_id, company.id)
    data = payload.model_dump(exclude_unset=True)
    if "translations" in data:
        data["translations"] = clean_translations(
            data["translations"], TRANSLATABLE, company.enabled_languages
        )
    for field, value in data.items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return NewsOut.model_validate(item)


@router.delete("/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_news(news_id: uuid.UUID, company: CurrentCompany, db: DB) -> None:
    item = await get_owned_or_404(db, News, news_id, company.id)
    await db.delete(item)
    await db.commit()


@router.post("/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_news(payload: ReorderRequest, company: CurrentCompany, db: DB) -> None:
    owned = set(
        (await db.scalars(select(News.id).where(News.company_id == company.id))).all()
    )
    unknown = [i for i in payload.ids if i not in owned]
    if unknown:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Unknown news ids: {', '.join(map(str, unknown))}"
        )
    for index, nid in enumerate(payload.ids):
        await db.execute(update(News).where(News.id == nid).values(sort_order=index))
    await db.commit()

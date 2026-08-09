"""Company creation, settings and team listing."""

import re
import secrets
import unicodedata
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import CurrentCompany, CurrentMembership, CurrentUser
from app.models import (
    DEFAULT_APPLICATION_STAGES,
    ApplicationStatus,
    Branch,
    Company,
    CompanyMember,
    User,
)
from app.schemas import CompanyCreate, CompanyOut, CompanyUpdate, TeamMemberOut

router = APIRouter(tags=["company"])

DB = Annotated[AsyncSession, Depends(get_db)]

_CYRILLIC = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}


def slugify(name: str) -> str:
    text = "".join(_CYRILLIC.get(ch, ch) for ch in name.lower())
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "company"


async def _unique_slug(db: AsyncSession, name: str) -> str:
    base = slugify(name)[:40]
    slug = base
    while await db.scalar(select(Company.id).where(Company.slug == slug)):
        slug = f"{base}-{secrets.token_hex(3)}"
    return slug


@router.post("/companies", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
async def create_company(payload: CompanyCreate, user: CurrentUser, db: DB) -> CompanyOut:
    """Create a company; the caller becomes its owner.

    MVP keeps one company per user — multi-company support exists in the data model
    (``company_members``) but the panel does not expose a switcher yet.
    """
    already = await db.scalar(
        select(CompanyMember).where(CompanyMember.user_id == user.id).limit(1)
    )
    if already is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "You already belong to a company"
        )

    company = Company(
        name=payload.name.strip(),
        slug=await _unique_slug(db, payload.name),
        default_language=payload.default_language,
        enabled_languages=[payload.default_language],
    )
    db.add(company)
    await db.flush()
    db.add(CompanyMember(company_id=company.id, user_id=user.id, role="owner"))
    for index, (system_key, label, translations, notify) in enumerate(DEFAULT_APPLICATION_STAGES):
        db.add(
            ApplicationStatus(
                company_id=company.id,
                system_key=system_key,
                label=label,
                translations=translations,
                notify_candidate=notify,
                sort_order=index,
            )
        )
    await db.commit()
    await db.refresh(company)
    return CompanyOut.model_validate(company)


@router.get("/company", response_model=CompanyOut)
async def get_company(company: CurrentCompany) -> CompanyOut:
    return CompanyOut.model_validate(company)


@router.patch("/company", response_model=CompanyOut)
async def update_company(
    payload: CompanyUpdate, company: CurrentCompany, db: DB
) -> CompanyOut:
    data = payload.model_dump(exclude_unset=True)

    # The default language is the fallback every untranslated field resolves to, so it must
    # stay in the published set — otherwise a candidate could pick a language whose gaps
    # fall back to a language the company no longer offers.
    if "enabled_languages" in data or "default_language" in data:
        new_default = data.get("default_language", company.default_language)
        new_enabled = data.get("enabled_languages", company.enabled_languages)
        if new_default not in new_enabled:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"The default language ({new_default}) must stay among the enabled languages",
            )

    # Guard the manual switch: turning branch mode on without any active branch would
    # leave the bot showing an empty branch list.
    if data.get("branches_enabled") is True:
        has_branch = await db.scalar(
            select(Branch.id)
            .where(Branch.company_id == company.id, Branch.is_active.is_(True))
            .limit(1)
        )
        if has_branch is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Create at least one active branch before enabling branch mode",
            )

    for field, value in data.items():
        setattr(company, field, value)
    await db.commit()
    await db.refresh(company)
    return CompanyOut.model_validate(company)


@router.get("/company/team", response_model=list[TeamMemberOut])
async def list_team(
    company: CurrentCompany, membership: CurrentMembership, db: DB
) -> list[TeamMemberOut]:
    rows = (
        await db.execute(
            select(User, CompanyMember.role)
            .join(CompanyMember, CompanyMember.user_id == User.id)
            .where(CompanyMember.company_id == company.id)
            .order_by(func.lower(User.full_name))
        )
    ).all()
    return [
        TeamMemberOut(
            user_id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=role,
            telegram_linked=u.telegram_user_id is not None,
        )
        for u, role in rows
    ]

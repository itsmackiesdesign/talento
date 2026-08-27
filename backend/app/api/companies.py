"""Company creation, settings and team listing."""

import hashlib
import re
import secrets
import unicodedata
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import CurrentCompany, CurrentUser, OwnerMembership
from app.models import (
    DEFAULT_APPLICATION_STAGES,
    SIGNUP_BONUS_UZS,
    ApplicationStatus,
    BalanceTransaction,
    Branch,
    Company,
    CompanyMember,
    TeamInvitation,
    User,
)
from app.schemas import (
    CompanyCreate,
    CompanyOut,
    CompanyUpdate,
    TeamInvitationAcceptOut,
    TeamInvitationCreate,
    TeamInvitationCreatedOut,
    TeamInvitationOut,
    TeamInvitationPreviewOut,
    TeamMemberOut,
)
from app.services.default_language import swap_default_language

router = APIRouter(tags=["company"])

DB = Annotated[AsyncSession, Depends(get_db)]
INVITATION_TTL = timedelta(days=7)

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
        billing_mode="pay_per_application",
        balance_uzs=SIGNUP_BONUS_UZS,
    )
    db.add(company)
    await db.flush()
    db.add(CompanyMember(company_id=company.id, user_id=user.id, role="owner"))
    db.add(
        BalanceTransaction(
            company_id=company.id,
            amount_uzs=SIGNUP_BONUS_UZS,
            balance_after_uzs=SIGNUP_BONUS_UZS,
            kind="signup_bonus",
            description="Welcome bonus",
        )
    )
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
    payload: CompanyUpdate, company: CurrentCompany, _: OwnerMembership, db: DB
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

    # Relabel existing content *before* flipping the column — the new base tab must show
    # translations[new_lang], not whatever the old base column happened to hold. See
    # app/services/default_language.py for why this can't just be a column update.
    new_default = data.get("default_language")
    if new_default and new_default != company.default_language:
        await swap_default_language(db, company.id, company.default_language, new_default)

    for field, value in data.items():
        setattr(company, field, value)
    await db.commit()
    await db.refresh(company)
    return CompanyOut.model_validate(company)


@router.get("/company/team", response_model=list[TeamMemberOut])
async def list_team(
    company: CurrentCompany, db: DB
) -> list[TeamMemberOut]:
    rows = (
        await db.execute(
            select(User, CompanyMember.role, CompanyMember.created_at)
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
            joined_at=joined_at,
        )
        for u, role, joined_at in rows
    ]


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _invitation_out(invitation: TeamInvitation) -> TeamInvitationOut:
    return TeamInvitationOut(
        id=invitation.id,
        email=invitation.email,
        role="member",
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


@router.get("/company/team/invitations", response_model=list[TeamInvitationOut])
async def list_team_invitations(
    company: CurrentCompany, _: OwnerMembership, db: DB
) -> list[TeamInvitationOut]:
    invitations = (
        await db.scalars(
            select(TeamInvitation)
            .where(
                TeamInvitation.company_id == company.id,
                TeamInvitation.accepted_at.is_(None),
                TeamInvitation.expires_at > datetime.now(UTC),
            )
            .order_by(TeamInvitation.created_at.desc())
        )
    ).all()
    return [_invitation_out(invitation) for invitation in invitations]


@router.post(
    "/company/team/invitations",
    response_model=TeamInvitationCreatedOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_team_invitation(
    payload: TeamInvitationCreate,
    company: CurrentCompany,
    owner: OwnerMembership,
    db: DB,
) -> TeamInvitationCreatedOut:
    email = str(payload.email).lower().strip()
    existing_member = await db.scalar(
        select(CompanyMember.user_id)
        .join(User, User.id == CompanyMember.user_id)
        .where(CompanyMember.company_id == company.id, User.email == email)
    )
    if existing_member is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This user is already a team member")

    raw_token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    invitation = await db.scalar(
        select(TeamInvitation)
        .where(
            TeamInvitation.company_id == company.id,
            TeamInvitation.email == email,
            TeamInvitation.accepted_at.is_(None),
        )
        .order_by(TeamInvitation.created_at.desc())
        .limit(1)
    )
    if invitation is None:
        invitation = TeamInvitation(
            company_id=company.id,
            email=email,
            role="member",
            token_hash=_token_hash(raw_token),
            invited_by_user_id=owner.user_id,
            expires_at=now + INVITATION_TTL,
        )
        db.add(invitation)
    else:
        # Inviting the same address again acts as a resend and invalidates the old link.
        invitation.token_hash = _token_hash(raw_token)
        invitation.invited_by_user_id = owner.user_id
        invitation.expires_at = now + INVITATION_TTL
        invitation.created_at = now

    await db.commit()
    await db.refresh(invitation)
    return TeamInvitationCreatedOut(
        **_invitation_out(invitation).model_dump(),
        invite_url=f'{settings.FRONTEND_URL.rstrip("/")}/invite/{raw_token}',
    )


@router.delete(
    "/company/team/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_team_invitation(
    invitation_id: uuid.UUID,
    company: CurrentCompany,
    _: OwnerMembership,
    db: DB,
) -> None:
    invitation = await db.get(TeamInvitation, invitation_id)
    if invitation is None or invitation.company_id != company.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    await db.delete(invitation)
    await db.commit()


async def _active_invitation(token: str, db: AsyncSession) -> TeamInvitation:
    invitation = await db.scalar(
        select(TeamInvitation).where(TeamInvitation.token_hash == _token_hash(token))
    )
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    if invitation.accepted_at is not None:
        raise HTTPException(status.HTTP_410_GONE, "This invitation has already been used")
    if invitation.expires_at <= datetime.now(UTC):
        raise HTTPException(status.HTTP_410_GONE, "This invitation has expired")
    return invitation


@router.get("/team/invitations/{token}", response_model=TeamInvitationPreviewOut)
async def preview_team_invitation(token: str, db: DB) -> TeamInvitationPreviewOut:
    invitation = await _active_invitation(token, db)
    company = await db.get(Company, invitation.company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    return TeamInvitationPreviewOut(
        company_name=company.name,
        email=invitation.email,
        expires_at=invitation.expires_at,
    )


@router.post("/team/invitations/{token}/accept", response_model=TeamInvitationAcceptOut)
async def accept_team_invitation(
    token: str, user: CurrentUser, db: DB
) -> TeamInvitationAcceptOut:
    invitation = await db.scalar(
        select(TeamInvitation)
        .where(TeamInvitation.token_hash == _token_hash(token))
        .with_for_update()
    )
    if invitation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    if invitation.accepted_at is not None:
        raise HTTPException(status.HTTP_410_GONE, "This invitation has already been used")
    if invitation.expires_at <= datetime.now(UTC):
        raise HTTPException(status.HTTP_410_GONE, "This invitation has expired")
    if user.email.lower() != invitation.email:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"This invitation was issued to {invitation.email}",
        )

    existing = await db.scalar(
        select(CompanyMember).where(CompanyMember.user_id == user.id).limit(1)
    )
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This account already belongs to a company",
        )

    company = await db.get(Company, invitation.company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    db.add(
        CompanyMember(
            company_id=invitation.company_id,
            user_id=user.id,
            role="member",
        )
    )
    invitation.accepted_at = datetime.now(UTC)
    await db.commit()
    return TeamInvitationAcceptOut(
        company_id=company.id,
        company_name=company.name,
        role="member",
    )


@router.delete("/company/team/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    user_id: uuid.UUID,
    company: CurrentCompany,
    _: OwnerMembership,
    db: DB,
) -> None:
    member = await db.scalar(
        select(CompanyMember).where(
            CompanyMember.company_id == company.id,
            CompanyMember.user_id == user_id,
        )
    )
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team member not found")
    if member.role == "owner":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Transfer ownership before removing the owner",
        )
    await db.delete(member)
    await db.commit()


@router.post(
    "/company/team/{user_id}/transfer-ownership",
    response_model=list[TeamMemberOut],
)
async def transfer_team_ownership(
    user_id: uuid.UUID,
    company: CurrentCompany,
    owner: OwnerMembership,
    db: DB,
) -> list[TeamMemberOut]:
    target = await db.scalar(
        select(CompanyMember).where(
            CompanyMember.company_id == company.id,
            CompanyMember.user_id == user_id,
        )
    )
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team member not found")
    if target.user_id == owner.user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You are already the owner")

    owner.role = "member"
    target.role = "owner"
    await db.commit()
    return await list_team(company, db)

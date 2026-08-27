"""Platform-wide administration, deliberately isolated from tenant-scoped APIs."""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.billing import transaction_out, transaction_query
from app.core.db import get_db
from app.core.deps import CurrentPlatformAdmin
from app.core.logging import get_logger
from app.core.redis_client import get_redis
from app.models import (
    AdminAuditLog,
    Application,
    BalanceTransaction,
    Bot,
    Branch,
    Company,
    CompanyMember,
    User,
    Vacancy,
)
from app.schemas import (
    AdminAuditOut,
    AdminCompanyDetail,
    AdminCompanyItem,
    AdminCompanyMemberOut,
    AdminCompanyPage,
    AdminCompanyUpdate,
    AdminStatsOut,
    BalanceTopUpRequest,
    BalanceTransactionOut,
    BalanceTransactionPage,
)
from app.services.billing import top_up_balance

router = APIRouter(prefix="/admin", tags=["platform-admin"])
DB = Annotated[AsyncSession, Depends(get_db)]
log = get_logger(__name__)


async def _count(db: AsyncSession, model, *criteria) -> int:
    return int(await db.scalar(select(func.count()).select_from(model).where(*criteria)) or 0)


async def _audit_items(
    db: AsyncSession, *, company_id: uuid.UUID | None = None, limit: int = 20
) -> list[AdminAuditOut]:
    stmt = (
        select(AdminAuditLog, User.email, Company.name)
        .join(User, User.id == AdminAuditLog.actor_user_id)
        .outerjoin(Company, Company.id == AdminAuditLog.target_company_id)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(limit)
    )
    if company_id is not None:
        stmt = stmt.where(AdminAuditLog.target_company_id == company_id)
    rows = (await db.execute(stmt)).all()
    return [
        AdminAuditOut(
            id=audit.id,
            actor_email=actor_email,
            target_company_id=audit.target_company_id,
            target_company_name=company_name,
            action=audit.action,
            details=audit.details,
            created_at=audit.created_at,
        )
        for audit, actor_email, company_name in rows
    ]


def _company_list_query():
    owner_email = (
        select(User.email)
        .join(CompanyMember, CompanyMember.user_id == User.id)
        .where(
            CompanyMember.company_id == Company.id,
            CompanyMember.role == "owner",
        )
        .limit(1)
        .correlate(Company)
        .scalar_subquery()
    )
    bot_username = (
        select(Bot.bot_username)
        .where(Bot.company_id == Company.id)
        .correlate(Company)
        .scalar_subquery()
    )
    members_count = (
        select(func.count())
        .select_from(CompanyMember)
        .where(CompanyMember.company_id == Company.id)
        .correlate(Company)
        .scalar_subquery()
    )
    vacancies_count = (
        select(func.count())
        .select_from(Vacancy)
        .where(Vacancy.company_id == Company.id)
        .correlate(Company)
        .scalar_subquery()
    )
    applications_count = (
        select(func.count())
        .select_from(Application)
        .where(Application.company_id == Company.id)
        .correlate(Company)
        .scalar_subquery()
    )
    return select(
        Company,
        owner_email.label("owner_email"),
        bot_username.label("bot_username"),
        members_count.label("members_count"),
        vacancies_count.label("vacancies_count"),
        applications_count.label("applications_count"),
    )


def _to_company_item(row) -> AdminCompanyItem:
    company, owner_email, bot_username, members, vacancies, applications = row
    return AdminCompanyItem(
        id=company.id,
        name=company.name,
        slug=company.slug,
        billing_mode=company.billing_mode,
        balance_uzs=company.balance_uzs,
        application_price_uzs=company.application_price_uzs,
        is_suspended=company.is_suspended,
        suspension_reason=company.suspension_reason,
        owner_email=owner_email,
        bot_username=bot_username,
        members_count=members,
        vacancies_count=vacancies,
        applications_count=applications,
        created_at=company.created_at,
    )


@router.get("/stats", response_model=AdminStatsOut)
async def stats(_: CurrentPlatformAdmin, db: DB) -> AdminStatsOut:
    return AdminStatsOut(
        companies_total=await _count(db, Company),
        companies_active=await _count(db, Company, Company.is_suspended.is_(False)),
        companies_suspended=await _count(db, Company, Company.is_suspended.is_(True)),
        users_total=await _count(db, User),
        bots_active=int(
            await db.scalar(
                select(func.count())
                .select_from(Bot)
                .join(Company, Company.id == Bot.company_id)
                .where(Bot.is_active.is_(True), Company.is_suspended.is_(False))
            )
            or 0
        ),
        applications_total=await _count(db, Application),
    )


@router.get("/companies", response_model=AdminCompanyPage)
async def list_companies(
    _: CurrentPlatformAdmin,
    db: DB,
    q: Annotated[str | None, Query(max_length=120)] = None,
    tenant_status: Literal["all", "active", "suspended"] = "all",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> AdminCompanyPage:
    filters = []
    if q and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(or_(Company.name.ilike(pattern), Company.slug.ilike(pattern)))
    if tenant_status == "active":
        filters.append(Company.is_suspended.is_(False))
    elif tenant_status == "suspended":
        filters.append(Company.is_suspended.is_(True))

    total = int(
        await db.scalar(select(func.count()).select_from(Company).where(*filters)) or 0
    )
    rows = (
        await db.execute(
            _company_list_query()
            .where(*filters)
            .order_by(Company.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return AdminCompanyPage(
        items=[_to_company_item(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/companies/{company_id}", response_model=AdminCompanyDetail)
async def get_company(
    company_id: uuid.UUID, _: CurrentPlatformAdmin, db: DB
) -> AdminCompanyDetail:
    row = (await db.execute(_company_list_query().where(Company.id == company_id))).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    company = row[0]
    item = _to_company_item(row)
    member_rows = (
        await db.execute(
            select(User, CompanyMember.role, CompanyMember.created_at)
            .join(CompanyMember, CompanyMember.user_id == User.id)
            .where(CompanyMember.company_id == company_id)
            .order_by(CompanyMember.created_at)
        )
    ).all()
    return AdminCompanyDetail(
        **item.model_dump(),
        logo_url=company.logo_url,
        default_language=company.default_language,
        enabled_languages=company.enabled_languages,
        branches_count=await _count(db, Branch, Branch.company_id == company_id),
        members=[
            AdminCompanyMemberOut(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=role,
                created_at=joined_at,
            )
            for user, role, joined_at in member_rows
        ],
        recent_audit=await _audit_items(db, company_id=company_id),
    )


@router.patch("/companies/{company_id}", response_model=AdminCompanyDetail)
async def update_company(
    company_id: uuid.UUID,
    payload: AdminCompanyUpdate,
    admin: CurrentPlatformAdmin,
    db: DB,
) -> AdminCompanyDetail:
    company = await db.get(Company, company_id)
    if company is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")

    data = payload.model_dump(exclude_unset=True)
    changes: dict[str, dict[str, object]] = {}
    if "billing_mode" in data and data["billing_mode"] != company.billing_mode:
        changes["billing_mode"] = {
            "from": company.billing_mode,
            "to": data["billing_mode"],
        }
        company.billing_mode = data["billing_mode"]
    if (
        "application_price_uzs" in data
        and data["application_price_uzs"] != company.application_price_uzs
    ):
        changes["application_price_uzs"] = {
            "from": company.application_price_uzs,
            "to": data["application_price_uzs"],
        }
        company.application_price_uzs = data["application_price_uzs"]
    if "is_suspended" in data and data["is_suspended"] != company.is_suspended:
        suspended = bool(data["is_suspended"])
        changes["is_suspended"] = {"from": company.is_suspended, "to": suspended}
        company.is_suspended = suspended
        company.suspension_reason = (
            (data.get("suspension_reason") or "").strip() if suspended else None
        )
        company.suspended_at = datetime.now(UTC) if suspended else None
        company.suspended_by_user_id = admin.id if suspended else None

    if changes:
        db.add(
            AdminAuditLog(
                actor_user_id=admin.id,
                target_company_id=company.id,
                action="company.updated",
                details={"changes": changes, "reason": company.suspension_reason},
            )
        )
        await db.commit()
        bot_id = await db.scalar(select(Bot.id).where(Bot.company_id == company.id))
        if bot_id:
            redis = get_redis()
            try:
                await redis.delete(f"bot:auth:{bot_id}")
            except Exception as exc:  # noqa: BLE001
                log.warning("admin_cache_invalidation_failed", error=str(exc))
            finally:
                await redis.aclose()

    return await get_company(company_id, admin, db)


@router.post(
    "/companies/{company_id}/balance/top-up",
    response_model=BalanceTransactionOut,
    status_code=status.HTTP_201_CREATED,
)
async def top_up_company_balance(
    company_id: uuid.UUID,
    payload: BalanceTopUpRequest,
    admin: CurrentPlatformAdmin,
    db: DB,
) -> BalanceTransactionOut:
    try:
        transaction = await top_up_balance(
            db,
            company_id,
            payload.amount_uzs,
            admin.id,
            payload.description,
        )
    except LookupError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found") from None
    db.add(
        AdminAuditLog(
            actor_user_id=admin.id,
            target_company_id=company_id,
            action="balance.topped_up",
            details={
                "amount_uzs": payload.amount_uzs,
                "description": payload.description,
            },
        )
    )
    await db.commit()
    row = (
        await db.execute(
            transaction_query(company_id).where(BalanceTransaction.id == transaction.id)
        )
    ).one()
    return transaction_out(row)


@router.get(
    "/companies/{company_id}/billing/transactions",
    response_model=BalanceTransactionPage,
)
async def company_balance_transactions(
    company_id: uuid.UUID,
    _: CurrentPlatformAdmin,
    db: DB,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> BalanceTransactionPage:
    if await db.get(Company, company_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    total = int(
        await db.scalar(
            select(func.count())
            .select_from(BalanceTransaction)
            .where(BalanceTransaction.company_id == company_id)
        )
        or 0
    )
    rows = (
        await db.execute(
            transaction_query(company_id)
            .order_by(BalanceTransaction.created_at.desc(), BalanceTransaction.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return BalanceTransactionPage(
        items=[transaction_out(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/audit", response_model=list[AdminAuditOut])
async def list_audit(
    _: CurrentPlatformAdmin,
    db: DB,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AdminAuditOut]:
    return await _audit_items(db, limit=limit)

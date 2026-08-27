"""Tenant-visible billing summary and immutable balance history."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import CurrentCompany, OwnerMembership
from app.models import Application, BalanceTransaction, User, Vacancy
from app.schemas import BalanceTransactionOut, BalanceTransactionPage, BillingSummaryOut

router = APIRouter(prefix="/billing", tags=["billing"])
DB = Annotated[AsyncSession, Depends(get_db)]


def transaction_out(row) -> BalanceTransactionOut:
    transaction, vacancy_title, created_by_email = row
    return BalanceTransactionOut(
        id=transaction.id,
        amount_uzs=transaction.amount_uzs,
        balance_after_uzs=transaction.balance_after_uzs,
        kind=transaction.kind,
        description=transaction.description,
        application_id=transaction.application_id,
        vacancy_title=vacancy_title,
        created_by_email=created_by_email,
        created_at=transaction.created_at,
    )


def transaction_query(company_id):
    return (
        select(BalanceTransaction, Vacancy.title, User.email)
        .outerjoin(Application, Application.id == BalanceTransaction.application_id)
        .outerjoin(Vacancy, Vacancy.id == Application.vacancy_id)
        .outerjoin(User, User.id == BalanceTransaction.created_by_user_id)
        .where(BalanceTransaction.company_id == company_id)
    )


@router.get("/summary", response_model=BillingSummaryOut)
async def summary(company: CurrentCompany, _: OwnerMembership) -> BillingSummaryOut:
    remaining = None
    if company.billing_mode == "pay_per_application":
        remaining = company.balance_uzs // company.application_price_uzs
    return BillingSummaryOut(
        billing_mode=company.billing_mode,
        balance_uzs=company.balance_uzs,
        application_price_uzs=company.application_price_uzs,
        remaining_applications=remaining,
    )


@router.get("/transactions", response_model=BalanceTransactionPage)
async def transactions(
    company: CurrentCompany,
    _: OwnerMembership,
    db: DB,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> BalanceTransactionPage:
    total = int(
        await db.scalar(
            select(func.count())
            .select_from(BalanceTransaction)
            .where(BalanceTransaction.company_id == company.id)
        )
        or 0
    )
    rows = (
        await db.execute(
            transaction_query(company.id)
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

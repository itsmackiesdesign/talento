"""Atomic prepaid balance operations for pay-per-application tenants."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BalanceTransaction, Company


class InsufficientBalanceError(Exception):
    pass


async def can_accept_application(db: AsyncSession, company_id: uuid.UUID) -> bool:
    row = (
        await db.execute(
            select(
                Company.billing_mode,
                Company.balance_uzs,
                Company.application_price_uzs,
            ).where(Company.id == company_id)
        )
    ).first()
    if row is None:
        return False
    mode, balance, price = row
    return mode == "unlimited" or balance >= price


async def lock_billable_company(db: AsyncSession, company_id: uuid.UUID) -> Company:
    """Lock the tenant until application creation and any debit commit together."""
    company = await db.scalar(
        select(Company).where(Company.id == company_id).with_for_update()
    )
    if company is None:
        raise InsufficientBalanceError
    if (
        company.billing_mode == "pay_per_application"
        and company.balance_uzs < company.application_price_uzs
    ):
        raise InsufficientBalanceError
    return company


def charge_application(
    db: AsyncSession,
    company: Company,
    application_id: uuid.UUID,
    vacancy_title: str,
) -> BalanceTransaction | None:
    if company.billing_mode != "pay_per_application":
        return None
    amount = company.application_price_uzs
    company.balance_uzs -= amount
    transaction = BalanceTransaction(
        company_id=company.id,
        amount_uzs=-amount,
        balance_after_uzs=company.balance_uzs,
        kind="application_charge",
        description=f"Application: {vacancy_title}"[:500],
        application_id=application_id,
    )
    db.add(transaction)
    return transaction


async def top_up_balance(
    db: AsyncSession,
    company_id: uuid.UUID,
    amount_uzs: int,
    actor_user_id: uuid.UUID,
    description: str | None,
) -> BalanceTransaction:
    company = await db.scalar(
        select(Company).where(Company.id == company_id).with_for_update()
    )
    if company is None:
        raise LookupError("Company not found")
    company.balance_uzs += amount_uzs
    transaction = BalanceTransaction(
        company_id=company.id,
        amount_uzs=amount_uzs,
        balance_after_uzs=company.balance_uzs,
        kind="top_up",
        description=(description or "Balance top-up").strip()[:500],
        created_by_user_id=actor_user_id,
    )
    db.add(transaction)
    return transaction

"""Prepaid pay-per-application billing and ledger behavior."""

from sqlalchemy import select

from app.models import Application, BalanceTransaction, Company, User
from tests.conftest import TestSession, feed, make_company, register


async def make_admin(client, db):
    account = await register(client, "billing-admin@example.com")
    user = await db.scalar(select(User).where(User.email == account["email"]))
    user.is_platform_admin = True
    await db.commit()
    return account


async def test_new_tenant_gets_pay_per_application_and_welcome_bonus(client):
    tenant = await make_company(client)
    response = await client.get("/api/v1/billing/summary", headers=tenant["headers"])
    assert response.status_code == 200
    assert response.json() == {
        "billing_mode": "pay_per_application",
        "balance_uzs": 20_000,
        "application_price_uzs": 2000,
        "remaining_applications": 10,
    }
    history = await client.get(
        "/api/v1/billing/transactions", headers=tenant["headers"]
    )
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["kind"] == "signup_bonus"
    assert history.json()["items"][0]["amount_uzs"] == 20_000
    assert history.json()["items"][0]["balance_after_uzs"] == 20_000


async def test_admin_configures_billing_and_tops_up_balance(client, db):
    admin = await make_admin(client, db)
    tenant = await make_company(client)
    configured = await client.patch(
        f"/api/v1/admin/companies/{tenant['company_id']}",
        json={"billing_mode": "pay_per_application", "application_price_uzs": 3500},
        headers=admin["headers"],
    )
    assert configured.status_code == 200
    assert configured.json()["billing_mode"] == "pay_per_application"
    assert configured.json()["application_price_uzs"] == 3500

    topped_up = await client.post(
        f"/api/v1/admin/companies/{tenant['company_id']}/balance/top-up",
        json={"amount_uzs": 10_000, "description": "Bank transfer"},
        headers=admin["headers"],
    )
    assert topped_up.status_code == 201
    assert topped_up.json()["amount_uzs"] == 10_000
    assert topped_up.json()["balance_after_uzs"] == 30_000

    summary = await client.get("/api/v1/billing/summary", headers=tenant["headers"])
    assert summary.json()["balance_uzs"] == 30_000
    assert summary.json()["remaining_applications"] == 8
    history = await client.get(
        "/api/v1/billing/transactions", headers=tenant["headers"]
    )
    assert history.json()["items"][0]["description"] == "Bank transfer"
    assert history.json()["items"][0]["created_by_email"] == admin["email"]


async def test_tenant_cannot_top_up_its_own_balance(client):
    tenant = await make_company(client)
    response = await client.post(
        f"/api/v1/admin/companies/{tenant['company_id']}/balance/top-up",
        json={"amount_uzs": 10_000},
        headers=tenant["headers"],
    )
    assert response.status_code == 403


async def test_application_debits_configured_price(bot, session, tenant):
    async with TestSession() as db:
        company = await db.get(Company, tenant["company_id"])
        company.billing_mode = "pay_per_application"
        company.balance_uzs = 5_000
        company.application_price_uzs = 2_000
        await db.commit()

    await feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")

    async with TestSession() as db:
        application = await db.scalar(select(Application))
        transaction = await db.scalar(select(BalanceTransaction))
        company = await db.get(Company, tenant["company_id"])
    assert application is not None
    assert transaction.application_id == application.id
    assert transaction.amount_uzs == -2_000
    assert transaction.balance_after_uzs == 3_000
    assert company.balance_uzs == 3_000
    assert "Спасибо" in session.last_text


async def test_insufficient_balance_rejects_application_without_debit(bot, session, tenant):
    async with TestSession() as db:
        company = await db.get(Company, tenant["company_id"])
        company.billing_mode = "pay_per_application"
        company.balance_uzs = 1_999
        company.application_price_uzs = 2_000
        await db.commit()

    await feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")

    assert "временно недоступен" in session.last_text
    async with TestSession() as db:
        assert await db.scalar(select(Application)) is None
        assert await db.scalar(select(BalanceTransaction)) is None
        company = await db.get(Company, tenant["company_id"])
        assert company.balance_uzs == 1_999


async def test_unlimited_application_creates_no_balance_transaction(bot, tenant):
    await feed(bot, tenant, data=f"apply:{tenant['vacancy_id'].hex}")
    async with TestSession() as db:
        assert await db.scalar(select(Application)) is not None
        assert await db.scalar(select(BalanceTransaction)) is None


async def test_balance_history_is_tenant_isolated(client, db):
    admin = await make_admin(client, db)
    first = await make_company(client, "First")
    second = await make_company(client, "Second")
    await client.post(
        f"/api/v1/admin/companies/{first['company_id']}/balance/top-up",
        json={"amount_uzs": 1111},
        headers=admin["headers"],
    )
    await client.post(
        f"/api/v1/admin/companies/{second['company_id']}/balance/top-up",
        json={"amount_uzs": 2222},
        headers=admin["headers"],
    )
    history = await client.get(
        "/api/v1/billing/transactions", headers=first["headers"]
    )
    assert [item["amount_uzs"] for item in history.json()["items"]] == [1111, 20_000]

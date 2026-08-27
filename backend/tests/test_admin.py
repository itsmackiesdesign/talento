"""Platform-admin authorization, tenant controls, and audit coverage."""

from sqlalchemy import select

from app.core.crypto import encrypt
from app.models import Bot, User
from tests.conftest import make_company, register


async def make_admin(client, db):
    account = await register(client, "platform-admin@example.com")
    user = await db.scalar(select(User).where(User.email == account["email"]))
    user.is_platform_admin = True
    await db.commit()
    return account


async def test_regular_user_cannot_access_admin_api(client):
    user = await register(client)
    response = await client.get("/api/v1/admin/stats", headers=user["headers"])
    assert response.status_code == 403


async def test_admin_can_see_cross_tenant_stats_and_list(client, db):
    admin = await make_admin(client, db)
    first = await make_company(client, "First Tenant")
    second = await make_company(client, "Second Tenant")

    stats = await client.get("/api/v1/admin/stats", headers=admin["headers"])
    assert stats.status_code == 200
    assert stats.json()["companies_total"] == 2
    assert stats.json()["users_total"] == 3

    response = await client.get(
        "/api/v1/admin/companies",
        params={"q": "Second"},
        headers=admin["headers"],
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == second["company_id"]
    assert response.json()["items"][0]["owner_email"] == second["email"]
    assert response.json()["items"][0]["id"] != first["company_id"]


async def test_suspend_blocks_tenant_and_writes_audit(client, db):
    admin = await make_admin(client, db)
    tenant = await make_company(client, "Suspended Tenant")

    response = await client.patch(
        f"/api/v1/admin/companies/{tenant['company_id']}",
        json={"is_suspended": True, "suspension_reason": "Terms violation"},
        headers=admin["headers"],
    )
    assert response.status_code == 200
    assert response.json()["is_suspended"] is True
    assert response.json()["recent_audit"][0]["action"] == "company.updated"

    blocked = await client.get("/api/v1/company", headers=tenant["headers"])
    assert blocked.status_code == 403
    assert "suspended" in blocked.json()["detail"].lower()

    restored = await client.patch(
        f"/api/v1/admin/companies/{tenant['company_id']}",
        json={"is_suspended": False},
        headers=admin["headers"],
    )
    assert restored.status_code == 200
    assert restored.json()["is_suspended"] is False
    assert (await client.get("/api/v1/company", headers=tenant["headers"])).status_code == 200


async def test_suspension_requires_reason(client, db):
    admin = await make_admin(client, db)
    tenant = await make_company(client)
    response = await client.patch(
        f"/api/v1/admin/companies/{tenant['company_id']}",
        json={"is_suspended": True},
        headers=admin["headers"],
    )
    assert response.status_code == 422


async def test_suspended_tenant_bot_stops_processing_updates(client, db):
    admin = await make_admin(client, db)
    tenant = await make_company(client)
    bot = Bot(
        company_id=tenant["company_id"],
        token_encrypted=encrypt("123456789:AAHfake-token-for-tests"),
        bot_username="suspended_bot",
        webhook_secret="suspension-secret",
    )
    db.add(bot)
    await db.commit()

    suspended = await client.patch(
        f"/api/v1/admin/companies/{tenant['company_id']}",
        json={"is_suspended": True, "suspension_reason": "Administrative review"},
        headers=admin["headers"],
    )
    assert suspended.status_code == 200

    webhook = await client.post(
        f"/webhook/{bot.id}/{bot.webhook_secret}",
        headers={"X-Telegram-Bot-Api-Secret-Token": bot.webhook_secret},
        json={"update_id": 1},
    )
    assert webhook.status_code == 200
    assert webhook.json() == {"ok": True, "skipped": "bot_inactive"}

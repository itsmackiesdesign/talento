"""Platform-bot notification group linking."""

import uuid

from sqlalchemy import select

from app.api import notifications
from app.models import Company, CompanyMember, User
from tests.conftest import TestSession, make_company, register


async def test_owner_links_and_unlinks_notification_group(client, monkeypatch):
    owner = await make_company(client, "Acme Coffee")
    sent: list[tuple[int, str]] = []

    async def send_message(token, chat_id, text, **kwargs):
        sent.append((chat_id, text))

    monkeypatch.setattr(notifications.settings, "PLATFORM_BOT_TOKEN", "platform-token")
    monkeypatch.setattr(notifications.settings, "PLATFORM_BOT_USERNAME", "talento_notify_bot")
    monkeypatch.setattr(notifications.tg, "send_message", send_message)

    response = await client.get(
        "/api/v1/notifications/link-code", headers=owner["headers"]
    )
    assert response.status_code == 200, response.text
    code = response.json()["code"]
    assert f"startgroup=link_{code}" in response.json()["deep_link"]

    # Sending a valid code privately must not consume it.
    await notifications.handle_platform_update(
        {
            "message": {
                "text": f"/link {code}",
                "chat": {"id": 123, "type": "private"},
            }
        }
    )
    assert "внутри группы" in sent[-1][1]

    await notifications.handle_platform_update(
        {
            "message": {
                "text": f"/link@talento_notify_bot {code}",
                "chat": {
                    "id": -100123456789,
                    "type": "supergroup",
                    "title": "Acme HR",
                },
            }
        }
    )
    assert "Новые заявки будут приходить сюда" in sent[-1][1]

    company = await client.get("/api/v1/company", headers=owner["headers"])
    assert company.json()["notification_chat_id"] == -100123456789
    assert company.json()["notification_chat_title"] == "Acme HR"

    unlinked = await client.delete(
        "/api/v1/notifications/link", headers=owner["headers"]
    )
    assert unlinked.status_code == 204
    company = await client.get("/api/v1/company", headers=owner["headers"])
    assert company.json()["notification_chat_id"] is None


async def test_member_cannot_change_notification_group(client, monkeypatch):
    owner = await make_company(client)
    member = await register(client, "member@example.com")
    async with TestSession() as db:
        user = await db.scalar(select(User).where(User.email == member["email"]))
        assert user is not None
        db.add(
            CompanyMember(
                company_id=uuid.UUID(owner["company_id"]),
                user_id=user.id,
                role="member",
            )
        )
        await db.commit()

    monkeypatch.setattr(notifications.settings, "PLATFORM_BOT_TOKEN", "platform-token")
    assert (
        await client.get("/api/v1/notifications/link-code", headers=member["headers"])
    ).status_code == 403
    assert (
        await client.delete("/api/v1/notifications/link", headers=member["headers"])
    ).status_code == 403


async def test_one_group_cannot_be_linked_to_two_companies(client, monkeypatch):
    first = await make_company(client, "First")
    second = await make_company(client, "Second")
    sent: list[str] = []

    async def send_message(token, chat_id, text, **kwargs):
        sent.append(text)

    monkeypatch.setattr(notifications.settings, "PLATFORM_BOT_TOKEN", "platform-token")
    monkeypatch.setattr(notifications.tg, "send_message", send_message)

    async with TestSession() as db:
        company = await db.get(Company, uuid.UUID(first["company_id"]))
        assert company is not None
        company.notification_chat_id = -100987654321
        company.notification_chat_title = "First HR"
        await db.commit()

    response = await client.get(
        "/api/v1/notifications/link-code", headers=second["headers"]
    )
    await notifications.handle_platform_update(
        {
            "message": {
                "text": f"/link {response.json()['code']}",
                "chat": {
                    "id": -100987654321,
                    "type": "group",
                    "title": "Shared HR",
                },
            }
        }
    )

    assert "другой компании" in sent[-1]

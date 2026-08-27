"""Bot connection and webhook authentication."""

import uuid
from unittest.mock import AsyncMock, patch

from sqlalchemy import select

from app.api import webhook as webhook_api
from app.core.crypto import decrypt, encrypt, mask_token
from app.models import Bot as BotModel
from tests.conftest import TestSession, make_company

TOKEN = "123456789:AAHfake-token-for-tests"


async def _connect_bot(client, owner, token=TOKEN):
    with (
        patch("app.services.telegram.get_me", new=AsyncMock(return_value={"username": "acme_bot"})),
        patch("app.services.telegram.set_webhook", new=AsyncMock(return_value=True)) as setter,
    ):
        resp = await client.post("/api/v1/bot", json={"token": token}, headers=owner["headers"])
    return resp, setter


async def test_connect_bot_validates_and_registers_webhook(client):
    owner = await make_company(client)
    resp, setter = await _connect_bot(client, owner)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["bot_username"] == "acme_bot"
    # The raw token must never come back over the wire.
    assert TOKEN not in resp.text
    assert body["token_hint"] == mask_token(TOKEN)

    setter.assert_awaited_once()
    url = setter.await_args.args[1]
    assert url.startswith("https://test.example.com/webhook/")


async def test_token_is_encrypted_at_rest(client):
    owner = await make_company(client)
    await _connect_bot(client, owner)

    async with TestSession() as db:
        row = await db.scalar(select(BotModel))
    assert row.token_encrypted != TOKEN
    assert decrypt(row.token_encrypted) == TOKEN


async def test_invalid_token_is_422_with_a_readable_message(client):
    from app.services.telegram import TelegramError

    owner = await make_company(client)
    with patch(
        "app.services.telegram.get_me",
        new=AsyncMock(side_effect=TelegramError("Unauthorized", 401)),
    ):
        resp = await client.post(
            "/api/v1/bot", json={"token": TOKEN}, headers=owner["headers"]
        )
    assert resp.status_code == 422
    assert "Unauthorized" in resp.json()["detail"]


async def test_malformed_token_is_rejected_before_calling_telegram(client):
    owner = await make_company(client)
    resp = await client.post(
        "/api/v1/bot", json={"token": "not-a-real-token-at-all"}, headers=owner["headers"]
    )
    assert resp.status_code == 422


async def test_second_bot_is_conflict(client):
    owner = await make_company(client)
    await _connect_bot(client, owner)
    resp, _ = await _connect_bot(client, owner)
    assert resp.status_code == 409


async def test_member_cannot_change_bot_settings(client, db):
    """Bot settings are owner-only (spec §2)."""
    from app.models import CompanyMember, User

    owner = await make_company(client)
    await _connect_bot(client, owner)

    from tests.conftest import register

    member = await register(client)
    async with TestSession() as session:
        user = await session.scalar(select(User).where(User.email == member["email"]))
        session.add(
            CompanyMember(
                company_id=uuid.UUID(owner["company_id"]), user_id=user.id, role="member"
            )
        )
        await session.commit()

    resp = await client.patch(
        "/api/v1/bot", json={"about_text": "hacked"}, headers=member["headers"]
    )
    assert resp.status_code == 403


# --------------------------------------------------------------------------- webhook


async def _make_bot_row(company_id: uuid.UUID, secret: str = "correct-secret") -> uuid.UUID:
    async with TestSession() as db:
        row = BotModel(
            company_id=company_id,
            token_encrypted=encrypt(TOKEN),
            bot_username="acme_bot",
            webhook_secret=secret,
        )
        db.add(row)
        await db.commit()
        return row.id


async def test_webhook_rejects_wrong_path_secret(client):
    owner = await make_company(client)
    bot_id = await _make_bot_row(uuid.UUID(owner["company_id"]))

    resp = await client.post(
        f"/webhook/{bot_id}/wrong-secret",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "correct-secret"},
    )
    assert resp.status_code == 403


async def test_webhook_rejects_missing_header(client):
    """A leaked URL alone must not be enough to forge updates."""
    owner = await make_company(client)
    bot_id = await _make_bot_row(uuid.UUID(owner["company_id"]))

    resp = await client.post(f"/webhook/{bot_id}/correct-secret", json={"update_id": 1})
    assert resp.status_code == 403


async def test_webhook_rejects_wrong_header(client):
    owner = await make_company(client)
    bot_id = await _make_bot_row(uuid.UUID(owner["company_id"]))

    resp = await client.post(
        f"/webhook/{bot_id}/correct-secret",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "nope"},
    )
    assert resp.status_code == 403


async def test_webhook_rejects_unknown_bot(client):
    resp = await client.post(
        f"/webhook/{uuid.uuid4()}/whatever",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "whatever"},
    )
    assert resp.status_code == 403


async def test_webhook_accepts_valid_request(client):
    owner = await make_company(client)
    bot_id = await _make_bot_row(uuid.UUID(owner["company_id"]))

    resp = await client.post(
        f"/webhook/{bot_id}/correct-secret",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "correct-secret"},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


async def test_platform_webhook_is_not_captured_by_tenant_uuid_route(client, monkeypatch):
    handler = AsyncMock()
    monkeypatch.setattr(webhook_api.settings, "PLATFORM_BOT_TOKEN", TOKEN)
    monkeypatch.setattr(webhook_api, "_process_platform_update", handler)
    secret = webhook_api.platform_webhook_secret()
    payload = {"update_id": 1, "message": {"text": "/start"}}

    resp = await client.post(f"/webhook/platform/{secret}", json=payload)

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"ok": True}
    handler.assert_awaited_once_with(payload)


async def test_inactive_bot_skips_processing(client):
    owner = await make_company(client)
    async with TestSession() as db:
        row = BotModel(
            company_id=uuid.UUID(owner["company_id"]),
            token_encrypted=encrypt(TOKEN),
            bot_username="acme_bot",
            webhook_secret="correct-secret",
            is_active=False,
        )
        db.add(row)
        await db.commit()
        bot_id = row.id

    resp = await client.post(
        f"/webhook/{bot_id}/correct-secret",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "correct-secret"},
    )
    assert resp.json()["skipped"] == "bot_inactive"

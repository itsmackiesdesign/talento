"""Durable worker hand-off for Telegram updates."""

from unittest.mock import AsyncMock

from sqlalchemy import select

from app.api import notifications
from app.models import TelegramUpdateInbox
from app.workers import tasks
from tests.conftest import TestSession


async def test_platform_inbox_processes_once_and_clears_payload(monkeypatch):
    handler = AsyncMock()
    monkeypatch.setattr(notifications, "handle_platform_update", handler)
    payload = {"update_id": 9001, "message": {"text": "/start"}}
    async with TestSession() as db:
        inbox = TelegramUpdateInbox(
            source="platform",
            dedupe_key="platform:platform:9001",
            update_id=9001,
            payload=payload,
        )
        db.add(inbox)
        await db.commit()
        inbox_id = inbox.id

    assert await tasks._dispatch_inbox_update(inbox_id) == "processed"
    assert await tasks._dispatch_inbox_update(inbox_id) == "already processed"
    handler.assert_awaited_once_with(payload)

    async with TestSession() as db:
        stored = await db.scalar(
            select(TelegramUpdateInbox).where(TelegramUpdateInbox.id == inbox_id)
        )
    assert stored is not None
    assert stored.status == "processed"
    assert stored.attempts == 1
    assert stored.payload == {}
    assert stored.processed_at is not None

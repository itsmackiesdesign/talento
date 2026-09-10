"""Durable Telegram update inbox shared by tenant and platform webhooks."""

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.db import SessionLocal
from app.models import TelegramUpdateInbox

InboxSource = Literal["tenant", "platform"]


class InvalidTelegramUpdate(ValueError):
    """The request body is not a Telegram Update and must not be acknowledged."""


@dataclass(frozen=True)
class InboxReceipt:
    inbox_id: uuid.UUID
    should_enqueue: bool


def _update_id(payload: dict) -> int:
    update_id = payload.get("update_id")
    if isinstance(update_id, bool) or not isinstance(update_id, int):
        raise InvalidTelegramUpdate("Telegram update_id is required")
    return update_id


async def store_update(
    *, source: InboxSource, payload: dict, bot_id: uuid.UUID | None = None
) -> InboxReceipt:
    """Persist a Telegram update before it is acknowledged to Telegram.

    An existing pending/processing row already has a broker job, so a webhook retry does
    not multiply queue work. A previously failed enqueue is explicitly revived.
    """

    if source == "tenant" and bot_id is None:
        raise ValueError("Tenant Telegram update needs a bot_id")
    update_id = _update_id(payload)
    scope = str(bot_id) if bot_id is not None else "platform"
    dedupe_key = f"{source}:{scope}:{update_id}"

    async with SessionLocal() as db:
        result = await db.execute(
            insert(TelegramUpdateInbox)
            .values(
                bot_id=bot_id,
                source=source,
                dedupe_key=dedupe_key,
                update_id=update_id,
                payload=payload,
            )
            .on_conflict_do_nothing(index_elements=["dedupe_key"])
            .returning(TelegramUpdateInbox.id)
        )
        inbox_id = result.scalar_one_or_none()
        if inbox_id is not None:
            await db.commit()
            return InboxReceipt(inbox_id=inbox_id, should_enqueue=True)

        inbox = await db.scalar(
            select(TelegramUpdateInbox).where(TelegramUpdateInbox.dedupe_key == dedupe_key)
        )
        if inbox is None:  # pragma: no cover - defensive only; the unique row must exist.
            raise RuntimeError("Telegram inbox conflict row disappeared")
        return InboxReceipt(inbox_id=inbox.id, should_enqueue=inbox.status == "failed")


async def mark_enqueue_failed(inbox_id: uuid.UUID, error: str) -> None:
    """Make a stored update recoverable by Telegram's next retry after broker failure."""

    async with SessionLocal() as db:
        inbox = await db.get(TelegramUpdateInbox, inbox_id, with_for_update=True)
        if inbox is None or inbox.status == "processed":
            return
        inbox.status = "failed"
        inbox.last_error = error[:2000]
        await db.commit()

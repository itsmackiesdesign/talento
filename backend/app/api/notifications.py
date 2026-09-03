"""Connect one tenant-owned Telegram group to the platform notification bot.

An owner generates a short-lived code in the panel, adds the platform bot to the desired
group, and sends ``/link CODE`` there. The code identifies the company; the group chat ID
is then persisted on that company and receives every new-application notification.
"""

import secrets
import uuid
from html import escape
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import SessionLocal, get_db
from app.core.deps import CurrentCompany, OwnerMembership
from app.core.logging import get_logger
from app.core.redis_client import get_redis
from app.models import Company
from app.schemas import LinkCodeOut
from app.services import telegram as tg

router = APIRouter(prefix="/notifications", tags=["notifications"])
log = get_logger(__name__)

DB = Annotated[AsyncSession, Depends(get_db)]

CODE_TTL_SECONDS = 600
GROUP_TYPES = {"group", "supergroup"}


@router.get("/link-code", response_model=LinkCodeOut)
async def create_link_code(
    company: CurrentCompany, _: OwnerMembership
) -> LinkCodeOut:
    if not settings.PLATFORM_BOT_TOKEN:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Telegram notifications are not configured on this instance "
            "(set PLATFORM_BOT_TOKEN).",
        )
    code = secrets.token_hex(3).upper()
    redis = get_redis()
    try:
        await redis.set(f"group-link:{code}", str(company.id), ex=CODE_TTL_SECONDS)
    finally:
        await redis.aclose()

    username = settings.PLATFORM_BOT_USERNAME
    return LinkCodeOut(
        code=code,
        expires_in=CODE_TTL_SECONDS,
        bot_username=username,
        deep_link=f"https://t.me/{username}?startgroup=link_{code}" if username else None,
    )


@router.delete("/link", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_telegram_group(
    company: CurrentCompany, _: OwnerMembership, db: DB
) -> None:
    company.notification_chat_id = None
    company.notification_chat_title = None
    await db.commit()


async def _consume_code(code: str) -> uuid.UUID | None:
    redis = get_redis()
    try:
        key = f"group-link:{code.strip().upper()}"
        raw = await redis.get(key)
        if raw is None:
            return None
        await redis.delete(key)
        return uuid.UUID(raw)
    except (ValueError, TypeError):
        return None
    finally:
        await redis.aclose()


def _link_code(text: str) -> str | None:
    command, _, argument = text.partition(" ")
    command = command.split("@", 1)[0].lower()
    argument = argument.strip()
    if command == "/start" and argument.startswith("link_"):
        return argument.removeprefix("link_")
    if command == "/link" and argument:
        return argument
    return None


async def handle_platform_update(payload: dict) -> None:
    """Handle group linking commands delivered through the platform-bot webhook."""
    message = payload.get("message") or {}
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    chat_type = chat.get("type")
    if not chat_id or not text:
        return

    token = settings.PLATFORM_BOT_TOKEN
    code = _link_code(text)
    if code is None:
        if text.split(" ", 1)[0].split("@", 1)[0].lower() == "/start":
            await tg.send_message(
                token,
                chat_id,
                "Привет! Это служебный бот Talento. Добавьте меня в рабочую группу, "
                "затем отправьте в этой группе команду <code>/link КОД</code> из панели.",
            )
        return

    if chat_type not in GROUP_TYPES:
        await tg.send_message(
            token,
            chat_id,
            "Эту команду нужно отправить внутри группы, куда должны приходить заявки.",
        )
        return

    company_id = await _consume_code(code)
    if company_id is None:
        await tg.send_message(
            token, chat_id, "Код не найден или истёк. Сгенерируйте новый в панели."
        )
        return

    async with SessionLocal() as db:
        company = await db.get(Company, company_id)
        if company is None:
            await tg.send_message(token, chat_id, "Компания не найдена.")
            return
        used_by = await db.scalar(
            select(Company.id).where(
                Company.notification_chat_id == chat_id,
                Company.id != company.id,
            )
        )
        if used_by is not None:
            await tg.send_message(
                token,
                chat_id,
                "Эта группа уже подключена к другой компании Talento.",
            )
            return
        company.notification_chat_id = chat_id
        company.notification_chat_title = chat.get("title") or "Telegram group"
        await db.commit()
        company_name = company.name

    log.info(
        "notification_group_linked",
        company_id=str(company_id),
        chat_id=chat_id,
    )
    await tg.send_message(
        token,
        chat_id,
        f"✅ Готово! Группа подключена к <b>{escape(company_name)}</b>. "
        "Новые заявки будут приходить сюда.",
    )

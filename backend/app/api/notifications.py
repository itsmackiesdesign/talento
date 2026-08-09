"""HR ↔ Telegram linking via the platform service bot.

Flow (spec §3.1 / prompt 5): the panel calls ``GET /notifications/link-code`` to get a
short-lived code, the HR sends ``/link {code}`` to the platform bot, and this module ties
the resulting ``telegram_user_id`` to their user account. From then on the notification
tasks can reach them.
"""

import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import SessionLocal, get_db
from app.core.deps import CurrentUser
from app.core.logging import get_logger
from app.core.redis_client import get_redis
from app.models import User
from app.schemas import LinkCodeOut
from app.services import telegram as tg

router = APIRouter(prefix="/notifications", tags=["notifications"])
log = get_logger(__name__)

DB = Annotated[AsyncSession, Depends(get_db)]

CODE_TTL_SECONDS = 600


@router.get("/link-code", response_model=LinkCodeOut)
async def create_link_code(user: CurrentUser) -> LinkCodeOut:
    if not settings.PLATFORM_BOT_TOKEN:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Telegram notifications are not configured on this instance "
            "(set PLATFORM_BOT_TOKEN).",
        )
    code = secrets.token_hex(3).upper()
    redis = get_redis()
    try:
        await redis.set(f"link:{code}", str(user.id), ex=CODE_TTL_SECONDS)
    finally:
        await redis.aclose()

    username = settings.PLATFORM_BOT_USERNAME
    return LinkCodeOut(
        code=code,
        expires_in=CODE_TTL_SECONDS,
        bot_username=username,
        deep_link=f"https://t.me/{username}?start=link_{code}" if username else None,
    )


@router.delete("/link", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_telegram(user: CurrentUser, db: DB) -> None:
    persisted = await db.get(User, user.id)
    if persisted is not None:
        persisted.telegram_user_id = None
        await db.commit()


async def _consume_code(code: str) -> uuid.UUID | None:
    redis = get_redis()
    try:
        key = f"link:{code.strip().upper()}"
        raw = await redis.get(key)
        if raw is None:
            return None
        await redis.delete(key)  # single use
        return uuid.UUID(raw)
    except (ValueError, TypeError):
        return None
    finally:
        await redis.aclose()


async def handle_platform_update(payload: dict) -> None:
    """Minimal update handler for the platform bot: ``/start link_CODE`` and ``/link CODE``."""
    message = payload.get("message") or {}
    text = (message.get("text") or "").strip()
    chat_id = (message.get("chat") or {}).get("id")
    tg_user_id = (message.get("from") or {}).get("id")
    if not chat_id or not tg_user_id or not text:
        return

    token = settings.PLATFORM_BOT_TOKEN
    code: str | None = None
    if text.startswith("/start"):
        arg = text[len("/start") :].strip()
        if arg.startswith("link_"):
            code = arg.removeprefix("link_")
        else:
            await tg.send_message(
                token,
                chat_id,
                "Привет! Это служебный бот Talento.\n\n"
                "Чтобы получать уведомления о новых заявках, откройте панель → "
                "Настройки → Уведомления и отправьте сюда команду <code>/link КОД</code>.",
            )
            return
    elif text.startswith("/link"):
        code = text[len("/link") :].strip()

    if not code:
        return

    user_id = await _consume_code(code)
    if user_id is None:
        await tg.send_message(
            token, chat_id, "Код не найден или истёк. Сгенерируйте новый в панели."
        )
        return

    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None:
            await tg.send_message(token, chat_id, "Пользователь не найден.")
            return
        # telegram_user_id is UNIQUE — release it from any previous account first.
        previous = await db.scalar(select(User).where(User.telegram_user_id == tg_user_id))
        if previous is not None and previous.id != user.id:
            previous.telegram_user_id = None
            await db.flush()
        user.telegram_user_id = tg_user_id
        await db.commit()
        name = user.full_name

    log.info("hr_telegram_linked", user_id=str(user_id), telegram_user_id=tg_user_id)
    await tg.send_message(
        token, chat_id, f"✅ Готово, {name}! Теперь вы будете получать уведомления о новых заявках."
    )

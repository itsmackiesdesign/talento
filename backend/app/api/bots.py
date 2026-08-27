"""Connecting, configuring and disconnecting a company's Telegram bot."""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import decrypt, encrypt, mask_token
from app.core.db import get_db
from app.core.deps import CurrentCompany, OwnerMembership
from app.core.i18n import clean_translations
from app.core.logging import get_logger
from app.core.redis_client import get_redis
from app.models import Bot
from app.schemas import BotConnect, BotOut, BotUpdate
from app.services import telegram

router = APIRouter(prefix="/bot", tags=["bot"])

TRANSLATABLE = ("welcome_message", "about_text", "after_apply_message", "contacts_text")
log = get_logger(__name__)

DB = Annotated[AsyncSession, Depends(get_db)]


def webhook_url(bot: Bot) -> str:
    return f"{settings.BASE_URL.rstrip('/')}/webhook/{bot.id}/{bot.webhook_secret}"


def _to_out(bot: Bot) -> BotOut:
    out = BotOut.model_validate(bot)
    out.token_hint = mask_token(decrypt(bot.token_encrypted))
    out.webhook_url = webhook_url(bot)
    return out


async def _invalidate_bot_cache(bot_id) -> None:
    """The webhook caches each bot's auth record; drop it whenever the bot row changes."""
    redis = get_redis()
    try:
        await redis.delete(f"bot:auth:{bot_id}")
    except Exception as exc:  # noqa: BLE001
        log.warning("cache_invalidation_failed", error=str(exc), bot_id=str(bot_id))
    finally:
        await redis.aclose()


@router.post("", response_model=BotOut, status_code=status.HTTP_201_CREATED)
async def connect_bot(
    payload: BotConnect, company: CurrentCompany, _: OwnerMembership, db: DB
) -> BotOut:
    existing = await db.scalar(select(Bot).where(Bot.company_id == company.id))
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A bot is already connected. Disconnect it before adding another.",
        )

    token = payload.token.strip()
    try:
        me = await telegram.get_me(token)
    except telegram.TelegramError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Telegram rejected this token: {exc.description}",
        ) from exc

    bot = Bot(
        company_id=company.id,
        token_encrypted=encrypt(token),
        bot_username=me.get("username", ""),
        webhook_secret=secrets.token_urlsafe(32),
        language=company.default_language,
    )
    db.add(bot)
    await db.flush()

    try:
        await telegram.set_webhook(token, webhook_url(bot), bot.webhook_secret)
    except telegram.TelegramError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Could not register the webhook: {exc.description}. "
            f"Make sure BASE_URL is a public HTTPS address (currently {settings.BASE_URL}).",
        ) from exc

    await db.commit()
    await db.refresh(bot)
    log.info("bot_connected", company_id=str(company.id), username=bot.bot_username)
    return _to_out(bot)


@router.get("", response_model=BotOut)
async def get_bot(company: CurrentCompany, _: OwnerMembership, db: DB) -> BotOut:
    bot = await db.scalar(select(Bot).where(Bot.company_id == company.id))
    if bot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bot connected yet")
    return _to_out(bot)


@router.get("/webhook-status")
async def webhook_status(company: CurrentCompany, _: OwnerMembership, db: DB) -> dict:
    """Surfaced in Settings → Bot so the user can see Telegram's own view of the webhook."""
    bot = await db.scalar(select(Bot).where(Bot.company_id == company.id))
    if bot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bot connected yet")
    try:
        info = await telegram.get_webhook_info(decrypt(bot.token_encrypted))
    except telegram.TelegramError as exc:
        return {"ok": False, "error": exc.description}
    return {
        "ok": True,
        "url": info.get("url"),
        "matches_expected": info.get("url") == webhook_url(bot),
        "pending_update_count": info.get("pending_update_count", 0),
        "last_error_message": info.get("last_error_message"),
        "last_error_date": info.get("last_error_date"),
    }


@router.patch("", response_model=BotOut)
async def update_bot(
    payload: BotUpdate, company: CurrentCompany, _: OwnerMembership, db: DB
) -> BotOut:
    bot = await db.scalar(select(Bot).where(Bot.company_id == company.id))
    if bot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bot connected yet")
    data = payload.model_dump(exclude_unset=True)
    if "translations" in data:
        data["translations"] = clean_translations(
            data["translations"], TRANSLATABLE, company.enabled_languages
        )
    for field, value in data.items():
        setattr(bot, field, value)
    await db.commit()
    await db.refresh(bot)
    await _invalidate_bot_cache(bot.id)
    return _to_out(bot)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_bot(company: CurrentCompany, _: OwnerMembership, db: DB) -> None:
    bot = await db.scalar(select(Bot).where(Bot.company_id == company.id))
    if bot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No bot connected yet")
    try:
        await telegram.delete_webhook(decrypt(bot.token_encrypted))
    except telegram.TelegramError as exc:
        # Telegram being unreachable must not strand the row in the panel.
        log.warning("delete_webhook_failed", error=exc.description, bot_id=str(bot.id))
    bot_id = bot.id
    await db.delete(bot)
    await db.commit()
    await _invalidate_bot_cache(bot_id)

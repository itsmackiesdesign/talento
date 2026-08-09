"""Multi-tenant aiogram runtime.

Architecture — one Dispatcher per process, one Bot instance per update:

* The **Dispatcher** holds handler registrations and middleware. That wiring is identical for
  every tenant and is expensive to rebuild, so it is constructed once at import time and
  reused for all 1 000+ bots the process serves.
* A **Bot** instance, by contrast, *is* the credential: it wraps one token plus its own HTTP
  session. Caching Bot objects per tenant would mean holding every customer's token in
  process memory indefinitely and leaking sessions when a token is rotated or revoked. So we
  build one per update inside a context manager and close its session immediately after —
  the cost is a few microseconds, and the token's lifetime in memory stays bounded by a
  single request.

Per-update tenant context (company, bot row, decrypted token) travels to handlers through
``dp.feed_update(..., ctx=...)``, which aiogram injects as a keyword argument.
"""

import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass

from aiogram import BaseMiddleware, Dispatcher
from aiogram import Bot as AiogramBot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import decrypt
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.models import Bot as BotModel
from app.models import Company

log = get_logger(__name__)

_dispatcher: Dispatcher | None = None


class LanguageMiddleware(BaseMiddleware):
    """Resolve the candidate's language once per update and inject it as ``lang``.

    Doing this in middleware rather than in each handler means the resolution rules live in
    exactly one place, and no handler can accidentally render half a screen in the wrong
    language by forgetting to look it up.
    """

    async def __call__(self, handler, event, data):
        from app.bot import language

        ctx: BotContext | None = data.get("ctx")
        user = data.get("event_from_user")
        if ctx is not None and user is not None:
            data["lang"] = await language.resolve(
                redis=data["redis"],
                db=data["db"],
                bot_id=ctx.bot_id,
                tg_user_id=user.id,
                telegram_language_code=user.language_code,
                enabled=ctx.company.enabled_languages,
                default=ctx.company.default_language,
            )
        else:  # pragma: no cover - updates without a user (channel posts) never reach here
            data["lang"] = ctx.lang if ctx else "ru"
        return await handler(event, data)


def get_dispatcher() -> Dispatcher:
    """Build (once) and return the process-wide Dispatcher."""
    global _dispatcher
    if _dispatcher is None:
        from app.bot.handlers import router as handlers_router

        dp = Dispatcher()
        dp.message.middleware(LanguageMiddleware())
        dp.callback_query.middleware(LanguageMiddleware())
        dp.include_router(handlers_router)
        _dispatcher = dp
        log.info("dispatcher_initialised")
    return _dispatcher


@dataclass
class BotContext:
    """Everything a handler needs to know about which tenant it is serving."""

    bot_row: BotModel
    company: Company
    token: str

    @property
    def bot_id(self) -> uuid.UUID:
        return self.bot_row.id

    @property
    def company_id(self) -> uuid.UUID:
        return self.company.id

    @property
    def lang(self) -> str:
        return self.bot_row.language or self.company.default_language or "ru"


async def get_bot_auth(redis, bot_id: uuid.UUID) -> tuple[str, bool] | None:
    """Return ``(webhook_secret, is_active)`` for the webhook's auth check.

    Cached in Redis (default 10 min) so the hot path — which runs on every candidate
    keystroke across every tenant — costs no database round-trip. ``app/api/bots.py``
    invalidates the entry whenever the bot row changes, so a disconnected bot stops being
    accepted immediately rather than after the TTL.
    """
    key = f"bot:auth:{bot_id}"
    try:
        cached = await redis.get(key)
    except Exception:  # noqa: BLE001 — fall through to the database if Redis is unavailable
        cached = None
    if cached:
        if cached == "-":
            return None
        secret, active = cached.rsplit("|", 1)
        return secret, active == "1"

    async with SessionLocal() as db:
        row = (
            await db.execute(
                select(BotModel.webhook_secret, BotModel.is_active).where(BotModel.id == bot_id)
            )
        ).first()

    value = "-" if row is None else f"{row[0]}|{'1' if row[1] else '0'}"
    try:
        await redis.set(key, value, ex=settings.BOT_TOKEN_CACHE_SECONDS)
    except Exception:  # noqa: BLE001
        pass
    return None if row is None else (row[0], row[1])


async def load_bot_context(db: AsyncSession, bot_id: uuid.UUID) -> BotContext | None:
    row = (
        await db.execute(
            select(BotModel, Company)
            .join(Company, Company.id == BotModel.company_id)
            .where(BotModel.id == bot_id)
        )
    ).first()
    if row is None:
        return None
    bot_row, company = row
    return BotContext(bot_row=bot_row, company=company, token=decrypt(bot_row.token_encrypted))


@asynccontextmanager
async def telegram_bot(token: str):
    """Yield a short-lived aiogram Bot and always close its session."""
    bot = AiogramBot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        yield bot
    finally:
        await bot.session.close()

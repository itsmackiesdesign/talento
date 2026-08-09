"""Resolving and remembering the candidate's language.

Resolution order, first hit wins:

1. Redis — what the candidate last picked in this bot (90 days).
2. ``candidates.language`` — durable copy, survives Redis eviction and restarts.
3. Telegram's ``from_user.language_code`` — a free, usually-right first guess, so a
   Russian-speaking candidate never has to touch the picker at all.
4. The company's default language.

Only languages the company actually publishes in are ever returned; a company that enables
just Uzbek will not show a Russian menu to a Russian Telegram client.
"""

import uuid

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import normalise
from app.core.logging import get_logger
from app.models import Candidate

log = get_logger(__name__)

TTL_SECONDS = 60 * 60 * 24 * 90


def _key(bot_id: uuid.UUID | str, tg_user_id: int) -> str:
    return f"lang:{bot_id}:{tg_user_id}"


def _first_enabled(*candidates: str | None, enabled: list[str]) -> str | None:
    for value in candidates:
        lang = normalise(value)
        if lang and lang in enabled:
            return lang
    return None


async def resolve(
    redis: Redis,
    db: AsyncSession,
    bot_id: uuid.UUID,
    tg_user_id: int,
    telegram_language_code: str | None,
    enabled: list[str],
    default: str,
) -> str:
    enabled = [lang for lang in (enabled or []) if normalise(lang)] or [default]

    try:
        cached = await redis.get(_key(bot_id, tg_user_id))
    except Exception as exc:  # noqa: BLE001 — never let a cache miss break the bot
        log.warning("language_cache_read_failed", error=str(exc))
        cached = None

    chosen = _first_enabled(cached, enabled=enabled)
    if chosen:
        return chosen

    stored = await db.scalar(
        select(Candidate.language).where(Candidate.telegram_user_id == tg_user_id)
    )
    return (
        _first_enabled(stored, telegram_language_code, enabled=enabled)
        or (default if default in enabled else enabled[0])
    )


async def remember(
    redis: Redis,
    db: AsyncSession,
    bot_id: uuid.UUID,
    tg_user_id: int,
    lang: str,
) -> None:
    """Persist the choice to Redis and, if the candidate already exists, to their row."""
    try:
        await redis.set(_key(bot_id, tg_user_id), lang, ex=TTL_SECONDS)
    except Exception as exc:  # noqa: BLE001
        log.warning("language_cache_write_failed", error=str(exc))

    candidate = await db.scalar(
        select(Candidate).where(Candidate.telegram_user_id == tg_user_id)
    )
    if candidate is not None and candidate.language != lang:
        candidate.language = lang
        await db.commit()

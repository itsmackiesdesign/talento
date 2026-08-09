"""The single multi-tenant Telegram webhook endpoint.

One route serves every connected bot. The path carries the bot id plus a per-bot secret,
and Telegram additionally echoes that secret in ``X-Telegram-Bot-Api-Secret-Token`` — both
are checked, in constant time, before an update is looked at.

Telegram retries any update it doesn't get a prompt 200 for, so the handler acknowledges
first and does the real work in a background task (spec §7). The auth check runs against a
small Redis-cached record so the hot path costs no database round-trip; the background task
then loads the full tenant context with its own session, which keeps every ORM instance
bound to the session that actually uses it.
"""

import secrets
import uuid
from typing import Annotated

from aiogram.types import Update
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from app.bot.runtime import get_bot_auth, get_dispatcher, load_bot_context, telegram_bot
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.core.redis_client import get_redis

router = APIRouter(tags=["webhook"])
log = get_logger(__name__)

RATE_LIMIT_PER_SECOND = 30


async def _rate_limited(redis, bot_id: uuid.UUID) -> bool:
    """Per-bot fixed window: one noisy tenant must not starve the others."""
    try:
        key = f"rl:webhook:{bot_id}"
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, 1)
        return count > RATE_LIMIT_PER_SECOND
    except Exception as exc:  # noqa: BLE001 — Redis down must not take the webhook down
        log.warning("rate_limit_check_failed", error=str(exc))
        return False


async def _process(bot_id: uuid.UUID, payload: dict) -> None:
    """Run one update through the shared Dispatcher with a fresh session and Bot."""
    redis = get_redis()
    try:
        async with SessionLocal() as db:
            ctx = await load_bot_context(db, bot_id)
            if ctx is None:
                return
            async with telegram_bot(ctx.token) as bot:
                await get_dispatcher().feed_update(
                    bot, Update.model_validate(payload), ctx=ctx, db=db, redis=redis
                )
    except Exception as exc:  # noqa: BLE001 — a failed update must not crash the worker
        log.exception("update_processing_failed", error=str(exc), bot_id=str(bot_id))
    finally:
        await redis.aclose()


@router.post("/webhook/{bot_id}/{secret}", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    bot_id: uuid.UUID,
    secret: str,
    request: Request,
    background: BackgroundTasks,
    x_telegram_bot_api_secret_token: Annotated[
        str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")
    ] = None,
) -> dict:
    redis = get_redis()
    try:
        auth = await get_bot_auth(redis, bot_id)
        if auth is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Unknown bot")
        expected, is_active = auth

        # compare_digest on both checks: a timing-based probe of either would otherwise let
        # an attacker recover the secret and forge updates for this tenant.
        path_ok = secrets.compare_digest(secret, expected)
        header_ok = secrets.compare_digest(x_telegram_bot_api_secret_token or "", expected)
        if not (path_ok and header_ok):
            log.warning(
                "webhook_auth_failed",
                bot_id=str(bot_id),
                header_present=bool(x_telegram_bot_api_secret_token),
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid webhook secret")

        if not is_active:
            return {"ok": True, "skipped": "bot_inactive"}

        if await _rate_limited(redis, bot_id):
            log.warning("webhook_rate_limited", bot_id=str(bot_id))
            return {"ok": True, "skipped": "rate_limited"}
    finally:
        await redis.aclose()

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Malformed update") from None

    background.add_task(_process, bot_id, payload)
    return {"ok": True}


@router.post("/webhook/platform/{secret}", status_code=status.HTTP_200_OK)
async def platform_webhook(secret: str, request: Request, background: BackgroundTasks) -> dict:
    """Service bot used for HR notifications and the ``/link {code}`` flow (spec §3.1)."""
    if not settings.PLATFORM_BOT_TOKEN:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Platform bot is not configured")
    if not secrets.compare_digest(secret, platform_webhook_secret()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid webhook secret")

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Malformed update") from None

    background.add_task(_process_platform_update, payload)
    return {"ok": True}


def platform_webhook_secret() -> str:
    """Derived from the platform token so it needs no extra env var, but never *is* the token."""
    import hashlib

    return hashlib.sha256(
        f"{settings.PLATFORM_BOT_TOKEN}{settings.JWT_SECRET}".encode()
    ).hexdigest()[:32]


async def _process_platform_update(payload: dict) -> None:
    from app.api.notifications import handle_platform_update

    try:
        await handle_platform_update(payload)
    except Exception as exc:  # noqa: BLE001
        log.exception("platform_update_failed", error=str(exc))

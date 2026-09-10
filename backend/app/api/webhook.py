"""The single multi-tenant Telegram webhook endpoint.

One route serves every connected bot. The path carries the bot id plus a per-bot secret,
and Telegram additionally echoes that secret in ``X-Telegram-Bot-Api-Secret-Token`` — both
are checked, in constant time, before an update is looked at.

Telegram retries any update it doesn't get a prompt 200 for. We therefore persist it to the
PostgreSQL inbox *before* acknowledgement and dispatch it through Celery afterwards. The auth
check runs against a small Redis-cached record so the hot path costs no database round-trip.
"""

import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.bot.runtime import get_bot_auth
from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis_client import get_redis
from app.services.telegram_inbox import (
    InvalidTelegramUpdate,
    mark_enqueue_failed,
    store_update,
)
from app.workers.tasks import process_telegram_update

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


def platform_webhook_secret() -> str:
    """Derived from the platform token so it needs no extra env var, but never *is* the token."""
    import hashlib

    return hashlib.sha256(
        f"{settings.PLATFORM_BOT_TOKEN}{settings.JWT_SECRET}".encode()
    ).hexdigest()[:32]


async def _enqueue(receipt) -> None:
    if not receipt.should_enqueue:
        return
    try:
        process_telegram_update.delay(str(receipt.inbox_id))
    except Exception as exc:  # noqa: BLE001 — returning non-200 asks Telegram to retry safely.
        await mark_enqueue_failed(receipt.inbox_id, f"Celery publish failed: {type(exc).__name__}")
        log.exception("telegram_inbox_enqueue_failed", inbox_id=str(receipt.inbox_id))
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Could not queue Telegram update; please retry",
        ) from exc


# Keep this static route before /webhook/{bot_id}/{secret}. Otherwise Starlette matches
# "platform" as bot_id first and FastAPI rejects it as a non-UUID with HTTP 422.
@router.post("/webhook/platform/{secret}", status_code=status.HTTP_200_OK)
async def platform_webhook(secret: str, request: Request) -> dict:
    """Service bot used for HR notifications and the ``/link {code}`` flow (spec §3.1)."""
    if not settings.PLATFORM_BOT_TOKEN:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Platform bot is not configured")
    if not secrets.compare_digest(secret, platform_webhook_secret()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid webhook secret")

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Malformed update") from None

    try:
        receipt = await store_update(source="platform", payload=payload)
    except InvalidTelegramUpdate as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    await _enqueue(receipt)
    return {"ok": True, "queued": receipt.should_enqueue}


@router.post("/webhook/{bot_id}/{secret}", status_code=status.HTTP_200_OK)
async def telegram_webhook(
    bot_id: uuid.UUID,
    secret: str,
    request: Request,
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
    finally:
        await redis.aclose()

    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Malformed update") from None

    try:
        receipt = await store_update(source="tenant", bot_id=bot_id, payload=payload)
    except InvalidTelegramUpdate as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    await _enqueue(receipt)
    return {"ok": True, "queued": receipt.should_enqueue}

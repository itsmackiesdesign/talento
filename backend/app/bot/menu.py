"""Label → action routing for bottom (reply) keyboards.

Inline keyboards carry a `callback_data` payload, so a tap arrives already identified.
Reply keyboards do not: the bot receives an ordinary text message containing whatever was
written on the button. To keep the rest of the handlers working on stable action strings
(`vac:<id>`, `opt:2`, `submit`, …), every keyboard we send also records a
``{label: action}`` map for that user, and incoming text is resolved through it.

The map lives in Redis under ``menu:{bot_id}:{tg_user_id}`` and is *replaced* on every
send, never merged. That matters: it means only the keyboard currently on screen can be
activated, so a vacancy title from three screens ago cannot be re-triggered by someone
scrolling up and tapping an old button — a real hazard with reply keyboards, which stay
visible after the message that introduced them.
"""

import json
import uuid

from redis.asyncio import Redis

from app.core.logging import get_logger

log = get_logger(__name__)

TTL_SECONDS = 60 * 60 * 24


def _key(bot_id: uuid.UUID | str, tg_user_id: int) -> str:
    return f"menu:{bot_id}:{tg_user_id}"


async def remember(
    redis: Redis, bot_id: uuid.UUID | str, tg_user_id: int, mapping: dict[str, str]
) -> None:
    """Record the label→action map for the keyboard just sent."""
    if not mapping:
        await clear(redis, bot_id, tg_user_id)
        return
    try:
        await redis.set(
            _key(bot_id, tg_user_id), json.dumps(mapping, ensure_ascii=False), ex=TTL_SECONDS
        )
    except Exception as exc:  # noqa: BLE001 — a lost map degrades to "use the menu", not a crash
        log.warning("menu_store_failed", error=str(exc))


async def resolve(
    redis: Redis, bot_id: uuid.UUID | str, tg_user_id: int, label: str
) -> str | None:
    """Return the action for a tapped label, or None if it isn't on the current keyboard."""
    try:
        raw = await redis.get(_key(bot_id, tg_user_id))
    except Exception as exc:  # noqa: BLE001
        log.warning("menu_read_failed", error=str(exc))
        return None
    if not raw:
        return None
    try:
        return json.loads(raw).get(label.strip())
    except (ValueError, AttributeError):
        return None


async def clear(redis: Redis, bot_id: uuid.UUID | str, tg_user_id: int) -> None:
    try:
        await redis.delete(_key(bot_id, tg_user_id))
    except Exception as exc:  # noqa: BLE001
        log.warning("menu_clear_failed", error=str(exc))

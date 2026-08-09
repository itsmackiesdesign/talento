"""Shared async Redis connection pool.

Used for: bot-token cache, candidate FSM state, HR Telegram link codes, rate limiting.
"""

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

_pool: ConnectionPool | None = None


def get_redis() -> Redis:
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.REDIS_URL, decode_responses=True, max_connections=50
        )
    return Redis(connection_pool=_pool)


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None

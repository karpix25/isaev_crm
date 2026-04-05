from __future__ import annotations

from typing import Optional

from redis.asyncio import Redis

from src.config import settings

_redis: Optional[Redis] = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is None:
        return
    try:
        await _redis.aclose()
    finally:
        _redis = None


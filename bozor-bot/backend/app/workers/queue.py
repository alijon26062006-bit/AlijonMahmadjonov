"""Постановка фоновых задач в arq."""
from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings

_pool = None


async def _get_pool():
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool


async def enqueue_publish(listing_id: int) -> None:
    pool = await _get_pool()
    await pool.enqueue_job("publish_listing", listing_id)


async def enqueue_notify_rejected(listing_id: int) -> None:
    pool = await _get_pool()
    await pool.enqueue_job("notify_rejected", listing_id)

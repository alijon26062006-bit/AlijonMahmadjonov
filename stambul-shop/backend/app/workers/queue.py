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


async def enqueue_new_order(order_id: int) -> None:
    pool = await _get_pool()
    await pool.enqueue_job("new_order", order_id)


async def enqueue_order_status(order_id: int) -> None:
    pool = await _get_pool()
    await pool.enqueue_job("order_status", order_id)

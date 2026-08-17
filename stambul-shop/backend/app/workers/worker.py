"""Фоновый воркер arq: уведомления по заказам.

Запуск: arq app.workers.worker.WorkerSettings
"""
from arq.connections import RedisSettings

from app.bot.factory import create_bot
from app.config import get_settings
from app.db.base import SessionMaker
from app.services import order_service


async def new_order(ctx: dict, order_id: int) -> None:
    from app.bot.handlers.orders import notify_new_order
    async with SessionMaker() as session:
        order = await order_service.load(session, order_id)
        if order:
            await notify_new_order(ctx["bot"], session, order)


async def order_status(ctx: dict, order_id: int) -> None:
    from app.bot.handlers.orders import notify_status
    async with SessionMaker() as session:
        order = await order_service.load(session, order_id)
        if order:
            await notify_status(ctx["bot"], session, order)


async def startup(ctx: dict) -> None:
    ctx["bot"] = create_bot()


async def shutdown(ctx: dict) -> None:
    await ctx["bot"].session.close()


class WorkerSettings:
    functions = [new_order, order_status]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 4
    job_timeout = 60

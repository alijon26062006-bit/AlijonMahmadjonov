"""Фоновый воркер arq: уведомления по заказам.

Запуск: arq app.workers.worker.WorkerSettings
"""
import asyncio

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


# Отделение фона держит в памяти модель на несколько сотен мегабайт.
# Пропускаем по одной фотографии за раз: на маленьком сервере две
# параллельные обработки кончаются нехваткой памяти, а не ускорением.
_studio_lock = asyncio.Semaphore(1)


async def process_photo(ctx: dict, photo_id: int,
                        background: str | None = None) -> None:
    """Подготовка одной фотографии для каталога.

    Живёт в воркере, а не в запросе: модель отделения фона занимает секунды
    и заметный кусок памяти, и держать всё это внутри HTTP-запроса нельзя.
    """
    from app.services import photo_studio
    async with _studio_lock, SessionMaker() as session:
        try:
            await photo_studio.process(session, photo_id, background)
        except photo_studio.StudioError:
            pass          # причина уже записана в самой фотографии


async def process_product_photos(ctx: dict, product_id: int,
                                 background: str | None = None) -> None:
    """Все фотографии товара — в одном стиле и с одним фоном.

    Фон определяется по первой фотографии и переиспользуется для
    остальных: иначе вид спереди окажется на светлом, а вид сбоку на сером.
    """
    from app.services import photo_studio
    async with _studio_lock, SessionMaker() as session:
        ids = await photo_studio.pending_for_product(session, product_id)
        shared = background
        for photo_id in ids:
            try:
                photo = await photo_studio.process(session, photo_id, shared)
                shared = shared or photo.background
            except photo_studio.StudioError:
                continue   # одна неудача не отменяет остальные


async def startup(ctx: dict) -> None:
    ctx["bot"] = create_bot()


async def shutdown(ctx: dict) -> None:
    await ctx["bot"].session.close()


class WorkerSettings:
    functions = [new_order, order_status, process_photo,
                 process_product_photos]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 4
    job_timeout = 600

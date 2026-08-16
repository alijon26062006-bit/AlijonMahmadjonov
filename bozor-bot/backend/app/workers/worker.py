"""Фоновый воркер arq: публикация в канал, автоархивация.

Запуск: arq app.workers.worker.WorkerSettings
"""
import html
from datetime import datetime, timedelta

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.bot import texts
from app.bot.factory import create_bot
from app.config import get_settings
from app.db.base import SessionMaker
from app.db.models import ST_APPROVED, ST_ARCHIVED, City, District, Listing, User
from app.schemas_engine.registry import get_schema
from app.services.publisher import channel_post_url, miniapp_button, publish_to_channel


async def publish_listing(ctx: dict, listing_id: int) -> None:
    bot = ctx["bot"]
    async with SessionMaker() as session:
        listing = (await session.scalars(
            select(Listing).where(Listing.id == listing_id)
            .options(selectinload(Listing.photos)))).first()
        if not listing or listing.status != ST_APPROVED:
            return
        schema = get_schema(listing.category_slug)
        city = await session.get(City, listing.city_id) if listing.city_id else None
        district = (await session.get(District, listing.district_id)
                    if listing.district_id else None)

        s = get_settings()
        if s.channel_id:
            msg_id = await publish_to_channel(
                bot, listing, schema, listing.photos,
                city.name if city else None, district.name if district else None)
            listing.channel_message_id = msg_id

        listing.published_at = datetime.utcnow()
        listing.expires_at = datetime.utcnow() + timedelta(days=s.listing_ttl_days)
        await session.commit()

        author = await session.get(User, listing.author_id)
        if author:
            try:
                text = texts.APPROVED_AUTHOR.format(title=html.escape(listing.title))
                if (url := channel_post_url(listing)):
                    text += f'\n<a href="{url}">Смотреть в канале</a>'
                await bot.send_message(author.tg_id, text,
                                       reply_markup=miniapp_button(listing))
            except Exception:
                author.bot_blocked = True
                await session.commit()


async def notify_rejected(ctx: dict, listing_id: int) -> None:
    """Сообщает автору об отклонении — одинаково для бота и админ-панели."""
    bot = ctx["bot"]
    async with SessionMaker() as session:
        listing = await session.get(Listing, listing_id)
        if not listing:
            return
        author = await session.get(User, listing.author_id)
        if not author:
            return
        try:
            await bot.send_message(
                author.tg_id,
                texts.REJECTED_AUTHOR.format(
                    reason=html.escape(listing.reject_reason or "не указана")))
        except Exception:
            author.bot_blocked = True
            await session.commit()


async def ask_seller(ctx: dict, deal_id: int) -> None:
    """Спрашивает продавца, подтверждает ли он сделку.

    Двух «да» достаточно, чтобы снять объявление, — поэтому вопрос задаётся
    именно продавцу, а не берётся на веру со слов покупателя.
    """
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    from app.db.models import DEAL_WAIT_SELLER, Deal

    bot = ctx["bot"]
    async with SessionMaker() as session:
        deal = await session.get(Deal, deal_id)
        if not deal or deal.status != DEAL_WAIT_SELLER:
            return
        listing = await session.get(Listing, deal.listing_id)
        seller = await session.get(User, deal.seller_id)
        buyer = await session.get(User, deal.buyer_id)
        if not (listing and seller):
            return

        who = f"@{buyer.username}" if buyer and buyer.username else \
              html.escape(buyer.first_name if buyer else "Покупатель")
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Да, договорились",
                                 callback_data=f"deal:yes:{deal.id}"),
            InlineKeyboardButton(text="❌ Нет",
                                 callback_data=f"deal:no:{deal.id}"),
        ]])
        try:
            await bot.send_message(
                seller.tg_id,
                texts.DEAL_ASK_SELLER.format(
                    who=who, title=html.escape(listing.title)),
                reply_markup=kb)
        except Exception:
            seller.bot_blocked = True
            await session.commit()


async def archive_expired(ctx: dict) -> None:
    async with SessionMaker() as session:
        await session.execute(
            update(Listing)
            .where(Listing.status == ST_APPROVED,
                   Listing.expires_at < datetime.utcnow())
            .values(status=ST_ARCHIVED))
        await session.commit()


async def startup(ctx: dict) -> None:
    ctx["bot"] = create_bot()


async def shutdown(ctx: dict) -> None:
    await ctx["bot"].session.close()


class WorkerSettings:
    functions = [publish_listing, notify_rejected, ask_seller]
    cron_jobs = [cron(archive_expired, hour=3, minute=0)]   # автоархив в 03:00 UTC
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 4
    job_timeout = 120

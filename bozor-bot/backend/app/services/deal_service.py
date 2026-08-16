"""Сделки: от «связаться» до «договорились».

Площадка не видит переписку — люди уходят в личку Telegram. Но она может
спросить обе стороны, чем всё кончилось, и по двум «да» снять объявление
и засчитать сделку. Спрашиваем не сразу: сначала человеку нужно успеть
поговорить.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DEAL_DONE, DEAL_FAILED, DEAL_OPEN, DEAL_WAIT_SELLER, ST_APPROVED,
    ST_OCCUPIED, ST_SOLD, Deal, Listing, User,
)
from app.schemas_engine.registry import get_schema

ASK_AFTER = timedelta(hours=2)     # раньше спрашивать бессмысленно
MAX_ASKS = 3                       # больше трёх раз не пристаём


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def open_deal(session: AsyncSession, listing: Listing,
                    buyer: User) -> Deal | None:
    """Покупатель нажал «Связаться». Свои объявления не считаем."""
    if buyer.id == listing.author_id:
        return None
    deal = await session.scalar(
        select(Deal).where(Deal.listing_id == listing.id,
                           Deal.buyer_id == buyer.id))
    if deal is None:
        deal = Deal(listing_id=listing.id, buyer_id=buyer.id,
                    seller_id=listing.author_id, status=DEAL_OPEN)
        session.add(deal)
        await session.commit()
        await session.refresh(deal)
    return deal


async def question_for_buyer(session: AsyncSession, listing: Listing,
                             viewer: User | None) -> dict | None:
    """Вопрос «вы договорились?», если пора его задать.

    Пора — когда человек уже писал продавцу, с тех пор прошло время, и мы
    ещё не получили ответа и не спросили трижды.
    """
    if viewer is None or viewer.id == listing.author_id:
        return None
    deal = await session.scalar(
        select(Deal).where(Deal.listing_id == listing.id,
                           Deal.buyer_id == viewer.id,
                           Deal.status == DEAL_OPEN))
    if deal is None or deal.asked_count >= MAX_ASKS:
        return None
    started = deal.created_at
    if started is not None and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    if started is not None and _now() - started < ASK_AFTER:
        return None

    deal.asked_count += 1
    await session.commit()
    seller = await session.get(User, listing.author_id)
    return {"deal_id": deal.id,
            "seller_name": seller.first_name if seller else "продавцом"}


async def buyer_answer(session: AsyncSession, deal_id: int, buyer: User,
                       agreed: bool) -> Deal | None:
    """Ответ покупателя. «Да» — идём спрашивать продавца."""
    deal = await session.get(Deal, deal_id)
    if deal is None or deal.buyer_id != buyer.id or deal.status != DEAL_OPEN:
        return None
    deal.buyer_answered_at = _now()
    deal.status = DEAL_WAIT_SELLER if agreed else DEAL_FAILED
    await session.commit()
    return deal


async def seller_answer(session: AsyncSession, deal_id: int, seller: User,
                        agreed: bool) -> tuple[Deal, Listing] | None:
    """Ответ продавца. Второе «да» снимает объявление с публикации.

    У аренды статус «Занято» — объявление вернётся одной кнопкой, когда жильё
    освободится. У продажи «Продано».
    """
    deal = await session.get(Deal, deal_id)
    if deal is None or deal.seller_id != seller.id or deal.status != DEAL_WAIT_SELLER:
        return None
    listing = await session.get(Listing, deal.listing_id)
    if listing is None:
        return None

    deal.seller_answered_at = _now()
    deal.status = DEAL_DONE if agreed else DEAL_FAILED
    if agreed and listing.status == ST_APPROVED:
        schema = get_schema(listing.category_slug)
        listing.status = ST_OCCUPIED if (schema and schema.is_rent) else ST_SOLD
    await session.commit()
    return deal, listing


async def pending_for_seller(session: AsyncSession, seller: User) -> list[Deal]:
    """Сделки, где ждём слова продавца."""
    return list(await session.scalars(
        select(Deal).where(Deal.seller_id == seller.id,
                           Deal.status == DEAL_WAIT_SELLER)
        .order_by(Deal.buyer_answered_at)))


async def stats(session: AsyncSession, days: int = 7) -> dict:
    """Счётчики для панели: сколько разговоров и сколько из них состоялось."""
    since = _now() - timedelta(days=days)

    async def count(*conds) -> int:
        return await session.scalar(
            select(func.count()).select_from(Deal).where(*conds)) or 0

    started = await count()
    done = await count(Deal.status == DEAL_DONE)
    return {
        "started": started,
        "done": done,
        "done_week": await count(Deal.status == DEAL_DONE,
                                 Deal.seller_answered_at > since),
        "waiting_seller": await count(Deal.status == DEAL_WAIT_SELLER),
        "failed": await count(Deal.status == DEAL_FAILED),
        # доля состоявшихся от всех начатых разговоров, в процентах
        "conversion": round(done * 100 / started) if started else 0,
    }

"""«Мои объявления»: статусы и управление, включая цикл аренды занято/свободно."""
from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import texts
from app.db.models import (
    ST_APPROVED, ST_ARCHIVED, ST_OCCUPIED, ST_SOLD, Listing, User,
)
from app.schemas_engine.registry import get_schema
from app.services.publisher import channel_post_url

router = Router()


def item_kb(listing: Listing) -> InlineKeyboardMarkup:
    schema = get_schema(listing.category_slug)
    rows = []
    if listing.status == ST_APPROVED:
        if schema and schema.is_rent:
            rows.append([InlineKeyboardButton(
                text="🔒 Занято", callback_data=f"my:occupy:{listing.id}")])
        else:
            rows.append([InlineKeyboardButton(
                text="🤝 Продано", callback_data=f"my:sold:{listing.id}")])
        rows.append([InlineKeyboardButton(
            text="📦 Снять с публикации", callback_data=f"my:archive:{listing.id}")])
        if (url := channel_post_url(listing)):
            rows.append([InlineKeyboardButton(text="↗️ Открыть в канале", url=url)])
    elif listing.status == ST_OCCUPIED:
        rows.append([InlineKeyboardButton(
            text="🔓 Снова свободно", callback_data=f"my:free:{listing.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(F.text == texts.MENU_MY)
async def my_listings(message: Message, session: AsyncSession, user: User) -> None:
    rows = (await session.scalars(
        select(Listing).where(Listing.author_id == user.id)
        .order_by(Listing.created_at.desc()).limit(10))).all()
    if not rows:
        await message.answer(texts.MY_EMPTY)
        return
    for listing in rows:
        status = texts.STATUS_LABEL.get(listing.status, listing.status)
        extra = f"\nПричина: {listing.reject_reason}" \
            if listing.status == "rejected" and listing.reject_reason else ""
        await message.answer(
            f"{status}\n<b>{listing.title}</b>{extra}",
            reply_markup=item_kb(listing))


ACTIONS = {"occupy": ST_OCCUPIED, "free": ST_APPROVED,
           "sold": ST_SOLD, "archive": ST_ARCHIVED}


@router.callback_query(F.data.startswith("my:"))
async def my_action(cb: CallbackQuery, session: AsyncSession, user: User) -> None:
    _, action, listing_id = cb.data.split(":")
    listing = await session.get(Listing, int(listing_id))
    if not listing or listing.author_id != user.id:
        await cb.answer("Не найдено", show_alert=True)
        return
    new_status = ACTIONS.get(action)
    if not new_status:
        await cb.answer()
        return
    listing.status = new_status
    await session.commit()
    await cb.answer("Готово")
    status = texts.STATUS_LABEL.get(listing.status, listing.status)
    try:
        await cb.message.edit_text(f"{status}\n<b>{listing.title}</b>",
                                   reply_markup=item_kb(listing))
    except Exception:
        pass


# ─────────────────── Подтверждение сделки продавцом ───────────────────

@router.callback_query(F.data.startswith("deal:"))
async def deal_answer(cb: CallbackQuery, session: AsyncSession, bot: Bot,
                      user: User) -> None:
    """Кнопки из вопроса «сделка состоялась?». Второе «да» снимает объявление."""
    _, verdict, raw_id = cb.data.split(":")
    from app.services import deal_service

    result = await deal_service.seller_answer(session, int(raw_id), user,
                                              verdict == "yes")
    if result is None:
        await cb.answer("Этот вопрос уже закрыт", show_alert=True)
        return
    deal, listing = result
    await cb.answer("Спасибо!")
    try:
        await cb.message.edit_text(
            cb.message.html_text + "\n\n"
            + (texts.DEAL_DONE_SELLER if verdict == "yes"
               else texts.DEAL_FAILED_SELLER))
    except Exception:
        pass

    if verdict == "yes":
        buyer = await session.get(User, deal.buyer_id)
        if buyer and not buyer.bot_blocked:
            try:
                await bot.send_message(buyer.tg_id, texts.DEAL_DONE_BUYER)
            except Exception:
                pass

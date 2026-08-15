"""Модерация в приватной группе админов.

Идемпотентность: SELECT ... FOR UPDATE — двойное нажатие двумя админами
не публикует объявление дважды.
"""
import html

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)
from aiogram.utils.media_group import MediaGroupBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.bot import texts
from app.config import get_settings
from app.db.models import (
    ST_APPROVED, ST_PENDING, ST_REJECTED, City, District, Listing,
    ModerationLog, User,
)
from app.schemas_engine.registry import get_schema
from app.services import moderation_service
from app.services.publisher import build_caption

router = Router()


class ModStates(StatesGroup):
    reason = State()


def mod_kb(listing_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"mod:ok:{listing_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"mod:no:{listing_id}")],
        [InlineKeyboardButton(text="🚫 Забанить автора", callback_data=f"mod:ban:{listing_id}")],
    ])


async def send_to_moderation(bot: Bot, session: AsyncSession, listing: Listing) -> None:
    s = get_settings()
    if not s.admin_chat_id:
        return
    schema = get_schema(listing.category_slug)
    city = await session.get(City, listing.city_id) if listing.city_id else None
    district = await session.get(District, listing.district_id) if listing.district_id else None
    author = await session.get(User, listing.author_id)

    caption = build_caption(listing, schema,
                            city.name if city else None,
                            district.name if district else None)
    photos = (await session.scalars(
        select(Listing).where(Listing.id == listing.id)
        .options(selectinload(Listing.photos)))).first().photos

    if photos:
        builder = MediaGroupBuilder()
        for i, p in enumerate(photos[:10]):
            builder.add_photo(media=p.file_id,
                              caption=caption if i == 0 else None,
                              parse_mode="HTML" if i == 0 else None)
        await bot.send_media_group(chat_id=s.admin_chat_id, media=builder.build())

    who = f"@{author.username}" if author and author.username else \
          html.escape(author.first_name if author else "?")
    flags = f"\n{html.escape(listing.flag_note)}" if listing.flag_note else ""
    await bot.send_message(
        chat_id=s.admin_chat_id,
        text=texts.MOD_NEW.format(id=listing.id,
                                  category=f"{schema.emoji} {schema.title}",
                                  author=who, flags=flags),
        reply_markup=mod_kb(listing.id))


async def _lock_pending(session: AsyncSession, listing_id: int) -> Listing | None:
    return await session.scalar(
        select(Listing).where(Listing.id == listing_id).with_for_update())


@router.callback_query(F.data.startswith("mod:ok:"))
async def approve(cb: CallbackQuery, session: AsyncSession, bot: Bot,
                  user: User) -> None:
    if not user.is_admin:
        await cb.answer("Только для админов", show_alert=True)
        return
    listing_id = int(cb.data.split(":")[2])
    try:
        await moderation_service.approve(session, listing_id, user)
    except moderation_service.AlreadyHandled as e:
        await cb.answer(texts.MOD_ALREADY.format(status=e.status), show_alert=True)
        return
    await cb.answer("Одобрено")
    try:
        await cb.message.edit_text(
            cb.message.text + "\n\n" + texts.MOD_APPROVED.format(
                admin=f"@{user.username}" if user.username else user.first_name))
    except Exception:
        pass


@router.callback_query(F.data.startswith("mod:no:"))
async def reject_menu(cb: CallbackQuery, user: User) -> None:
    if not user.is_admin:
        await cb.answer("Только для админов", show_alert=True)
        return
    listing_id = int(cb.data.split(":")[2])
    rows = [[InlineKeyboardButton(text=label, callback_data=f"mod:r:{listing_id}:{code}")]
            for code, label in texts.REJECT_REASONS]
    rows.append([InlineKeyboardButton(text=texts.BTN_BACK,
                                      callback_data=f"mod:back:{listing_id}")])
    try:
        await cb.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception:
        pass
    await cb.answer()


@router.callback_query(F.data.startswith("mod:back:"))
async def reject_back(cb: CallbackQuery) -> None:
    listing_id = int(cb.data.split(":")[2])
    try:
        await cb.message.edit_reply_markup(reply_markup=mod_kb(listing_id))
    except Exception:
        pass
    await cb.answer()


REASON_LABELS = dict(texts.REJECT_REASONS)


@router.callback_query(F.data.startswith("mod:r:"))
async def reject_reason(cb: CallbackQuery, session: AsyncSession, bot: Bot,
                        user: User, state: FSMContext) -> None:
    _, _, listing_id, code = cb.data.split(":")
    listing_id = int(listing_id)
    if code == "custom":
        await state.set_state(ModStates.reason)
        await state.update_data(listing_id=listing_id,
                                control_msg=cb.message.message_id)
        await cb.message.answer(texts.MOD_REASON_ASK)
        await cb.answer()
        return
    await _do_reject(cb, session, bot, user, listing_id, REASON_LABELS.get(code, code))


@router.message(ModStates.reason, F.text)
async def custom_reason(message: Message, session: AsyncSession, bot: Bot,
                        user: User, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    reason = message.text.strip()[:500]
    try:
        await moderation_service.reject(session, data["listing_id"], user, reason)
    except moderation_service.AlreadyHandled as e:
        await message.answer(texts.MOD_ALREADY.format(status=e.status))
        return
    await message.answer(texts.MOD_REJECTED.format(
        admin=f"@{user.username}" if user.username else user.first_name,
        reason=reason))


async def _do_reject(cb: CallbackQuery, session: AsyncSession, bot: Bot,
                     user: User, listing_id: int, reason: str) -> None:
    try:
        await moderation_service.reject(session, listing_id, user, reason)
    except moderation_service.AlreadyHandled as e:
        await cb.answer(texts.MOD_ALREADY.format(status=e.status), show_alert=True)
        return
    await cb.answer("Отклонено")
    try:
        await cb.message.edit_text(
            cb.message.text + "\n\n" + texts.MOD_REJECTED.format(
                admin=f"@{user.username}" if user.username else user.first_name,
                reason=reason))
    except Exception:
        pass


@router.callback_query(F.data.startswith("mod:ban:"))
async def ban_author(cb: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not user.is_admin:
        await cb.answer("Только для админов", show_alert=True)
        return
    listing_id = int(cb.data.split(":")[2])
    listing = await session.get(Listing, listing_id)
    if not listing:
        await cb.answer("Не найдено", show_alert=True)
        return
    author = await session.get(User, listing.author_id)
    author.is_banned = True
    listing.status = ST_REJECTED
    listing.reject_reason = "Автор заблокирован"
    session.add(ModerationLog(listing_id=listing.id, admin_id=user.id,
                              action="ban_author"))
    await session.commit()
    await cb.answer(f"Автор {author.first_name} забанен", show_alert=True)

"""Модерация в приватной группе админов.

Идемпотентность: SELECT ... FOR UPDATE — двойное нажатие двумя админами
не публикует объявление дважды.
"""
import html

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message,
)
from aiogram.utils.media_group import MediaGroupBuilder
from sqlalchemy import func, select
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


async def pending_count(session: AsyncSession) -> int:
    return await session.scalar(
        select(func.count()).select_from(Listing)
        .where(Listing.status == ST_PENDING)) or 0


async def notify_admins(bot: Bot, session: AsyncSession) -> None:
    """Короткий сигнал каждому админу в личку: заявка ждёт.

    Карточку целиком в личку не шлём — её показывает очередь, по одной.
    Иначе при десятке заявок в чате получилась бы каша из фотографий.
    """
    left = await pending_count(session)
    for tg_id in get_settings().admin_id_list:
        try:
            await bot.send_message(tg_id, f"{texts.MOD_NEW_PING}\nВ очереди: {left}")
        except Exception:
            pass          # админ не запускал бота — писать ему нельзя, это нормально


async def send_to_moderation(bot: Bot, session: AsyncSession, listing: Listing) -> None:
    s = get_settings()
    await notify_admins(bot, session)
    if not s.admin_chat_id:
        return            # группы нет — разбор идёт очередью в боте
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
    from_queue = bool(data.get("from_queue"))
    skipped = data.get("mod_skipped")
    card_msgs = data.get(QUEUE_MSGS) or []
    await state.clear()
    if from_queue:      # после очистки состояния карточку всё равно надо убрать
        await state.update_data(**{QUEUE_MSGS: card_msgs, "mod_skipped": skipped})
    reason = message.text.strip()[:500]
    try:
        await moderation_service.reject(session, data["listing_id"], user, reason)
    except moderation_service.AlreadyHandled as e:
        await message.answer(texts.MOD_ALREADY.format(status=e.status))
    else:
        await message.answer(texts.MOD_REJECTED.format(
            admin=f"@{user.username}" if user.username else user.first_name,
            reason=reason))
    if from_queue:                    # разбор очереди продолжается сам собой
        await show_next(bot, message.chat.id, session, state, skip_ids=skipped)


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


# ─────────────────── Очередь модерации прямо в боте ───────────────────
#
# Заявки разбираются по одной: показали карточку — нажали «Одобрить» или
# «Отклонить» — карточка исчезает, сразу приходит следующая. Ходить в группу
# и листать переписку не нужно.

QUEUE_MSGS = "mod_queue_msgs"      # id сообщений текущей карточки в состоянии


def queue_kb(listing_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"mq:ok:{listing_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"mq:no:{listing_id}")],
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"mq:skip:{listing_id}"),
         InlineKeyboardButton(text="🚫 Бан автора", callback_data=f"mq:ban:{listing_id}")],
    ])


async def _clear_card(bot: Bot, chat_id: int, state: FSMContext) -> None:
    """Убирает предыдущую карточку вместе с её фотографиями."""
    data = await state.get_data()
    for mid in data.get(QUEUE_MSGS) or []:
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass                      # старше двух суток — Telegram не даёт удалить
    await state.update_data(**{QUEUE_MSGS: []})


async def show_next(bot: Bot, chat_id: int, session: AsyncSession,
                    state: FSMContext, skip_ids: list[int] | None = None) -> None:
    """Показывает следующую заявку. Пусто — говорит об этом и выходит."""
    await _clear_card(bot, chat_id, state)

    query = select(Listing).where(Listing.status == ST_PENDING)
    if skip_ids:
        query = query.where(Listing.id.notin_(skip_ids))
    listing = await session.scalar(
        query.options(selectinload(Listing.photos))
        .order_by(Listing.created_at).limit(1))

    if listing is None:
        left = await pending_count(session)
        await bot.send_message(
            chat_id,
            texts.MOD_QUEUE_EMPTY if not left else texts.MOD_QUEUE_ALL_SKIPPED)
        return

    schema = get_schema(listing.category_slug)
    city = await session.get(City, listing.city_id) if listing.city_id else None
    district = await session.get(District, listing.district_id) if listing.district_id else None
    author = await session.get(User, listing.author_id)
    caption = build_caption(listing, schema,
                            city.name if city else None,
                            district.name if district else None)

    sent: list[int] = []
    if listing.photos:
        builder = MediaGroupBuilder()
        for i, p in enumerate(listing.photos[:10]):
            builder.add_photo(media=p.file_id,
                              caption=caption if i == 0 else None,
                              parse_mode="HTML" if i == 0 else None)
        try:
            msgs = await bot.send_media_group(chat_id=chat_id, media=builder.build())
            sent += [m.message_id for m in msgs]
        except Exception:
            pass                      # фото могли протухнуть — карточку всё равно покажем

    who = f"@{author.username}" if author and author.username else \
          html.escape(author.first_name if author else "?")
    flags = f"\n{html.escape(listing.flag_note)}" if listing.flag_note else ""
    total = await pending_count(session)
    card = await bot.send_message(
        chat_id,
        texts.MOD_QUEUE_CARD.format(
            id=listing.id, left=total,
            category=f"{schema.emoji} {schema.title}", author=who, flags=flags),
        reply_markup=queue_kb(listing.id))
    sent.append(card.message_id)
    await state.update_data(**{QUEUE_MSGS: sent})


@router.message(Command("queue"))
@router.message(F.text == texts.MENU_MOD)
async def open_queue(message: Message, session: AsyncSession, bot: Bot,
                     user: User, state: FSMContext) -> None:
    if not user.is_admin:
        return                        # для остальных такой команды словно нет
    await state.clear()               # выходим из мастера, если админ был в нём
    await show_next(bot, message.chat.id, session, state)


@router.callback_query(F.data.regexp(r"^mq:(ok|no|back|skip|ban):"))
async def queue_action(cb: CallbackQuery, session: AsyncSession, bot: Bot,
                       user: User, state: FSMContext) -> None:
    if not user.is_admin:
        await cb.answer("Только для админов", show_alert=True)
        return
    _, action, raw_id = cb.data.split(":")[:3]
    listing_id = int(raw_id)
    chat_id = cb.message.chat.id

    if action == "skip":
        data = await state.get_data()
        skipped = list(data.get("mod_skipped") or []) + [listing_id]
        await state.update_data(mod_skipped=skipped)
        await cb.answer("Пропущено")
        await show_next(bot, chat_id, session, state, skip_ids=skipped)
        return

    if action == "no":                # спрашиваем причину, карточку не трогаем
        rows = [[InlineKeyboardButton(text=label,
                                      callback_data=f"mq:r:{listing_id}:{code}")]
                for code, label in texts.REJECT_REASONS]
        rows.append([InlineKeyboardButton(text=texts.BTN_BACK,
                                          callback_data=f"mq:back:{listing_id}")])
        try:
            await cb.message.edit_reply_markup(
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        except Exception:
            pass
        await cb.answer()
        return

    if action == "back":
        try:
            await cb.message.edit_reply_markup(reply_markup=queue_kb(listing_id))
        except Exception:
            pass
        await cb.answer()
        return

    if action == "ban":
        listing = await session.get(Listing, listing_id)
        if not listing:
            await cb.answer("Не найдено", show_alert=True)
            return
        banned = await moderation_service.set_ban(session, listing.author_id,
                                                  user, True)
        if banned is None:
            await cb.answer("Себя забанить нельзя", show_alert=True)
            return
        try:
            await moderation_service.reject(session, listing_id, user,
                                            "Автор заблокирован")
        except moderation_service.AlreadyHandled:
            pass
        await cb.answer("Автор забанен", show_alert=True)
        await show_next(bot, chat_id, session, state,
                        skip_ids=(await state.get_data()).get("mod_skipped"))
        return

    if action == "ok":
        try:
            await moderation_service.approve(session, listing_id, user)
        except moderation_service.AlreadyHandled as e:
            await cb.answer(texts.MOD_ALREADY.format(status=e.status), show_alert=True)
            await show_next(bot, chat_id, session, state,
                            skip_ids=(await state.get_data()).get("mod_skipped"))
            return
        await cb.answer("✅ Одобрено")
        await show_next(bot, chat_id, session, state,
                        skip_ids=(await state.get_data()).get("mod_skipped"))
        return


@router.callback_query(F.data.startswith("mq:r:"))
async def queue_reject_reason(cb: CallbackQuery, session: AsyncSession, bot: Bot,
                              user: User, state: FSMContext) -> None:
    if not user.is_admin:
        await cb.answer("Только для админов", show_alert=True)
        return
    _, _, raw_id, code = cb.data.split(":")
    listing_id = int(raw_id)
    if code == "custom":
        await state.set_state(ModStates.reason)
        await state.update_data(listing_id=listing_id, from_queue=True)
        await cb.message.answer(texts.MOD_REASON_ASK)
        await cb.answer()
        return
    try:
        await moderation_service.reject(session, listing_id, user,
                                        REASON_LABELS.get(code, code))
    except moderation_service.AlreadyHandled as e:
        await cb.answer(texts.MOD_ALREADY.format(status=e.status), show_alert=True)
    else:
        await cb.answer("❌ Отклонено")
    await show_next(bot, cb.message.chat.id, session, state,
                    skip_ids=(await state.get_data()).get("mod_skipped"))


# ─────────────────────── Панель админа прямо в боте ───────────────────────

@router.message(Command("panel"))
@router.message(Command("stats"))
@router.message(F.text == texts.MENU_PANEL)
async def panel(message: Message, session: AsyncSession, user: User) -> None:
    """Всё хозяйство одним экраном: объявления, люди, сделки, справочники."""
    if not user.is_admin:
        return
    from datetime import datetime, timedelta

    from app.db.models import ST_ARCHIVED, ST_REJECTED, ST_SOLD, Report
    from app.services import deal_service, tac_service

    week = datetime.utcnow() - timedelta(days=7)
    day = datetime.utcnow() - timedelta(days=1)

    async def listings(*conds) -> int:
        return await session.scalar(
            select(func.count()).select_from(Listing).where(*conds)) or 0

    async def users(*conds) -> int:
        return await session.scalar(
            select(func.count()).select_from(User).where(*conds)) or 0

    deals = await deal_service.stats(session)
    tac = await tac_service.stats(session)

    top = (await session.execute(
        select(Listing.category_slug, func.count())
        .where(Listing.status == ST_APPROVED)
        .group_by(Listing.category_slug)
        .order_by(func.count().desc()).limit(5))).all()
    top_lines = "\n".join(
        f"   {(s.title if (s := get_schema(slug)) else slug)} — {n}"
        for slug, n in top) or "   пока пусто"

    await message.answer(texts.PANEL.format(
        pending=await listings(Listing.status == ST_PENDING),
        approved=await listings(Listing.status == ST_APPROVED),
        rejected=await listings(Listing.status == ST_REJECTED),
        sold=await listings(Listing.status == ST_SOLD),
        archived=await listings(Listing.status == ST_ARCHIVED),
        day=await listings(Listing.created_at > day),
        week=await listings(Listing.created_at > week),
        users=await users(),
        users_week=await users(User.created_at > week),
        banned=await users(User.is_banned),
        deals_started=deals["started"],
        deals_done=deals["done"],
        deals_week=deals["done_week"],
        deals_waiting=deals["waiting_seller"],
        conversion=deals["conversion"],
        tac_total=tac["total"],
        tac_manual=tac["imported"],
        reports=await session.scalar(
            select(func.count()).select_from(Report)
            .where(Report.status == "new")) or 0,
        top=top_lines))

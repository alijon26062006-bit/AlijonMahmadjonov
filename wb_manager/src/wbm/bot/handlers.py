"""Обработчики Telegram. Вся логика — в BotServices, здесь только диалог."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from html import escape
from typing import Any

from aiogram import BaseMiddleware, Bot, F, Router
from aiogram.enums import ChatType
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    TelegramObject,
)

from wbm.bot import texts
from wbm.bot.services import BotServices, looks_like_token
from wbm.costs import MAX_FILE_BYTES
from wbm.db.models import RunStatus, Shop, User

logger = logging.getLogger(__name__)

router = Router(name="private")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)

group_router = Router(name="groups")
group_router.message.filter(F.chat.type != ChatType.PRIVATE)


class UserMiddleware(BaseMiddleware):
    """Находит или создаёт пользователя по Telegram-аккаунту и кладёт его в data["user"]."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        services: BotServices = data["services"]
        from_user = getattr(event, "from_user", None)
        chat = getattr(event, "chat", None) or getattr(
            getattr(event, "message", None), "chat", None
        )
        if from_user is None or chat is None:
            return None
        data["user"] = await services.register(from_user.id, chat.id, from_user.full_name)
        return await handler(event, data)


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def _delete_quietly(message: Message) -> bool:
    try:
        await message.delete()
    except TelegramBadRequest:
        logger.warning("Не удалось удалить сообщение с токеном в чате %d", message.chat.id)
        return False
    return True


async def current_shop(services: BotServices, user: User, state: FSMContext) -> Shop | None:
    shops = await services.shops(user.id)
    if not shops:
        return None
    chosen = (await state.get_data()).get("shop_id")
    return next((s for s in shops if s.id == chosen), shops[0])


# ── начало и номер телефона ───────────────────────────────────────────────────


@router.message(CommandStart())
async def on_start(message: Message, user: User, services: BotServices) -> None:
    if not user.phone:
        await message.answer(texts.WELCOME, reply_markup=phone_keyboard())
        return
    shops = await services.shops(user.id)
    await message.answer(texts.HELP if shops else texts.token_instructions())


@router.message(F.contact)
async def on_contact(message: Message, user: User, services: BotServices) -> None:
    contact = message.contact
    if contact is None or message.from_user is None or contact.user_id != message.from_user.id:
        await message.answer(texts.ALIEN_CONTACT, reply_markup=phone_keyboard())
        return
    await services.save_phone(user.id, contact.phone_number)
    await message.answer(texts.PHONE_SAVED, reply_markup=ReplyKeyboardRemove())
    shops = await services.shops(user.id)
    await message.answer(texts.HELP if shops else texts.token_instructions())


# ── токен ─────────────────────────────────────────────────────────────────────


@router.message(F.text.func(looks_like_token))
async def on_token(message: Message, user: User, services: BotServices, state: FSMContext) -> None:
    text = message.text or ""
    deleted = await _delete_quietly(message)
    if not user.phone:
        await message.answer(texts.NEED_PHONE_FIRST, reply_markup=phone_keyboard())
        return
    status = await message.answer(
        texts.DELETED_NOTICE
        if deleted
        else "⚠️ Не получилось удалить сообщение с токеном — удалите его сами. Проверяю токен…"
    )
    result = await services.connect_token(user, text)
    if not result.ok:
        await status.edit_text(f"❌ {escape(result.message)}")
        return
    await state.update_data(shop_id=result.shop_id)
    await status.edit_text(
        texts.shop_connected(
            result.shop_name, result.available, result.warnings, updated=result.updated
        )
    )


@group_router.message(F.text.func(looks_like_token))
async def on_token_in_group(message: Message) -> None:
    await _delete_quietly(message)
    await message.answer(texts.GROUP_WARNING)


# ── справка ───────────────────────────────────────────────────────────────────


@router.message(Command("help"))
async def on_help(message: Message) -> None:
    await message.answer(texts.HELP)


@router.message(Command("token"))
async def on_token_help(message: Message) -> None:
    await message.answer(texts.token_instructions())


@router.message(Command("costs"))
async def on_costs_help(message: Message) -> None:
    await message.answer(texts.COSTS_HELP)


# ── себестоимость ─────────────────────────────────────────────────────────────


@router.message(F.document)
async def on_document(
    message: Message, user: User, services: BotServices, state: FSMContext, bot: Bot
) -> None:
    shop = await current_shop(services, user, state)
    if shop is None:
        await message.answer(texts.NO_SHOP)
        return
    document = message.document
    if document is None:
        return
    if document.file_size and document.file_size > MAX_FILE_BYTES:
        await message.answer("❌ Файл больше 5 МБ.")
        return
    buffer = await bot.download(document)
    if buffer is None:
        await message.answer("❌ Не удалось скачать файл, пришлите ещё раз.")
        return
    result = await services.save_costs(
        user.id, shop.id, document.file_name or "costs.csv", buffer.read()
    )
    if not result.ok:
        await message.answer(f"❌ {escape(result.message)}\n\n{texts.COSTS_HELP}")
        return
    reply = f"✅ Себестоимость для «{escape(shop.name)}» сохранена: {result.saved} артикулов."
    if result.errors:
        shown = "\n".join(f"• {escape(e)}" for e in result.errors[:10])
        more = f"\n… и ещё {len(result.errors) - 10}" if len(result.errors) > 10 else ""
        reply += f"\n\nПропущены строки:\n{shown}{more}"
    await message.answer(reply)


# ── анализ и история ──────────────────────────────────────────────────────────


@router.message(Command("analyze"))
async def on_analyze(
    message: Message, user: User, services: BotServices, state: FSMContext
) -> None:
    if not user.phone:
        await message.answer(texts.WELCOME, reply_markup=phone_keyboard())
        return
    shop = await current_shop(services, user, state)
    if shop is None:
        await message.answer(texts.NO_SHOP)
        return
    run, is_new = await services.start_analysis(user.id, shop.id, message.chat.id)
    if run is None:
        await message.answer(texts.NO_SHOP)
        return
    if not is_new:
        await message.answer(
            "⏳ Анализ этого магазина уже идёт — пришлю результат, как будет готов."
        )
        return
    progress = await message.answer(texts.progress_text(shop.name, 0, "В очереди"))
    await services.remember_progress_message(run.id, progress.message_id)


@router.message(Command("history"))
async def on_history(
    message: Message, user: User, services: BotServices, state: FSMContext
) -> None:
    shop = await current_shop(services, user, state)
    if shop is None:
        await message.answer(texts.NO_SHOP)
        return
    runs = await services.history(user.id, shop.id)
    if not runs:
        await message.answer("Анализов пока не было. Запустите: /analyze")
        return
    status_titles = {
        RunStatus.QUEUED: "в очереди",
        RunStatus.RUNNING: "идёт",
        RunStatus.DONE: "готов",
        RunStatus.FAILED: "ошибка",
    }
    buttons = [
        [
            InlineKeyboardButton(
                text=f"📎 {run.created_at:%d.%m.%Y %H:%M} — {status_titles.get(RunStatus(run.status), run.status)}",
                callback_data=f"pdf:{run.id}",
            )
        ]
        for run in runs
    ]
    await message.answer(
        f"История анализов «{escape(shop.name)}» — нажмите, чтобы получить PDF:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(F.data.startswith("pdf:"))
async def on_pdf(callback: CallbackQuery, user: User, services: BotServices) -> None:
    run_id = _id_from(callback.data)
    result = await services.report_pdf(user.id, run_id) if run_id else None
    if result is None or not isinstance(callback.message, Message):
        await callback.answer("Отчёт ещё не готов или недоступен", show_alert=True)
        return
    pdf, filename = result
    await callback.answer()
    await callback.message.answer_document(BufferedInputFile(pdf, filename=filename))


# ── магазины ──────────────────────────────────────────────────────────────────


@router.message(Command("shops"))
async def on_shops(message: Message, user: User, services: BotServices, state: FSMContext) -> None:
    shops = await services.shops(user.id)
    if not shops:
        await message.answer(texts.NO_SHOP)
        return
    current = await current_shop(services, user, state)
    rows = [
        [
            InlineKeyboardButton(
                text=("✅ " if current and shop.id == current.id else "") + shop.name[:40],
                callback_data=f"shop:{shop.id}",
            ),
            InlineKeyboardButton(text="🗑", callback_data=f"delshop:{shop.id}"),
        ]
        for shop in shops
    ]
    await message.answer(
        "Ваши магазины. Нажмите на название, чтобы выбрать, 🗑 — чтобы удалить.\n"
        "Новый магазин — пришлите его токен.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith("shop:"))
async def on_shop_select(
    callback: CallbackQuery, user: User, services: BotServices, state: FSMContext
) -> None:
    shop_id = _id_from(callback.data)
    shop = next((s for s in await services.shops(user.id) if s.id == shop_id), None)
    if shop is None:
        await callback.answer("Магазин не найден", show_alert=True)
        return
    await state.update_data(shop_id=shop.id)
    await callback.answer(f"Выбран магазин «{shop.name}»")


@router.callback_query(F.data.startswith("delshop:"))
async def on_shop_delete_ask(callback: CallbackQuery) -> None:
    shop_id = _id_from(callback.data)
    if not shop_id or not isinstance(callback.message, Message):
        await callback.answer()
        return
    await callback.answer()
    await callback.message.answer(
        "Удалить магазин вместе с токеном, себестоимостью и историей анализов?",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Да, удалить", callback_data=f"delshop_yes:{shop_id}"
                    ),
                    InlineKeyboardButton(text="Нет", callback_data="cancel"),
                ]
            ]
        ),
    )


@router.callback_query(F.data.startswith("delshop_yes:"))
async def on_shop_delete(
    callback: CallbackQuery, user: User, services: BotServices, state: FSMContext
) -> None:
    shop_id = _id_from(callback.data)
    deleted = await services.delete_shop(user.id, shop_id) if shop_id else False
    if deleted and (await state.get_data()).get("shop_id") == shop_id:
        await state.update_data(shop_id=None)
    await callback.answer("Магазин удалён" if deleted else "Магазин не найден", show_alert=True)
    if isinstance(callback.message, Message):
        await callback.message.delete()


@router.callback_query(F.data == "cancel")
async def on_cancel(callback: CallbackQuery) -> None:
    await callback.answer("Отменено")
    if isinstance(callback.message, Message):
        await callback.message.delete()


@router.message()
async def on_other(message: Message) -> None:
    await message.answer(texts.HELP)


def _id_from(data: str | None) -> int | None:
    try:
        return int((data or "").split(":", 1)[1])
    except (IndexError, ValueError):
        return None

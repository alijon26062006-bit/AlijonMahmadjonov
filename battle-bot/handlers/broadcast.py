"""Мастер рассылки: медиа → текст → кнопки → превью → отправка."""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Config
from handlers.panel import is_admin
from services import broadcast, keyboards, panel_ui, ui, validation
from services.validation import InputError
from storage.repo import Repo
from storage.settings import Settings

log = logging.getLogger(__name__)
router = Router(name="broadcast")


class Cast(StatesGroup):
    media = State()
    text = State()
    button_label = State()
    button_url = State()


def _draft(data: dict) -> broadcast.Draft:
    return broadcast.Draft(**data.get("draft", {}))


async def _save(state: FSMContext, draft: broadcast.Draft) -> None:
    await state.update_data(
        draft={
            "media_type": draft.media_type,
            "file_id": draft.file_id,
            "text": draft.text,
            "buttons": [list(pair) for pair in draft.buttons],
        }
    )


def _kb(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=list(rows))


def _btn(text: str, action: str, style: str | None = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=f"cast:{action}", style=style)


STEP_MEDIA = (
    "📨 <b>Рассылка · шаг 1 из 3</b>\n"
    f"{panel_ui.RULE}\n\n"
    "Пришлите <b>медиа</b> для рассылки: фото, видео, гифку, файл, аудио, "
    "голосовое, кружок или стикер.\n\n"
    "<i>Можно пропустить и отправить только текст.</i>"
)

STEP_TEXT = (
    "📨 <b>Рассылка · шаг 2 из 3</b>\n"
    f"{panel_ui.RULE}\n\n"
    "Пришлите <b>текст</b> сообщения.\n\n"
    "<i>Можно пропустить, если хватит медиа.</i>"
)


# ------------------------------------------------------------------- запуск

@router.callback_query(F.data == "p:broadcast")
@router.message(Command("broadcast"))
async def start_cast(event: Message | CallbackQuery, config: Config, state: FSMContext) -> None:
    user_id = event.from_user.id
    if not is_admin(user_id, config):
        return

    message = event.message if isinstance(event, CallbackQuery) else event
    await state.clear()
    await state.set_state(Cast.media)
    await _save(state, broadcast.Draft())
    await message.answer(STEP_MEDIA, reply_markup=_kb([_btn("Пропустить →", "skip:media")],
                                                      [_btn("Отмена", "cancel")]))
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(
    Cast.media,
    F.text.startswith("/") | F.text.in_(keyboards.menu_labels()),
)
@router.message(
    Cast.text,
    F.text.startswith("/") | F.text.in_(keyboards.menu_labels()),
)
@router.message(
    Cast.button_label,
    F.text.startswith("/") | F.text.in_(keyboards.menu_labels()),
)
@router.message(
    Cast.button_url,
    F.text.startswith("/") | F.text.in_(keyboards.menu_labels()),
)
async def leave_wizard(message: Message, state: FSMContext) -> None:
    """Из мастера всегда можно выйти командой или кнопкой меню."""
    await state.clear()
    raise SkipHandler()


# --------------------------------------------------------------- шаг 1: медиа

@router.message(Cast.media)
async def got_media(message: Message, state: FSMContext) -> None:
    if await ui.left_the_step(state):
        raise SkipHandler()  # состояние сняли выше — это сообщение не наше

    found = broadcast.extract_media(message)
    if found is None:
        if message.text:
            # прислали сразу текст — засчитываем его и идём к кнопкам
            draft = _draft(await state.get_data())
            draft.text = message.text
            await _save(state, draft)
            await _ask_buttons(message, state, draft)
            return
        await message.answer(
            "⚠️ Это не медиа. Пришлите фото, видео, гифку, файл, аудио, "
            "голосовое, кружок или стикер — либо нажмите «Пропустить»."
        )
        return

    draft = _draft(await state.get_data())
    draft.media_type, draft.file_id = found
    await _save(state, draft)

    await state.set_state(Cast.text)
    await message.answer(
        f"✅ Принято: <b>{broadcast.HUMAN.get(found[0], found[0])}</b>\n\n{STEP_TEXT}",
        reply_markup=_kb([_btn("Пропустить →", "skip:text")], [_btn("Отмена", "cancel")]),
    )


@router.callback_query(F.data == "cast:skip:media")
async def skip_media(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await state.set_state(Cast.text)
    await ui.edit_or_send(
        callback, STEP_TEXT, reply_markup=_kb([_btn("Отмена", "cancel")])
    )
    await callback.answer()


# ---------------------------------------------------------------- шаг 2: текст

@router.message(Cast.text)
async def got_text(message: Message, state: FSMContext) -> None:
    if await ui.left_the_step(state):
        raise SkipHandler()  # состояние сняли выше — это сообщение не наше

    draft = _draft(await state.get_data())
    try:
        draft.text = validation.as_text(message.html_text or message.text or "")
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return

    await _save(state, draft)
    await _ask_buttons(message, state, draft)


@router.callback_query(F.data == "cast:skip:text")
async def skip_text(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    draft = _draft(await state.get_data())
    if draft.is_empty:
        await callback.answer("Рассылка пустая — пришлите медиа или текст.", show_alert=True)
        return
    await _ask_buttons(callback.message, state, draft)
    await callback.answer()


# --------------------------------------------------------------- шаг 3: кнопки

async def _ask_buttons(message: Message, state: FSMContext, draft: broadcast.Draft) -> None:
    await state.set_state(None)
    listing = "\n".join(f"• <b>{label}</b> → {url}" for label, url in draft.buttons)
    await message.answer(
        "📨 <b>Рассылка · шаг 3 из 3</b>\n"
        f"{panel_ui.RULE}\n\n"
        f"Содержимое: <b>{draft.describe()}</b>\n"
        + (f"\n<b>Кнопки</b>\n{listing}\n" if draft.buttons else "")
        + "\nДобавить кнопку со ссылкой?",
        reply_markup=_kb(
            [_btn("➕ Добавить кнопку", "button:add", keyboards.BLUE)],
            [_btn("👁 Показать превью", "preview", keyboards.GREEN)],
            [_btn("Отмена", "cancel")],
        ),
    )


@router.callback_query(F.data == "cast:button:add")
async def ask_label(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await state.set_state(Cast.button_label)
    await callback.message.answer(
        "✏️ Пришлите <b>название кнопки</b>.\n<i>Например: Участвовать</i>",
        reply_markup=_kb([_btn("Отмена", "cancel")]),
    )
    await callback.answer()


@router.message(Cast.button_label)
async def got_label(message: Message, state: FSMContext) -> None:
    if await ui.left_the_step(state):
        raise SkipHandler()  # состояние сняли выше — это сообщение не наше

    try:
        label = validation.as_text(message.text or "", limit=64)
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return

    await state.update_data(pending_label=label)
    await state.set_state(Cast.button_url)
    await message.answer(
        f"🔗 Теперь <b>ссылку</b> для кнопки «{label}».\n"
        "<i>Например: https://t.me/realed или @realed</i>",
        reply_markup=_kb([_btn("Отмена", "cancel")]),
    )


@router.message(Cast.button_url)
async def got_url(message: Message, state: FSMContext) -> None:
    if await ui.left_the_step(state):
        raise SkipHandler()  # состояние сняли выше — это сообщение не наше

    try:
        url = validation.as_url(message.text or "")
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return

    data = await state.get_data()
    draft = _draft(data)
    draft.buttons.append((data["pending_label"], url))
    await _save(state, draft)
    await _ask_buttons(message, state, draft)


# ------------------------------------------------------------------- превью

@router.callback_query(F.data == "cast:preview")
async def preview(
    callback: CallbackQuery,
    bot: Bot,
    repo: Repo,
    config: Config,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not is_admin(callback.from_user.id, config):
        return

    draft = _draft(await state.get_data())
    if draft.is_empty:
        await callback.answer("Рассылка пустая.", show_alert=True)
        return

    await callback.answer("Собираю превью…")
    await callback.message.answer("👁 <b>Так это увидят люди:</b>")
    await broadcast.deliver(bot, draft, callback.from_user.id)

    recipients = len(repo.all_user_ids())
    rows = [[_btn(f"👥 Всем в личку ({recipients})", "send:users", keyboards.GREEN)]]

    main_channel = settings.get("main_channel_id")
    if main_channel:
        rows.append([_btn("📣 В главный канал", "send:main", keyboards.BLUE)])
    rows.append([_btn("⚔️ В канал батлов", "send:battles", keyboards.BLUE)])
    rows.append([_btn("➕ Ещё кнопку", "button:add")])
    rows.append([_btn("Отмена", "cancel")])

    await callback.message.answer(
        f"{panel_ui.RULE}\n"
        f"Содержимое: <b>{draft.describe()}</b>\n\n"
        "<b>Куда отправить?</b>",
        reply_markup=_kb(*rows),
    )


# ------------------------------------------------------------------ отправка

@router.callback_query(F.data.startswith("cast:send:"))
async def send_somewhere(
    callback: CallbackQuery,
    bot: Bot,
    repo: Repo,
    config: Config,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not is_admin(callback.from_user.id, config):
        return

    draft = _draft(await state.get_data())
    if draft.is_empty:
        await callback.answer("Рассылка пустая.", show_alert=True)
        return

    target = callback.data.split(":")[-1]
    if target == "users":
        await _send_to_users(callback, bot, repo, config, state, draft)
        return

    channel_id = (
        settings.get("main_channel_id") if target == "main" else config.channel_id
    )
    if not channel_id:
        await callback.answer("Главный канал не задан.", show_alert=True)
        return

    await state.clear()
    await callback.answer("Публикую…")
    try:
        posted = await broadcast.deliver(bot, draft, channel_id)
    except TelegramAPIError as error:
        await callback.message.answer(
            f"⚠️ <b>Не опубликовалось</b>\n\n{error}\n\n"
            "<i>Проверьте, что бот — администратор этого канала "
            "с правом публикации.</i>"
        )
        return

    # запоминаем пост, чтобы панель могла удалить его вместе с остальными
    if posted is not None:
        repo.record_post(channel_id, posted.message_id, None, kind="broadcast")

    where = "главный канал" if target == "main" else "канал батлов"
    await callback.message.answer(f"✅ Опубликовано в <b>{where}</b>.")


async def _send_to_users(
    callback: CallbackQuery,
    bot: Bot,
    repo: Repo,
    config: Config,
    state: FSMContext,
    draft: broadcast.Draft,
) -> None:
    await state.clear()
    await callback.answer("Начинаю рассылку")
    status = await callback.message.answer("📤 Рассылка началась…")
    recipients = repo.all_user_ids()

    async def progress(done: int, total: int, report: broadcast.Report) -> None:
        try:
            await status.edit_text(
                f"📤 <b>Рассылка идёт</b>\n{panel_ui.RULE}\n\n"
                f"Обработано: <b>{done}</b> из <b>{total}</b>\n"
                f"Доставлено: <b>{report.sent}</b>"
            )
        except Exception:  # noqa: BLE001 - прогресс не должен ронять рассылку
            pass

    report = await broadcast.run(
        bot, draft, recipients, delay=config.dm_delay, on_progress=progress, repo=repo
    )
    log.info("Рассылка: доставлено %s, заблокировали %s, ошибок %s",
             report.sent, report.blocked, report.failed)

    await status.edit_text(
        f"✅ <b>Рассылка завершена</b>\n{panel_ui.RULE}\n\n"
        f"📬 Доставлено: <b>{report.sent}</b>\n"
        f"🚫 Заблокировали бота: <b>{report.blocked}</b>\n"
        f"⚠️ Не дошло: <b>{report.failed}</b>\n"
        f"Всего: <b>{report.total}</b>"
    )


@router.callback_query(F.data == "cast:cancel")
async def cancel(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await state.clear()
    await ui.edit_or_send(callback, "Рассылка отменена.")
    await callback.answer()

"""«Мой канал»: участник подключает свой канал, бот публикует туда его пары."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Config
from services import keyboards, member_channel, texts, ui
from services.keyboards import BLUE, GREEN, RED
from storage.repo import Repo
from storage.settings import Settings

log = logging.getLogger(__name__)
router = Router(name="mychannel")


class MyChannel(StatesGroup):
    waiting_forward = State()


def screen(channel, config: Config) -> InlineKeyboardMarkup:
    if channel is None:
        rows = [[InlineKeyboardButton(
            text="📡 Подключить канал", callback_data="mych:link", style=BLUE
        )]]
    else:
        rows = [
            [InlineKeyboardButton(
                text="🔄 Проверить", callback_data="mych:check", style=GREEN
            )],
            [InlineKeyboardButton(text="📢 Опубликовать мою пару", callback_data="mych:post")],
            [InlineKeyboardButton(
                text="🗑 Отключить канал", callback_data="mych:unlink", style=RED
            )],
        ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show(message: Message, repo: Repo, config: Config, settings: Settings, user) -> None:
    if not member_channel.enabled(settings):
        await message.answer(texts.MY_CHANNEL_OFF)
        return

    repo.upsert_user(user.id, user.username, user.first_name)
    channel = repo.member_channel(user.id)
    await message.answer(
        texts.my_channel_screen(channel, config.bot_username),
        reply_markup=screen(channel, config),
        disable_web_page_preview=True,
    )


@router.message(F.text.in_(keyboards.variants(keyboards.BTN_CHANNEL)))
@router.message(Command("mychannel"))
async def open_screen(
    message: Message, repo: Repo, config: Config, settings: Settings, state: FSMContext
) -> None:
    await state.clear()
    await show(message, repo, config, settings, message.from_user)


@router.callback_query(F.data == "mych:open")
async def open_from_button(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings, state: FSMContext
) -> None:
    await state.clear()
    await show(callback.message, repo, config, settings, callback.from_user)
    await callback.answer()


# ----------------------------------------------------------------- привязка

@router.callback_query(F.data == "mych:link")
async def ask_forward(callback: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    if not member_channel.enabled(settings):
        await callback.answer(texts.MY_CHANNEL_OFF, show_alert=True)
        return
    await state.set_state(MyChannel.waiting_forward)
    await callback.message.answer(texts.MY_CHANNEL_FORWARD)
    await callback.answer()


@router.message(
    MyChannel.waiting_forward,
    F.text.startswith("/") | F.text.in_(keyboards.menu_labels()),
)
async def command_escapes_input(message: Message, state: FSMContext) -> None:
    """Из ожидания пересылки всегда можно уйти командой или кнопкой меню."""
    await state.clear()
    raise SkipHandler()


@router.message(MyChannel.waiting_forward)
async def take_forward(
    message: Message, repo: Repo, config: Config, settings: Settings, state: FSMContext
) -> None:
    """Пересланный пост говорит, какой канал привязывать."""
    if await ui.left_the_step(state):
        raise SkipHandler()  # состояние сняли выше — это сообщение не наше

    chat_id, title, username, problem = member_channel.from_forward(message)
    if problem:
        await message.answer(problem)
        return

    problem = await member_channel.can_publish(message.bot, chat_id, message.from_user.id)
    if problem:
        await message.answer(problem)
        return

    if not repo.link_channel(message.from_user.id, chat_id, title, username):
        await message.answer(texts.MY_CHANNEL_TAKEN)
        return

    await state.clear()
    log.info("Участник %s подключил канал %s", message.from_user.id, chat_id)
    await message.answer(texts.my_channel_linked(title))
    await show(message, repo, config, settings, message.from_user)


@router.callback_query(F.data == "mych:check")
async def recheck(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    """Права могли вернуть — проверяем и снова включаем публикацию."""
    channel = repo.member_channel(callback.from_user.id)
    if channel is None:
        await callback.answer("Канал не подключён.", show_alert=True)
        return

    problem = await member_channel.can_publish(
        callback.bot, int(channel["chat_id"]), callback.from_user.id
    )
    if problem:
        repo.disable_channel(callback.from_user.id)
        await callback.message.answer(problem)
    else:
        repo.link_channel(
            callback.from_user.id, int(channel["chat_id"]),
            channel["title"], channel["username"],
        )
        await callback.answer("Всё работает ✅")

    await show(callback.message, repo, config, settings, callback.from_user)


@router.callback_query(F.data == "mych:unlink")
async def unlink(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    repo.unlink_channel(callback.from_user.id)
    await callback.answer("Отключено")
    await callback.message.answer(texts.MY_CHANNEL_UNLINKED)
    await show(callback.message, repo, config, settings, callback.from_user)


# --------------------------------------------------------- ручная публикация

@router.callback_query(F.data.startswith("mych:post"))
async def publish_now(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings,
    emoji_skip: set[int] | None = None,
) -> None:
    """Опубликовать свою пару прямо сейчас — если автопубликация не прошла."""
    if not member_channel.enabled(settings):
        await callback.answer(texts.MY_CHANNEL_OFF, show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) > 2 and parts[2].isdigit():
        match_id = int(parts[2])
    else:
        match = repo.active_match_for(callback.from_user.id)
        if match is None:
            await callback.answer(texts.MY_CHANNEL_NO_MATCH, show_alert=True)
            return
        match_id = int(match["id"])

    if repo.member_channel(callback.from_user.id) is None:
        await callback.answer("Сначала подключите канал.", show_alert=True)
        await show(callback.message, repo, config, settings, callback.from_user)
        return

    sent = await member_channel.publish_match(
        callback.bot, repo, config, settings, callback.from_user.id, match_id, emoji_skip
    )
    await callback.answer("Опубликовано ✅" if sent else "Не получилось — проверьте права.",
                          show_alert=not sent)

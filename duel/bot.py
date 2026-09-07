"""Телеграм-бот дуэли: кнопка запуска Mini App, профиль, таблица лидеров."""

from __future__ import annotations

import logging
import sqlite3

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    MenuButtonWebApp,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from . import rating as rating_mod
from . import storage
from .config import DuelConfig
from .i18n import LANG_NAMES, LANGS, normalize, t, title as title_of

log = logging.getLogger("duel.bot")
router = Router(name="duel")


def player_lang(conn: sqlite3.Connection, message: Message) -> str:
    """Язык игрока: сохранённый выбор, иначе язык его Телеграма."""

    row = storage.get_player(conn, message.from_user.id) if message.from_user else None
    if row is not None:
        return normalize(row["lang"])
    return normalize(message.from_user.language_code if message.from_user else None)


def play_keyboard(lang: str, webapp_url: str) -> InlineKeyboardMarkup:
    """Кнопки под сообщением бота. Игру открывает верхняя.

    Кнопка обязана быть именно здесь, а не на клавиатуре под полем ввода:
    с той Telegram не передаёт в приложение данные о том, кто его открыл
    (initData приходит пустой), и игра не может узнать игрока.
    """

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("bot.play", lang), web_app=WebAppInfo(url=webapp_url))],
            [
                InlineKeyboardButton(text=t("bot.top", lang), callback_data="duel:top"),
                InlineKeyboardButton(text=t("bot.me", lang), callback_data="duel:me"),
            ],
            [
                InlineKeyboardButton(text=t("bot.rules", lang), callback_data="duel:rules"),
                InlineKeyboardButton(text=t("bot.lang", lang), callback_data="duel:langs"),
            ],
        ]
    )


def main_keyboard(lang: str) -> ReplyKeyboardMarkup:
    """Клавиатура под полем ввода — только текстовые кнопки.

    Игру отсюда не открываем: см. play_keyboard.
    """

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("bot.top", lang)), KeyboardButton(text=t("bot.me", lang))],
            [KeyboardButton(text=t("bot.rules", lang)), KeyboardButton(text=t("bot.lang", lang))],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=LANG_NAMES[code], callback_data=f"duel:lang:{code}")]
            for code in LANGS
        ]
    )


def ensure_player(conn: sqlite3.Connection, message: Message) -> str:
    """Заводит игрока при первом обращении к боту и возвращает его язык."""

    user = message.from_user
    if user is None:
        return "ru"
    lang = player_lang(conn, message)
    storage.touch_player(
        conn,
        user.id,
        (f"{user.first_name or ''} {user.last_name or ''}".strip() or f"Игрок {user.id}"),
        username=user.username or "",
        lang=lang,
    )
    return lang


@router.message(CommandStart(deep_link=True))
async def start_deeplink(
    message: Message,
    command: CommandObject,
    conn: sqlite3.Connection,
    config: DuelConfig,
    hub=None,
) -> None:
    """Пришёл по ссылке-приглашению: t.me/бот?start=КОД.

    Так Telegram открывает переписку, а не игру. Значит, первое же сообщение
    должно быть кнопкой прямо в бой — а не приветствием, которое надо читать.
    """

    lang = ensure_player(conn, message)
    code = (command.args or "").strip().upper()
    if not code:
        await start(message, conn, config)
        return

    url = f"{config.webapp_url}?tgWebAppStartParam={code}"
    room = hub.queue.find_room(code) if hub is not None else None
    text = (
        t("bot.challenge", lang, name=room.host.name, link="").strip()
        if room is not None
        else t("bot.press", lang)
    )
    await message.answer(text, reply_markup=play_keyboard(lang, url))
    await message.answer(t("bot.start", lang), reply_markup=main_keyboard(lang))


@router.message(CommandStart())
@router.message(Command("play"))
async def start(message: Message, conn: sqlite3.Connection, config: DuelConfig) -> None:
    if message.chat.type != "private":
        lang = normalize(message.from_user.language_code if message.from_user else None)
        await message.answer(t("bot.only_private", lang))
        return
    lang = ensure_player(conn, message)
    await message.answer(t("bot.start", lang), reply_markup=main_keyboard(lang))
    await message.answer(
        t("bot.press", lang), reply_markup=play_keyboard(lang, config.webapp_url)
    )


@router.message(Command("duel"))
async def duel_command(
    message: Message,
    conn: sqlite3.Connection,
    config: DuelConfig,
    hub=None,
) -> None:
    """Открытый вызов в групповом чате.

    Кнопка тут обычная, со ссылкой: web_app-кнопки Telegram разрешает только
    в личной переписке. Ссылка ведёт в ту же комнату, поэтому дерётся тот,
    кто первым её откроет.
    """

    lang = ensure_player(conn, message)
    if message.chat.type == "private":
        await message.answer(
            t("bot.press", lang), reply_markup=play_keyboard(lang, config.webapp_url)
        )
        return
    if hub is None or message.from_user is None:
        return

    room = hub.open_group_room(
        message.from_user.id,
        message.from_user.first_name or f"Игрок {message.from_user.id}",
        message.chat.id,
    )
    link = hub.invite_link(room.code)
    if not link:
        await message.answer(t("bot.duel.no_link", lang))
        return

    await message.answer(
        t(
            "bot.duel.call",
            lang,
            name=message.from_user.first_name or "",
            duration=t("bot.duel.minute", lang),
        ),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=t("bot.duel.accept", lang), url=link)]
            ]
        ),
    )


@router.message(Command("rules"))
async def rules_cmd(message: Message, conn: sqlite3.Connection) -> None:
    await message.answer(t("bot.rules.text", ensure_player(conn, message)))


@router.message(Command("top"))
async def top_cmd(message: Message, conn: sqlite3.Connection) -> None:
    await message.answer(top_text(conn, ensure_player(conn, message)))


@router.message(Command("me"))
async def me_cmd(message: Message, conn: sqlite3.Connection) -> None:
    await message.answer(profile_text(conn, message, ensure_player(conn, message)))


@router.message(Command("lang"))
async def lang_cmd(message: Message, conn: sqlite3.Connection) -> None:
    lang = ensure_player(conn, message)
    await message.answer(t("bot.lang.choose", lang), reply_markup=lang_keyboard())


@router.callback_query(F.data.startswith("duel:lang:"))
async def lang_pick(
    call: CallbackQuery, conn: sqlite3.Connection, config: DuelConfig
) -> None:
    code = normalize(call.data.rsplit(":", 1)[-1])
    storage.set_lang(conn, call.from_user.id, code)
    await call.answer()
    if isinstance(call.message, Message):
        await call.message.answer(t("bot.lang.done", code), reply_markup=main_keyboard(code))
        await call.message.answer(
            t("bot.press", code), reply_markup=play_keyboard(code, config.webapp_url)
        )


@router.callback_query(F.data == "duel:top")
async def top_button_inline(call: CallbackQuery, conn: sqlite3.Connection) -> None:
    await call.answer()
    if isinstance(call.message, Message):
        await call.message.answer(top_text(conn, _caller_lang(conn, call)))


@router.callback_query(F.data == "duel:rules")
async def rules_button_inline(call: CallbackQuery, conn: sqlite3.Connection) -> None:
    await call.answer()
    if isinstance(call.message, Message):
        await call.message.answer(t("bot.rules.text", _caller_lang(conn, call)))


@router.callback_query(F.data == "duel:me")
async def me_button_inline(call: CallbackQuery, conn: sqlite3.Connection) -> None:
    await call.answer()
    if isinstance(call.message, Message):
        lang = _caller_lang(conn, call)
        await call.message.answer(_profile_of(conn, call.from_user.id, lang))


@router.callback_query(F.data == "duel:langs")
async def lang_button_inline(call: CallbackQuery, conn: sqlite3.Connection) -> None:
    await call.answer()
    if isinstance(call.message, Message):
        await call.message.answer(
            t("bot.lang.choose", _caller_lang(conn, call)), reply_markup=lang_keyboard()
        )


def _caller_lang(conn: sqlite3.Connection, call: CallbackQuery) -> str:
    row = storage.get_player(conn, call.from_user.id)
    if row is not None:
        return normalize(row["lang"])
    return normalize(call.from_user.language_code)


# Кнопки нижней клавиатуры приходят обычным текстом — ловим их на обоих языках.
def _button_texts(key: str) -> set[str]:
    return {t(key, lang) for lang in LANGS}


@router.message(F.text.in_(_button_texts("bot.top")))
async def top_button(message: Message, conn: sqlite3.Connection) -> None:
    await message.answer(top_text(conn, ensure_player(conn, message)))


@router.message(F.text.in_(_button_texts("bot.me")))
async def me_button(message: Message, conn: sqlite3.Connection) -> None:
    await message.answer(profile_text(conn, message, ensure_player(conn, message)))


@router.message(F.text.in_(_button_texts("bot.rules")))
async def rules_button(message: Message, conn: sqlite3.Connection) -> None:
    await message.answer(t("bot.rules.text", ensure_player(conn, message)))


@router.message(F.text.in_(_button_texts("bot.lang")))
async def lang_button(message: Message, conn: sqlite3.Connection) -> None:
    lang = ensure_player(conn, message)
    await message.answer(t("bot.lang.choose", lang), reply_markup=lang_keyboard())


def top_text(conn: sqlite3.Connection, lang: str, limit: int = 20) -> str:
    rows = storage.top(conn, limit)
    if not rows:
        return t("bot.top.empty", lang)
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = [t("bot.top.header", lang)]
    for place, row in enumerate(rows, start=1):
        mark = medals.get(place, f"{place}.")
        lines.append(f"{mark} {row['name']} — {row['rating']} ({row['wins']}/{row['games']})")
    return "\n".join(lines)


def profile_text(conn: sqlite3.Connection, message: Message, lang: str) -> str:
    return _profile_of(conn, message.from_user.id, lang)


def _profile_of(conn: sqlite3.Connection, user_id: int, lang: str) -> str:
    row = storage.get_player(conn, user_id)
    if row is None:
        return t("bot.profile.empty", lang, name="—")
    if row["games"] == 0:
        return t("bot.profile.empty", lang, name=row["name"])
    return t(
        "bot.profile",
        lang,
        name=row["name"],
        rating=row["rating"],
        title=title_of(rating_mod.title(row["rating"]), lang),
        place=storage.place_of(conn, row["id"]),
        games=row["games"],
        wins=row["wins"],
        losses=row["losses"],
        draws=row["draws"],
        correct=row["correct"],
        streak=row["best_streak"],
    )


async def setup_bot_ui(bot, config: DuelConfig) -> None:
    """Кнопка «меню» рядом с полем ввода и список команд."""

    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text=t("bot.menu.play"), web_app=WebAppInfo(url=config.webapp_url)
        )
    )
    await bot.set_my_commands(
        [
            BotCommand(command="play", description=t("bot.menu.play")),
            BotCommand(command="duel", description="Вызов в чате"),
            BotCommand(command="top", description="Таблица лидеров"),
            BotCommand(command="me", description="Мой профиль"),
            BotCommand(command="rules", description="Правила"),
            BotCommand(command="lang", description="Язык / Забон"),
        ]
    )

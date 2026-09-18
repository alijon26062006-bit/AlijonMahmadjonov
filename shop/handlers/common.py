"""Кӯмакчиҳои муштарак барои ҳамаи роутерҳо."""

from __future__ import annotations

import logging
import re

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from .. import catalog, keyboards, texts
from ..config import Config
from ..db import Database, User

log = logging.getLogger(__name__)

USERNAME_RE = re.compile(r"^@?[A-Za-z][A-Za-z0-9_]{4,31}$")
PLAYER_ID_RE = re.compile(r"^\d{6,12}$")


def clean_username(raw: str) -> str | None:
    """«@Ali_2006», «t.me/Ali_2006», «https://t.me/Ali_2006» → «@Ali_2006»."""
    value = (raw or "").strip()
    for prefix in ("https://", "http://"):
        if value.lower().startswith(prefix):
            value = value[len(prefix):]
    for prefix in ("t.me/", "telegram.me/", "telegram.dog/"):
        if value.lower().startswith(prefix):
            value = value[len(prefix):]
    value = value.split("?")[0].strip().lstrip("@")
    if not USERNAME_RE.match(value):
        return None
    return f"@{value}"


def clean_player_id(raw: str) -> str | None:
    value = re.sub(r"[\s\-]+", "", (raw or "").strip())
    return value if PLAYER_ID_RE.match(value) else None


def clean_player_server(raw: str) -> tuple[str, str] | None:
    """«123456789 1234» ё «123456789(1234)» → (ID, сервер)."""
    value = re.sub(r"[()\[\]]", " ", (raw or "").strip())
    parts = [p for p in re.split(r"[\s,;]+", value) if p]
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        return None
    player, server = parts
    if not 5 <= len(player) <= 12 or not 1 <= len(server) <= 6:
        return None
    return player, server


async def safe_edit(
    cb: CallbackQuery, text: str, markup: InlineKeyboardMarkup | None = None
) -> None:
    """Паёмро иваз мекунад; агар нашавад — паёми нав мефиристад."""
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest as exc:
        if "message is not modified" in str(exc):
            return
        try:
            await cb.message.answer(text, reply_markup=markup)
        except Exception:  # pragma: no cover
            log.exception("Паём фиристода нашуд")


async def show_main_menu(
    event: Message | CallbackQuery, db: Database, cfg: Config, *, edit: bool = True
) -> None:
    user_id = event.from_user.id
    user = db.user(user_id)
    balance = user.balance if user else 0
    text = texts.welcome(balance, cfg.currency, partner=db.is_partner(user_id))
    markup = keyboards.main_menu(
        is_admin=cfg.is_admin(user_id),
        reviews_url=cfg.reviews_url,
        other_games=db.active_count(catalog.CAT_OTHER) > 0,
    )
    if isinstance(event, CallbackQuery) and edit:
        await safe_edit(event, text, markup)
    else:
        message = event.message if isinstance(event, CallbackQuery) else event
        await message.answer(text, reply_markup=markup)


async def notify_admins(
    bot: Bot,
    cfg: Config,
    text: str,
    markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Ба ҳамаи админҳо хабар медиҳад. Хатои як админ ба боқӣ халал намерасонад."""
    for admin_id in cfg.admin_ids:
        try:
            await bot.send_message(admin_id, text, reply_markup=markup)
        except Exception as exc:
            log.warning("Ба админ %s хабар нарасид: %s", admin_id, exc)


async def notify_user(bot: Bot, user_id: int, text: str) -> bool:
    try:
        await bot.send_message(user_id, text)
        return True
    except Exception as exc:
        log.info("Ба корбар %s хабар нарасид: %s", user_id, exc)
        return False


def current_user(event: Message | CallbackQuery, db: Database) -> User:
    src = event.from_user
    return db.touch_user(src.id, src.username, src.first_name)

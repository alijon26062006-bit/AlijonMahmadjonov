"""Обязательная подписка на каналы.

Логика перенесена из PHP как есть, включая важное поведение: если бот не
админ в канале или канал указан неверно, такой канал просто пропускается,
а не блокирует покупателя. Любая неожиданная ошибка тоже пропускает
пользователя дальше — лучше отдать товар, чем повесить бота.
"""
from __future__ import annotations

import time

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import db
from handlers.common import is_admin, log
from texts import t

MEMBER_STATUSES = ("creator", "administrator", "member")

_CACHE_SEC = 90        # память процесса
_DB_CACHE_SEC = 300    # отметка sub_ok_at в базе

_cache: dict[int, tuple[bool, float]] = {}


def norm_chat(raw: str) -> str:
    """Приводит канал к виду @username или -100…, понятному getChatMember.

    Пригласительные ссылки (+xxx, joinchat) проверить нельзя — для них
    возвращаем пустую строку, такой канал пропускается.
    """
    c = (raw or "").strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if c.startswith(prefix):
            c = c[len(prefix):]
            break
    if not c or c[0] == "+" or "joinchat" in c:
        return ""
    if c[0] not in "@-":
        c = "@" + c
    return c


def btn_link(row: dict) -> str:
    link = (row.get("link") or "").strip()
    if link:
        return link
    chat = (row.get("chat") or "").strip()
    if chat.startswith("http"):
        return chat
    return f"https://t.me/{chat.lstrip('@')}" if chat and not chat.startswith("-") else ""


async def _is_member(bot: Bot, chat: str, uid: int) -> bool | None:
    """True — состоит, False — нет, None — проверить не удалось."""
    try:
        member = await bot.get_chat_member(chat_id=chat, user_id=uid)
        return member.status in MEMBER_STATUSES
    except Exception as e:
        log.debug("подписку на %s проверить не вышло: %s", chat, e)
        return None


async def ok(bot: Bot, uid: int) -> bool:
    """Пускать ли пользователя. Админы и случай «каналов нет» — всегда да."""
    try:
        if is_admin(uid):
            return True
        channels = await db.subs_list(True)
        if not channels:
            return True

        hit = _cache.get(uid)
        if hit and (time.time() - hit[1]) < _CACHE_SEC:
            return hit[0]

        if await db.sub_ok_at(uid) > int(time.time()) - _DB_CACHE_SEC:
            _cache[uid] = (True, time.time())
            return True

        allowed = True
        for row in channels:
            chat = norm_chat(row.get("chat") or "")
            if not chat:
                continue
            res = await _is_member(bot, chat, uid)
            if res is False:
                allowed = False
                break

        _cache[uid] = (allowed, time.time())
        if allowed:
            await db.mark_sub_ok(uid)
        return allowed
    except Exception as e:
        log.warning("проверка подписки упала, пропускаю пользователя: %s", e)
        return True


async def missing(bot: Bot, uid: int) -> list[dict]:
    """Каналы, на которые пользователь ещё не подписан."""
    if is_admin(uid):
        return []
    out = []
    for row in await db.subs_list(True):
        chat = norm_chat(row.get("chat") or "")
        if not chat:
            continue
        if await _is_member(bot, chat, uid) is False:
            out.append(row)
    return out


def kb(channels: list[dict], lang: str) -> InlineKeyboardMarkup:
    rows = []
    for c in channels:
        link = btn_link(c)
        if not link:
            continue
        title = (c.get("title") or c.get("chat") or "")[:40]
        rows.append([InlineKeyboardButton(text=f"▸ {title}", url=link)])
    rows.append([InlineKeyboardButton(text="✓ " + t(lang, "sub_check"),
                                      callback_data="subchk")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def text(lang: str) -> str:
    return (f"<b>{t(lang, 'sub_title')}</b>\n"
            f"<code>───────────────</code>\n"
            f"{t(lang, 'sub_txt')}\n\n{t(lang, 'sub_why')}")


def drop_cache(uid: int) -> None:
    """Сбросить кэш — после нажатия «я подписался» проверяем заново."""
    _cache.pop(uid, None)

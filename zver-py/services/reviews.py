"""Отзывы: запрос звёзд у покупателя и публикация в канал.

Правила из PHP-версии: отзыв спрашивается один раз по выполненному
заказу; в канал уходит, только если звёзд не меньше настройки rev_min
(по умолчанию 4) либо публикацию запустил админ вручную; при rev_anon=1
имя скрывается до первой буквы.
"""
from __future__ import annotations

import re

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config
import db
from handlers.common import log
from texts import t

MAX_TXT = 500


def stars_kb(oid: int) -> InlineKeyboardMarkup:
    btn = lambda n: InlineKeyboardButton(text="★" * n, callback_data=f"rv:{oid}:{n}")
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn(1), btn(2), btn(3)],
        [btn(4), btn(5)],
    ])


async def ask(bot: Bot, oid: int) -> bool:
    """Спросить оценку по заказу. False — заказ не выполнен или уже спрашивали."""
    order = await db.order(oid)
    if not order or order.get("status") != "done":
        return False
    if not await db.review_open(int(order["uid"]), oid):
        return False

    lang = (await db.get_user(int(order["uid"])) or {}).get("lang")
    try:
        await bot.send_message(int(order["uid"]),
                               f"<b>{t(lang, 'rev_ask')}</b>",
                               reply_markup=stars_kb(oid))
        return True
    except Exception as e:
        log.debug("отзыв по #%s не запрошен: %s", oid, e)
        return False


async def channel() -> str:
    """Канал для отзывов: rev_ch → reviews → channel. Приводим к @name / -100…"""
    for key in ("rev_ch", "reviews", "channel"):
        raw = (await db.setting(key, "")).strip()
        if not raw:
            continue
        if raw[0] in "@-" or raw.lstrip("-").isdigit():
            return raw
        m = re.search(r"t\.me/([A-Za-z0-9_]+)", raw)
        return "@" + (m.group(1) if m else raw.lstrip("@"))
    return ""


async def post(bot: Bot, oid: int, force: bool = False) -> bool:
    """Опубликовать отзыв в канал. force — админ публикует вручную."""
    rev = await db.review_by_order(oid)
    if not rev:
        return False
    if int(rev.get("posted") or 0) == 1 and not force:
        return False

    stars = int(rev.get("stars") or 0)
    if stars < 1:
        return False                       # ещё не оценил
    stars = max(1, min(5, stars))

    try:
        min_stars = max(1, min(5, int(await db.setting("rev_min", "4") or 4)))
    except ValueError:
        min_stars = 4
    if stars < min_stars and not force:
        return False

    chat = await channel()
    if not chat:
        return False

    order = await db.order(oid) or {}
    user = await db.get_user(int(rev["uid"])) or {}

    if (await db.setting("rev_anon", "0")) == "1":
        name = ((user.get("name") or "M").strip()[:1]) + "***"
    else:
        name = (user.get("name") or "").strip() or "Покупатель"
        if user.get("username"):
            name = "@" + str(user["username"]).lstrip("@")

    txt = (rev.get("txt") or "").strip()
    if txt == "-":
        txt = ""

    shop = await db.setting("shop", "ZVER TAJ")
    body = "★" * stars + "☆" * (5 - stars) + "\n<code>───────────────</code>\n"
    if order.get("game_name"):
        body += f"<b>{_esc(order['game_name'])}</b>"
        if order.get("pack_name"):
            body += f" · {_esc(order['pack_name'])}"
        body += "\n"
    if txt:
        body += f"\n«{_esc(txt[:MAX_TXT])}»\n"
    body += f"\n— {_esc(name)}\n<code>───────────────</code>\n<i>{_esc(shop)}</i>"

    kb = None
    try:
        me = await bot.get_me()
        if me.username:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text="▸ " + shop.upper(), url=f"https://t.me/{me.username}")]])
    except Exception:
        pass

    try:
        await bot.send_message(chat, body, reply_markup=kb,
                               disable_web_page_preview=True)
    except Exception as e:
        log.warning("отзыв не ушёл в канал %s: %s", chat, e)
        for admin_id in config.ADMINS:
            try:
                await bot.send_message(
                    admin_id,
                    "⚠︎ <b>ОТЗЫВ НЕ УШЁЛ В КАНАЛ</b>\n"
                    "<code>───────────────</code>\n"
                    f"Канал · <code>{_esc(chat)}</code>\n"
                    f"Причина · {_esc(str(e))}\n\n"
                    "<i>Сделайте бота админом канала.</i>")
            except Exception:
                pass
        return False

    await db.review_mark_posted(oid)
    return True


async def ask_pending(bot: Bot, limit: int = 15) -> int:
    """Разослать запросы отзывов по свежим выполненным заказам."""
    if (await db.setting("ask_rev", "1")) != "1":
        return 0
    sent = 0
    for row in await db.orders_awaiting_review(limit):
        if await ask(bot, int(row["id"])):
            sent += 1
    return sent


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

"""Боты для гильдии (Glory клана FF) — через Donatix, прямо в боте.

Клиент выбирает регион, вводит ID клана и платит с баланса бота. Бот
запускает группу через Donatix API (деньги у Donatix списываются с баланса
владельца бота), а клиенту присылает одно сообщение с цифрами — слава клана,
сколько набрано, участники, время работы. Это сообщение обновляется само
каждые LIVE_EVERY секунд, пока группа работает (live_loop), и по кнопке.

Деньги клиента:
  • не запустилось сразу — возвращаем тут же;
  • Donatix позже сообщил «не запустилась» (refunded) — возвращаем в live_loop;
  • после запуска — не возвращаются, можно только остановить.

Работает, только когда бот подключён к Donatix (DONATIX_URL) и Donatix
продаёт Glory (available).
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from decimal import Decimal, InvalidOperation

import aiohttp
import aiosqlite
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app import db, runtime
from app.config import settings
from app.money import fmt

log = logging.getLogger(__name__)

LIVE_EVERY = 30            # секунд между обновлениями «живого» сообщения
REGIONS_TTL = 300          # список регионов и цен держим 5 минут
TIMEOUT = aiohttp.ClientTimeout(total=25)
CLAN_RE = re.compile(r"^\d{5,15}$")

SCHEMA = """
CREATE TABLE IF NOT EXISTS glory_orders (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    dx_id       TEXT NOT NULL,          -- номер у Donatix: gl-15
    clan_id     TEXT NOT NULL,
    region      TEXT NOT NULL,
    price       INTEGER NOT NULL,       -- дирамы, списано с клиента
    cost        INTEGER NOT NULL,       -- дирамы, во что обошлось владельцу
    status      TEXT NOT NULL,          -- starting / running / stopped / failed
    refunded    INTEGER NOT NULL DEFAULT 0,
    chat_id     INTEGER,
    message_id  INTEGER,                -- «живое» сообщение с цифрами
    last_text   TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
)
"""

ERRORS = {   # коды Donatix → понятный клиенту текст (по-таджикски)
    "clan_busy": "Барои ин клан аллакай гурӯҳ кор карда истодааст — то анҷоми он интизор шавед.",
    "invalid_clan_id": "ID-и клан нодуруст аст. Танҳо рақамҳо, масалан 3012345678.",
    "invalid_region": "Минтақаро аз нав интихоб кунед.",
    "insufficient_balance": "Хизмат муваққатан дастрас нест. Пул ба баланс баргашт.",
    "not_available": "Хизмат муваққатан дастрас нест.",
}
STATUS = {"starting": "⏳ Оғоз мешавад", "running": "🟢 Кор мекунад", "stopped": "⏹ Қатъ шуд",
          "failed": "❌ Оғоз нашуд"}

available = False                    # показывать ли раздел в меню (обновляет refresh_available)
_regions: tuple[float, list[dict]] = (0.0, [])
_tasks: set[asyncio.Task] = set()


class GloryFail(Exception):
    pass


def connected() -> bool:
    return bool(os.environ.get("DONATIX_URL") and settings.fazer_api_key)


async def _dx(method: str, path: str, json: dict | None = None) -> tuple[int, dict]:
    url = os.environ["DONATIX_URL"].rstrip("/") + "/api/v2/glory" + path
    headers = {"X-API-Key": settings.fazer_api_key, "Accept": "application/json"}
    async with aiohttp.ClientSession(timeout=TIMEOUT, headers=headers) as s:
        async with s.request(method, url, json=json) as r:
            try:
                body = await r.json(content_type=None)
            except ValueError:
                body = {}
            return r.status, body if isinstance(body, dict) else {}


async def ensure(conn: aiosqlite.Connection) -> None:
    await conn.execute(SCHEMA)
    await conn.commit()


async def regions(force: bool = False) -> list[dict]:
    """Регионы и цены от Donatix (кэш 5 минут). Пусто — Glory сейчас не продаётся."""
    global _regions, available
    at, items = _regions
    if not force and items and time.time() - at < REGIONS_TTL:
        return items
    if not connected():
        available = False
        return []
    try:
        status, body = await _dx("GET", "/regions")
    except (aiohttp.ClientError, TimeoutError):
        return items          # Donatix не ответил — оставляем прежний список
    items = body.get("items") if status == 200 and isinstance(body.get("items"), list) else []
    _regions = (time.time(), items)
    available = bool(items)
    return items


async def refresh_available() -> bool:
    await regions(force=True)
    return available


def price_of(region: dict) -> tuple[int, int]:
    """(цена клиенту, себестоимость) в дирамах. Цену задаёт владелец в /panel → «🛡 Glory — цены»:
    одна цена на все регионы (glory_price_diram) или своя наценка (glory_margin); не задал —
    цена Donatix по курсу бота + общая наценка."""
    from app.services.games import offer_cost, offer_price
    try:
        usd = Decimal(str(region.get("price_usd") or "0"))
    except InvalidOperation:
        return 0, 0
    cost = offer_cost(usd)
    fixed = runtime.get_int("glory_price_diram")
    if fixed > 0:
        return fixed, cost
    return offer_price(usd, runtime.get_int("glory_margin") or runtime.margin_percent()), cost


def flag(code: str) -> str:
    code = (code or "").upper()
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code) if len(code) == 2 and code.isalpha() else "🌐"


async def launch(bot: Bot, conn: aiosqlite.Connection, user_id: int, region_id: str, clan_id: str) -> int:
    """Списать с клиента, запустить у Donatix. Не вышло — деньги назад и GloryFail с причиной."""
    await ensure(conn)
    if not CLAN_RE.match(clan_id):
        raise GloryFail(ERRORS["invalid_clan_id"])
    region = next((r for r in await regions() if r.get("id") == region_id), None)
    if region is None:
        raise GloryFail(ERRORS["invalid_region"])
    price, cost = price_of(region)
    if price <= 0:
        raise GloryFail(ERRORS["not_available"])
    if not await db.charge(conn, user_id, price):
        raise GloryFail(f"Дар баланс маблағ кифоя нест: {fmt(price)} лозим. Аввал балансро пур кунед.")
    try:
        status, body = await _dx("POST", "/orders", {"region": region_id, "clan_id": clan_id})
    except (aiohttp.ClientError, TimeoutError):
        status, body = 0, {}
    order = body.get("order") if status == 200 else None
    if not isinstance(order, dict) or not order.get("id"):
        await db.credit(conn, user_id, price)
        code = str(body.get("code") or "")
        if code == "insufficient_balance":
            from app.services.delivery import notify_admins
            await notify_admins(bot, f"⚠️ Glory: на счёте Donatix не хватает денег — клиент {user_id} не смог купить "
                                     f"(клан {clan_id}). Пополните счёт: /donatix")
        raise GloryFail(ERRORS.get(code) or "Оғоз нашуд — пул ба баланс баргашт. Баъдтар боз кӯшиш кунед.")
    now = time.time()
    cur = await conn.execute(
        "INSERT INTO glory_orders (user_id, dx_id, clan_id, region, price, cost, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, str(order["id"]), clan_id, region_id, price, cost, str(order.get("status") or "starting"), now, now))
    await conn.commit()
    log.info("Glory: клиент %s, клан %s, %s — %s", user_id, clan_id, region_id, order["id"])
    from app.services.delivery import notify_admins
    await notify_admins(bot, f"🛡 Glory: клиент {user_id} запустил ботов для клана {clan_id} ({region_id.upper()}) "
                             f"— {fmt(price)}, Donatix {order['id']}")
    return int(cur.lastrowid)


async def get(conn: aiosqlite.Connection, gid: int, user_id: int | None = None) -> aiosqlite.Row | None:
    await ensure(conn)
    sql, args = "SELECT * FROM glory_orders WHERE id = ?", [gid]
    if user_id is not None:
        sql, args = sql + " AND user_id = ?", [gid, user_id]
    async with conn.execute(sql, args) as cur:
        return await cur.fetchone()


async def mine(conn: aiosqlite.Connection, user_id: int, limit: int = 10) -> list[aiosqlite.Row]:
    await ensure(conn)
    async with conn.execute("SELECT * FROM glory_orders WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                            (user_id, limit)) as cur:
        return list(await cur.fetchall())


async def live(conn: aiosqlite.Connection, g: aiosqlite.Row) -> dict:
    """Свежие цифры у Donatix; заодно статус и возврат денег, если группа так и не запустилась."""
    try:
        status, body = await _dx("GET", f"/orders/{g['dx_id']}")
    except (aiohttp.ClientError, TimeoutError):
        status, body = 0, {}
    order = body.get("order") if status == 200 and isinstance(body.get("order"), dict) else {}
    new = str(order.get("status") or g["status"])
    if order and new != g["status"]:
        await conn.execute("UPDATE glory_orders SET status = ?, updated_at = ? WHERE id = ?", (new, time.time(), g["id"]))
        await conn.commit()
    if new == "failed" and order.get("refunded") and not g["refunded"]:
        cur = await conn.execute("UPDATE glory_orders SET refunded = 1 WHERE id = ? AND refunded = 0", (g["id"],))
        await conn.commit()
        if cur.rowcount:
            await db.credit(conn, g["user_id"], g["price"])
            log.info("Glory %s: не запустилась у Donatix — клиенту возвращено %s", g["id"], fmt(g["price"]))
    return order


def text(g: aiosqlite.Row, order: dict) -> str:
    clan = order.get("clan") if isinstance(order.get("clan"), dict) else {}
    status = str(order.get("status") or g["status"])
    lines = [f"🛡 <b>Glory барои клан</b> <code>{g['clan_id']}</code>",
             f"Минтақа: {flag(g['region'])} {g['region'].upper()} · {STATUS.get(status, status)}"]
    if clan.get("name"):
        members = f" · аъзоён: {clan.get('members')}" + (f"/{clan['capacity']}" if clan.get("capacity") else "")
        lines.append(f"Клан: <b>{clan['name']}</b> · сатҳ {clan.get('level', '—')}{members}")
    if order.get("glory") is not None:
        lines.append(f"\n🏆 Ҳоло: <b>{order.get('glory') or 0}</b> glory")
        lines.append(f"📈 Ҷамъ шуд: <b>+{order.get('farmed') or 0}</b>")
    if order.get("uptime"):
        lines.append(f"⏱ Вақти кор: {order['uptime']} · ботҳо: {order.get('bots') or '—'}")
    if status == "failed":
        lines.append("\nГурӯҳ оғоз нашуд — пул ба баланс баргашт." if g["refunded"] or order.get("refunded")
                     else "\nГурӯҳ оғоз нашуд.")
    elif status in ("starting", "running"):
        lines.append(f"\n<i>Рақамҳо худ ба худ ҳар {LIVE_EVERY} сония нав мешаванд.</i>")
    else:
        lines.append("\nГурӯҳ кори худро анҷом дод.")
    return "\n".join(lines)


def keyboard(g: aiosqlite.Row, status: str) -> InlineKeyboardMarkup:
    rows = []
    if status in ("starting", "running"):
        rows.append([InlineKeyboardButton(text="🔄 Навсозӣ", callback_data=f"gl:u:{g['id']}"),
                     InlineKeyboardButton(text="⏹ Қатъ кардан", callback_data=f"gl:s:{g['id']}")])
    rows.append([InlineKeyboardButton(text="🛡 Glory", callback_data="gl:home"),
                 InlineKeyboardButton(text="🏠 Меню", callback_data="m:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show(bot: Bot, conn: aiosqlite.Connection, g: aiosqlite.Row, *, chat_id: int | None = None,
               message_id: int | None = None) -> None:
    """Нарисовать «живое» сообщение: поправить старое или прислать новое и запомнить его."""
    order = await live(conn, g)
    g = await get(conn, g["id"])
    body = text(g, order)
    markup = keyboard(g, str(order.get("status") or g["status"]))
    chat = chat_id or g["chat_id"] or g["user_id"]
    mid = message_id or g["message_id"]
    if mid and body == g["last_text"] and message_id is None:
        return                              # ничего не поменялось — Telegram зря не дёргаем
    if mid:
        try:
            await bot.edit_message_text(body, chat_id=chat, message_id=mid, reply_markup=markup, parse_mode="HTML")
        except TelegramAPIError as exc:
            if "not modified" not in str(exc):
                mid = None                  # сообщение удалили или оно старое — пришлём новое
    if not mid:
        sent = await bot.send_message(chat, body, reply_markup=markup, parse_mode="HTML")
        mid = sent.message_id
    await conn.execute("UPDATE glory_orders SET chat_id = ?, message_id = ?, last_text = ? WHERE id = ?",
                       (chat, mid, body, g["id"]))
    await conn.commit()


async def stop(conn: aiosqlite.Connection, g: aiosqlite.Row) -> bool:
    try:
        status, _ = await _dx("POST", f"/orders/{g['dx_id']}/stop")
    except (aiohttp.ClientError, TimeoutError):
        return False
    if status == 200:
        await conn.execute("UPDATE glory_orders SET status = 'stopped', updated_at = ? WHERE id = ?",
                           (time.time(), g["id"]))
        await conn.commit()
    return status == 200


async def live_loop(bot: Bot) -> None:
    """Фон: у всех работающих групп — свежие цифры в «живом» сообщении клиента, раз в LIVE_EVERY секунд.
    Переживает перезапуск бота: список берётся из базы."""
    if not connected():
        return
    while True:
        try:
            await refresh_available()
            conn = await db.connect()
            try:
                await ensure(conn)
                async with conn.execute("SELECT * FROM glory_orders WHERE status IN ('starting', 'running') "
                                        "ORDER BY id LIMIT 200") as cur:
                    rows = list(await cur.fetchall())
                for g in rows:
                    try:
                        await show(bot, conn, g)
                    except Exception as exc:  # noqa: BLE001 — один заказ не должен остановить остальные
                        log.warning("Glory %s: обновление — %s", g["id"], exc)
            finally:
                await conn.close()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — фон не должен умирать
            log.warning("Glory: фоновое обновление — %s", exc)
        await asyncio.sleep(LIVE_EVERY)


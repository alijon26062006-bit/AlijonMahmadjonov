"""Магазин в Telegram — официальный бот проекта.

Покупатель делает всё кнопками: игры, Telegram Stars/Premium, карты, баланс, заказы.
Цены те же, что на сайте. Для каждого покупателя сайт сам заводит аккаунт, привязанный к Telegram:
баланс, заказы и D-коины общие с сайтом. Заказы помечаются source='shopbot' — в статистике видно,
сколько продано через бот.

Сообщения не плодятся: бот правит одно «экранное» сообщение. Статусы заказов и пополнений
бот присылает сам (следит за ними в shop_watch).
"""

from __future__ import annotations

import html
import json
import logging
import secrets
import sqlite3
import threading
import time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Callable

from . import accounts, db, orders, payments
from .catalog import get_product
from .config import Config

log = logging.getLogger(__name__)

SOURCE = "shopbot"
PAGE = 8                      # кнопок-игр на странице
PACKS = 10                    # пакетов на странице
MSG_LIMIT = (30, 10)          # не больше 30 действий за 10 секунд
WATCH_EVERY = 4               # как часто проверять статусы заказов и пополнений, сек
FINAL = ("completed", "failed", "cancelled", "refunded")

GROUPS = {   # раздел меню → виды товаров
    "games": ("topup", "game_key"),
    "tg": ("telegram_stars", "telegram_premium"),
    "cards": ("gift_card",),
    "steam": ("steam_topup",),
}

# Тексты: (русский, таджикский)
T: dict[str, tuple[str, str]] = {
    "hello": ("<b>{name}, добро пожаловать в {site}!</b>\n\n"
              "🎮 Донат в игры, ⭐ Telegram Stars и Premium, 🎁 карты — быстро и по честной цене.\n\n"
              "💰 Баланс: <b>{balance}</b>",
              "<b>{name}, хуш омадед ба {site}!</b>\n\n"
              "🎮 Донат ба бозиҳо, ⭐ Telegram Stars ва Premium, 🎁 кортҳо — зуд ва бо нархи ҳалол.\n\n"
              "💰 Баланс: <b>{balance}</b>"),
    "games": ("🎮 Игры", "🎮 Бозиҳо"),
    "tg": ("⭐ Stars / Premium", "⭐ Stars / Premium"),
    "cards": ("🎁 Карты", "🎁 Кортҳо"),
    "steam": ("🕹 Steam", "🕹 Steam"),
    "hits": ("🔥 Хиты недели", "🔥 Хитҳои ҳафта"),
    "balance": ("💰 Баланс", "💰 Баланс"),
    "orders": ("📦 Мои заказы", "📦 Фармоишҳои ман"),
    "support": ("🆘 Поддержка", "🆘 Дастгирӣ"),
    "lang": ("🌐 Язык", "🌐 Забон"),
    "back": ("‹ Назад", "‹ Бозгашт"),
    "home": ("🏠 Меню", "🏠 Меню"),
    "search": ("🔎 Поиск игры", "🔎 Ҷустуҷӯи бозӣ"),
    "search_ask": ("🔎 Напишите название игры, например <i>PUBG</i>.",
                   "🔎 Номи бозиро нависед, масалан <i>PUBG</i>."),
    "nothing": ("Ничего не нашлось. Попробуйте другое название.", "Ҳеҷ чиз ёфт нашуд. Номи дигарро санҷед."),
    "pick_game": ("<b>{title}</b>\nВыберите:", "<b>{title}</b>\nИнтихоб кунед:"),
    "hits_title": ("🔥 <b>Хиты недели</b> — что покупают чаще всего:",
                   "🔥 <b>Хитҳои ҳафта</b> — чизе ки бештар мехаранд:"),
    "pick_pack": ("<b>{game}</b>\nВыберите пакет:", "<b>{game}</b>\nБастаро интихоб кунед:"),
    "ask_field": ("<b>{product}</b>\n\n✍️ Введите: <b>{label}</b>", "<b>{product}</b>\n\n✍️ Ворид кунед: <b>{label}</b>"),
    "pick_field": ("<b>{product}</b>\n\nВыберите: <b>{label}</b>", "<b>{product}</b>\n\nИнтихоб кунед: <b>{label}</b>"),
    "saved": ("💾 {value}", "💾 {value}"),
    "ask_qty": ("<b>{product}</b>\n\nСколько? От {lo} до {hi}. Нажмите или напишите число.",
                "<b>{product}</b>\n\nЧанд? Аз {lo} то {hi}. Пахш кунед ё рақам нависед."),
    "confirm": ("🧾 <b>Проверьте заказ</b>\n\n{product}\n{fields}\n💵 К оплате: <b>{total}</b>\n"
                "💰 На балансе: {balance}",
                "🧾 <b>Фармоишро санҷед</b>\n\n{product}\n{fields}\n💵 Пардохт: <b>{total}</b>\n"
                "💰 Дар баланс: {balance}"),
    "pay": ("✅ Оплатить", "✅ Пардохт"),
    "cancel": ("❌ Отмена", "❌ Бекор"),
    "no_money": ("\n\n⚠️ Не хватает <b>{need}</b>. Пополните баланс — и заказ в одно нажатие.",
                 "\n\n⚠️ <b>{need}</b> намерасад. Балансро пур кунед — фармоиш бо як пахш."),
    "topup": ("➕ Пополнить", "➕ Пур кардан"),
    "history": ("📜 История", "📜 Таърих"),
    "created": ("⏳ <b>Заказ {id} принят</b>\n{product}\nСписано: {total}\n\nКак только будет готово — напишу.",
                "⏳ <b>Фармоиш {id} қабул шуд</b>\n{product}\nПардохт: {total}\n\nВақте тайёр шавад — менависам."),
    "done": ("✅ <b>Заказ {id} выполнен!</b>\n{product}", "✅ <b>Фармоиш {id} иҷро шуд!</b>\n{product}"),
    "failed": ("❌ <b>Заказ {id} не выполнен</b>\n{product}\n{reason}\n\n{total} вернулись на баланс.",
               "❌ <b>Фармоиш {id} иҷро нашуд</b>\n{product}\n{reason}\n\n{total} ба баланс баргашт."),
    "repeat": ("🔁 Повторить", "🔁 Такрор"),
    "balance_screen": ("💰 <b>Ваш баланс: {balance}</b>\n\nПополните — и покупайте в одно нажатие.",
                       "💰 <b>Баланси шумо: {balance}</b>\n\nПур кунед — ва бо як пахш харед."),
    "pick_method": ("➕ <b>Пополнение</b>\nВыберите способ оплаты:",
                    "➕ <b>Пур кардан</b>\nУсули пардохтро интихоб кунед:"),
    "no_methods": ("Пополнение временно недоступно. Напишите в поддержку.",
                   "Пур кардан муваққатан дастрас нест. Ба дастгирӣ нависед."),
    "ask_amount": ("<b>{method}</b>\nСколько сомони пополнить? Нажмите или напишите сумму.",
                   "<b>{method}</b>\nЧанд сомонӣ пур кунем? Пахш кунед ё маблағро нависед."),
    "pay_details": ("🧾 <b>Заявка #{id}</b>\n\nПереведите <b>{amount}</b>\n{method}:\n<code>{details}</code>\n\n"
                    "📸 Потом отправьте сюда <b>фото чека</b>.",
                    "🧾 <b>Дархост #{id}</b>\n\n<b>{amount}</b> гузаронед\n{method}:\n<code>{details}</code>\n\n"
                    "📸 Баъд <b>акси чек</b>-ро ба ин ҷо фиристед."),
    "pay_auto": ("🧾 <b>Заявка #{id}</b>\n\nПереведите ровно <b>{amount}</b>\n<code>{address}</code>\n\n{note}",
                 "🧾 <b>Дархост #{id}</b>\n\nМаҳз <b>{amount}</b> гузаронед\n<code>{address}</code>\n\n{note}"),
    "checking": ("⏳ <b>Проверяем чек</b>\nПодождите, как только проверим — напишу.",
                 "⏳ <b>Чекро месанҷем</b>\nИнтизор шавед, баъди санҷиш менависам."),
    "paid": ("✅ <b>Баланс пополнен на {amount}</b>\nТеперь на балансе: {balance}",
             "✅ <b>Баланс {amount} пур шуд</b>\nҲоло дар баланс: {balance}"),
    "rejected": ("❌ <b>Заявка #{id} отклонена</b>\n{reason}", "❌ <b>Дархост #{id} рад шуд</b>\n{reason}"),
    "need_receipt": ("📸 Пришлите фото чека к заявке #{id}.", "📸 Акси чекро барои дархост #{id} фиристед."),
    "no_orders": ("Заказов пока нет. Выберите игру в меню 👇", "Ҳоло фармоиш нест. Бозиро аз меню интихоб кунед 👇"),
    "orders_title": ("📦 <b>Мои заказы</b>", "📦 <b>Фармоишҳои ман</b>"),
    "hist_title": ("📜 <b>История баланса</b>", "📜 <b>Таърихи баланс</b>"),
    "support_text": ("🆘 Есть вопрос? Напишите: {contact}", "🆘 Савол доред? Нависед: {contact}"),
    "slow": ("Слишком быстро — подождите пару секунд.", "Хеле зуд — якчанд сония интизор шавед."),
    "unsub": ("🔕 Отписаться от новостей", "🔕 Аз хабарҳо даст кашидан"),
    "unsubbed": ("Готово — новостей больше не будет. Вернуть: /news",
                 "Тайёр — дигар хабар намеояд. Баргардондан: /news"),
    "subbed": ("🔔 Новости и скидки включены.", "🔔 Хабарҳо ва тахфифҳо фаъол шуданд."),
    "error": ("⚠️ {text}", "⚠️ {text}"),
    "lang_pick": ("Выберите язык / Забонро интихоб кунед:", "Выберите язык / Забонро интихоб кунед:"),
    "more": ("Ещё ›", "Боз ›"),
    "status_processing": ("⏳ в работе", "⏳ дар кор"),
    "status_completed": ("✅ готов", "✅ тайёр"),
    "status_failed": ("❌ не выполнен", "❌ иҷро нашуд"),
}


def tr(lang: str, key: str, **kw: Any) -> str:
    pair = T[key]
    text = pair[1] if lang == "tj" else pair[0]
    return text.format(**kw) if kw else text


def _e(value: Any) -> str:
    return html.escape(str(value), quote=False)


Btn = tuple  # (текст, callback_data) или (текст, callback_data, style) или (текст, None, url)


def kb(rows: list[list[Btn]]) -> dict[str, Any]:
    out = []
    for row in rows:
        line = []
        for b in row:
            if len(b) == 3 and b[1] is None:
                line.append({"text": b[0], "url": b[2]})
                continue
            item = {"text": b[0], "callback_data": b[1]}
            if len(b) == 3 and b[2]:
                item["style"] = b[2]          # цвет кнопки: success (зелёная), danger (красная), primary
            line.append(item)
        out.append(line)
    return {"inline_keyboard": out}


# ── Покупатель: аккаунт на сайте, язык, сохранённые ID ──

def shop_user(conn: sqlite3.Connection, tg_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM shop_users WHERE tg_id = ?", (tg_id,)).fetchone()


def ensure_user(conn: sqlite3.Connection, tg_id: int, name: str = "", start: str = "") -> sqlite3.Row:
    """Аккаунт сайта для этого Telegram — создаётся при первом /start, дальше тот же."""
    row = shop_user(conn, tg_id)
    if row is not None:
        conn.execute("UPDATE shop_users SET last_seen = ?, name = COALESCE(NULLIF(?, ''), name) WHERE tg_id = ?",
                     (db.now(), name[:64], tg_id))
        return shop_user(conn, tg_id)
    with db.tx(conn):
        row = shop_user(conn, tg_id)
        if row is not None:
            return row
        # Уже привязан к аккаунту через бота поддержки — берём тот же аккаунт
        linked = conn.execute("SELECT user_id FROM support_links WHERE tg_id = ?", (tg_id,)).fetchone()
        if linked:
            uid = linked["user_id"]
        else:
            uid = accounts.create_user(conn, email=f"tg{tg_id}@telegram.user", login=f"tg{tg_id}",
                                       password=secrets.token_urlsafe(24), status="active",
                                       project="Покупатель из Telegram-бота")
        conn.execute("INSERT INTO shop_users (tg_id, user_id, name, lang, start_param, created_at, last_seen) "
                     "VALUES (?, ?, ?, '', ?, ?, ?)", (tg_id, uid, name[:64], start[:64] or None, db.now(), db.now()))
    return shop_user(conn, tg_id)


def saved_values(row: sqlite3.Row) -> dict[str, dict[str, str]]:
    try:
        return json.loads(row["saved_json"] or "{}")
    except ValueError:
        return {}


def remember_fields(conn: sqlite3.Connection, tg_id: int, category: str, fields: dict[str, str]) -> None:
    row = shop_user(conn, tg_id)
    data = saved_values(row)
    keep = {k: v for k, v in fields.items() if k not in ("amount",)}
    if keep:
        data[category] = keep
        conn.execute("UPDATE shop_users SET saved_json = ? WHERE tg_id = ?",
                     (json.dumps(data, ensure_ascii=False)[:20000], tg_id))


# ── Цены в сомони ──

def tjs_rate(conn: sqlite3.Connection, config: Config) -> Decimal:
    return payments.settings(conn, config)["tjs_rate"]


def money(micro: int, rate: Decimal) -> str:
    tjs = (Decimal(micro) / 10_000 * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{tjs:f} смн"


def unit_price_micro(config: Config, user: sqlite3.Row, product: dict[str, Any]) -> int:
    return orders.quote(config, user, product, max(product["min_qty"], 1))["total_micro"]


# ── Каталог для бота ──

def _kinds_sql(group: str) -> tuple[str, list[str]]:
    kinds = list(GROUPS.get(group, ()))
    return "kind IN (" + ",".join("?" * len(kinds)) + ")", kinds


def game_list(conn: sqlite3.Connection, group: str, q: str = "") -> list[sqlite3.Row]:
    """Игры раздела: сначала популярные (заказы за 30 дней), потом по алфавиту. rowid — для кнопок."""
    where, args = _kinds_sql(group)
    sql = (f"SELECT MIN(p.rowid) AS rid, p.category_id, p.category_name, "
           f"(SELECT COUNT(*) FROM orders o JOIN products x ON x.id = o.product_id "
           f" WHERE x.category_id = p.category_id "
           f" AND o.created_at >= strftime('%Y-%m-%dT%H:%M:%S', 'now', '-30 day')) AS pop "
           f"FROM products p WHERE p.active = 1 AND p.hidden = 0 AND p.{where}")
    if q:
        sql += " AND (p.category_name LIKE ? OR p.name LIKE ?)"
        args += [f"%{q}%", f"%{q}%"]
    sql += " GROUP BY p.category_id ORDER BY pop DESC, p.category_name"
    return conn.execute(sql, args).fetchall()


def search_all(conn: sqlite3.Connection, q: str) -> list[sqlite3.Row]:
    kinds = sorted({k for ks in GROUPS.values() for k in ks})
    sql = ("SELECT MIN(rowid) AS rid, category_id, category_name FROM products WHERE active = 1 AND hidden = 0 "
           "AND kind IN (" + ",".join("?" * len(kinds)) + ") AND (category_name LIKE ? OR name LIKE ?) "
           "GROUP BY category_id ORDER BY category_name LIMIT 20")
    return conn.execute(sql, [*kinds, f"%{q}%", f"%{q}%"]).fetchall()


def hits(conn: sqlite3.Connection, days: int = 7, limit: int = 8) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT MIN(p.rowid) AS rid, p.category_id, p.category_name, COUNT(o.id) AS n FROM orders o "
        "JOIN products p ON p.id = o.product_id WHERE o.status = 'completed' AND p.active = 1 AND p.hidden = 0 "
        "AND o.created_at >= strftime('%Y-%m-%dT%H:%M:%S', 'now', ?) GROUP BY p.category_id ORDER BY n DESC LIMIT ?",
        (f"-{days} days", limit)).fetchall()


def product_by_rid(conn: sqlite3.Connection, rid: Any) -> dict[str, Any] | None:
    try:
        row = conn.execute("SELECT id FROM products WHERE rowid = ?", (int(rid),)).fetchone()
    except (TypeError, ValueError):
        return None
    return get_product(conn, row["id"]) if row else None


def packs(conn: sqlite3.Connection, category_id: str) -> list[dict[str, Any]]:
    from .catalog import load_product
    rows = conn.execute("SELECT rowid AS rid, * FROM products WHERE category_id = ? AND active = 1 AND hidden = 0 "
                        "ORDER BY CAST(base_price AS REAL), name", (category_id,)).fetchall()
    out = []
    for r in rows:
        p = load_product(r)
        p["rid"] = r["rid"]
        out.append(p)
    return out


def delivery_text(order: sqlite3.Row) -> str:
    try:
        d = json.loads(order["delivery_json"] or "{}")
    except ValueError:
        return ""
    codes = d.get("codes") or d.get("keys") or []
    lines = []
    for c in codes:
        value = (c.get("key") or c.get("code") or json.dumps(c, ensure_ascii=False)) if isinstance(c, dict) else c
        lines.append(f"<code>{_e(value)}</code>")
    if lines:
        return "\n🔑 " + "\n🔑 ".join(lines)
    if d.get("message"):
        return "\n" + _e(d["message"])
    return ""


# ── Статистика для админки ──

def stats(conn: sqlite3.Connection, days: int = 1) -> dict[str, Any]:
    """Продажи через бот: заказы, выручка, прибыль за период (с 00:00 по местному времени) и покупатели."""
    since, _ = orders._local_start(conn, days)
    row = conn.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(total_micro), 0) AS revenue, "
        "COALESCE(SUM(total_micro - cost_micro), 0) AS profit FROM orders "
        "WHERE source = ? AND status = 'completed' AND COALESCE(completed_at, created_at) >= ?",
        (SOURCE, since)).fetchone()
    new = conn.execute("SELECT COUNT(*) FROM shop_users WHERE created_at >= ?", (since,)).fetchone()[0]
    return {"orders": row["n"], "revenue": row["revenue"], "profit": row["profit"], "new_users": new}


def overview(conn: sqlite3.Connection) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*), COALESCE(SUM(subscribed), 0) FROM shop_users").fetchone()
    buyers = conn.execute("SELECT COUNT(DISTINCT user_id) FROM orders WHERE source = ? AND status = 'completed'",
                          (SOURCE,)).fetchone()[0]
    top = conn.execute(
        "SELECT p.category_name AS name, MIN(p.rowid) AS rid, COUNT(*) AS n, SUM(o.total_micro) AS revenue "
        "FROM orders o JOIN products p ON p.id = o.product_id WHERE o.source = ? AND o.status = 'completed' "
        "AND o.created_at >= strftime('%Y-%m-%dT%H:%M:%S', 'now', '-30 day') "
        "GROUP BY p.category_id ORDER BY n DESC LIMIT 10",
        (SOURCE,)).fetchall()
    sources = conn.execute(
        "SELECT COALESCE(start_param, '') AS src, COUNT(*) AS n FROM shop_users GROUP BY src ORDER BY n DESC LIMIT 10"
    ).fetchall()
    return {"users": total[0], "subscribed": total[1], "buyers": buyers, "top": top, "sources": sources,
            "today": stats(conn, 1), "week": stats(conn, 7), "month": stats(conn, 30)}


def bot_username(conn: sqlite3.Connection) -> str:
    return db.get_setting(conn, "shop.bot_username") or ""


# ── Рассылка ──

def broadcast(config: Config, text: str, api: Callable[..., Any] | None = None) -> threading.Thread:
    """Новость всем, кто не отписался. В фоне, ~20 сообщений в секунду (лимит Telegram — 30)."""
    from .tgbot import TelegramApi
    api = api or TelegramApi(config.shop_bot_token)

    def run() -> None:
        conn = db.connect(config.db_path)
        sent = gone = 0
        try:
            rows = conn.execute("SELECT tg_id, lang FROM shop_users WHERE subscribed = 1").fetchall()
            for r in rows:
                try:
                    api("sendMessage", chat_id=r["tg_id"], text=text, parse_mode="HTML",
                        disable_web_page_preview=True,
                        reply_markup=kb([[(tr(r["lang"], "home"), "h")], [(tr(r["lang"], "unsub"), "unsub")]]))
                    sent += 1
                except Exception as exc:  # noqa: BLE001 — заблокировал бота: больше не шлём
                    if "blocked" in str(exc) or "deactivated" in str(exc) or "not found" in str(exc):
                        conn.execute("UPDATE shop_users SET subscribed = 0 WHERE tg_id = ?", (r["tg_id"],))
                        gone += 1
                time.sleep(0.05)
            db.set_setting(conn, "shop.last_broadcast", json.dumps({"at": db.now(), "sent": sent, "gone": gone}))
        finally:
            conn.close()
    thread = threading.Thread(target=run, name="donatix-shop-broadcast", daemon=True)
    thread.start()
    return thread


# ── Бот ──

class ShopBot:
    def __init__(self, config: Config, supplier: Any, api: Callable[..., Any] | None = None):
        from .tgbot import TelegramApi
        self.config = config
        self.supplier = supplier
        self.api = api or TelegramApi(config.shop_bot_token)
        self.state: dict[int, dict[str, Any]] = {}
        self._hits: dict[int, list[float]] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_watch = 0.0

    # цикл
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="donatix-shopbot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        conn = db.connect(self.config.db_path)
        offset = int(db.get_setting(conn, "shop.tg_offset", "0") or 0)
        try:
            self.api("deleteWebhook", drop_pending_updates=False)
            me = self.api("getMe") or {}
            if me.get("username"):
                db.set_setting(conn, "shop.bot_username", me["username"])
            self.api("setMyCommands", commands=[{"command": "start", "description": "Меню / Меню"},
                                                {"command": "balance", "description": "Баланс"},
                                                {"command": "orders", "description": "Мои заказы"},
                                                {"command": "lang", "description": "Язык / Забон"}])
            log.info("бот-магазин запущен: @%s", me.get("username"))
        except Exception as exc:
            log.warning("бот-магазин: %s", exc)
        try:
            while not self._stop.is_set():
                try:
                    updates = self.api("getUpdates", offset=offset, timeout=WATCH_EVERY,
                                       allowed_updates=["message", "callback_query"]) or []
                except Exception as exc:
                    log.warning("бот-магазин: %s", exc)
                    self._stop.wait(10)
                    continue
                for upd in updates:
                    offset = max(offset, int(upd["update_id"]) + 1)
                    try:
                        self.handle(conn, upd)
                    except Exception:
                        log.exception("бот-магазин: обработка %s", upd.get("update_id"))
                if updates:
                    db.set_setting(conn, "shop.tg_offset", str(offset))
                try:
                    self.watch(conn)
                except Exception:
                    log.exception("бот-магазин: статусы")
        finally:
            conn.close()

    # отправка
    def show(self, chat: int, text: str, rows: list[list[Btn]] | None = None, *, edit: int | None = None) -> int | None:
        """Показать экран: поправить сообщение edit, а не вышло — прислать новое. Вернёт message_id."""
        markup = kb(rows) if rows else None
        if edit:
            try:
                self.api("editMessageText", chat_id=chat, message_id=edit, text=text, parse_mode="HTML",
                         reply_markup=markup, disable_web_page_preview=True)
                return edit
            except Exception as exc:  # noqa: BLE001
                if "not modified" in str(exc):
                    return edit
        res = self.api("sendMessage", chat_id=chat, text=text, parse_mode="HTML", reply_markup=markup,
                       disable_web_page_preview=True) or {}
        return res.get("message_id")

    def _limited(self, tg_id: int) -> bool:
        count, window = MSG_LIMIT
        now = time.time()
        hits_ = [t for t in self._hits.get(tg_id, []) if now - t < window]
        hits_.append(now)
        self._hits[tg_id] = hits_
        return len(hits_) > count

    # входящие
    def handle(self, conn: sqlite3.Connection, upd: dict[str, Any]) -> None:
        if "callback_query" in upd:
            cq = upd["callback_query"]
            msg = cq.get("message") or {}
            chat = msg.get("chat") or {}
            if chat.get("type") != "private":
                return
            tg_id = int(chat["id"])
            sender = cq.get("from") or {}
            if self._limited(tg_id):
                self.api("answerCallbackQuery", callback_query_id=cq["id"], text=tr("", "slow"))
                return
            su = ensure_user(conn, tg_id, sender.get("first_name") or "")
            self.api("answerCallbackQuery", callback_query_id=cq["id"])
            self.on_button(conn, su, str(cq.get("data") or ""), msg.get("message_id"))
            return
        msg = upd.get("message") or {}
        chat = msg.get("chat") or {}
        if chat.get("type") != "private":
            return
        tg_id = int(chat["id"])
        if self._limited(tg_id):
            return
        sender = msg.get("from") or {}
        text = (msg.get("text") or "").strip()
        start = text.split(maxsplit=1)[1] if text.startswith("/start ") else ""
        su = ensure_user(conn, tg_id, sender.get("first_name") or "", start)
        if text.startswith("/"):
            self.on_command(conn, su, text, start)
            return
        if msg.get("photo") or msg.get("document"):
            self.on_receipt(conn, su, msg)
            return
        if text:
            self.on_text(conn, su, text)

    def on_command(self, conn: sqlite3.Connection, su: sqlite3.Row, text: str, start: str) -> None:
        tg_id, cmd = su["tg_id"], text.split()[0].split("@")[0].lower()
        self.state.pop(tg_id, None)
        if cmd == "/lang" or (cmd == "/start" and not su["lang"]):
            if start:
                self.state[tg_id] = {"after_lang": start}
            self.show(tg_id, tr("", "lang_pick"), [[("🇷🇺 Русский", "l:ru"), ("🇹🇯 Тоҷикӣ", "l:tj")]])
        elif cmd == "/balance":
            self.screen_balance(conn, su)
        elif cmd == "/orders":
            self.screen_orders(conn, su, 0)
        elif cmd == "/news":
            conn.execute("UPDATE shop_users SET subscribed = 1 WHERE tg_id = ?", (tg_id,))
            self.show(tg_id, tr(su["lang"], "subbed"), [[(tr(su["lang"], "home"), "h")]])
        elif cmd == "/start" and start:
            self.open_deep_link(conn, su, start)
        else:
            self.screen_home(conn, su)

    def open_deep_link(self, conn: sqlite3.Connection, su: sqlite3.Row, start: str, edit: int | None = None) -> None:
        """t.me/бот?start=g123 — сразу нужная игра (ссылки для постов в канале)."""
        if start.startswith("g") and start[1:].isdigit():
            p = product_by_rid(conn, start[1:])
            if p:
                self.screen_packs(conn, su, p["category_id"], 0, edit)
                return
        self.screen_home(conn, su, edit)

    # экраны
    def _user(self, conn: sqlite3.Connection, su: sqlite3.Row) -> sqlite3.Row:
        return accounts.get_user(conn, su["user_id"])

    def screen_home(self, conn: sqlite3.Connection, su: sqlite3.Row, edit: int | None = None) -> None:
        lang, user = su["lang"], self._user(conn, su)
        text = tr(lang, "hello", name=_e(su["name"] or "👋"), site=_e(self.config.site_name),
                  balance=money(user["balance_micro"], tjs_rate(conn, self.config)))
        rows = [[(tr(lang, "games"), "g:games:0", "primary")],
                [(tr(lang, "tg"), "g:tg:0"), (tr(lang, "cards"), "g:cards:0")],
                [(tr(lang, "hits"), "hit"), (tr(lang, "steam"), "g:steam:0")],
                [(tr(lang, "balance"), "b", "success"), (tr(lang, "orders"), "my:0")],
                [(tr(lang, "support"), "sup"), (tr(lang, "lang"), "lang")]]
        self.show(su["tg_id"], text, rows, edit=edit)

    def screen_games(self, conn: sqlite3.Connection, su: sqlite3.Row, group: str, page: int,
                     edit: int | None = None, q: str = "") -> None:
        lang = su["lang"]
        rows_all = search_all(conn, q) if q else game_list(conn, group)
        if not rows_all:
            self.show(su["tg_id"], tr(lang, "nothing"), [[(tr(lang, "search"), "s")], [(tr(lang, "home"), "h")]],
                      edit=edit)
            return
        part = rows_all[page * PAGE:(page + 1) * PAGE]
        rows: list[list[Btn]] = []
        for i in range(0, len(part), 2):
            rows.append([(r["category_name"][:30], f"c:{r['rid']}:0") for r in part[i:i + 2]])
        nav: list[Btn] = []
        if page > 0:
            nav.append(("‹", f"g:{group}:{page - 1}"))
        if (page + 1) * PAGE < len(rows_all) and not q:
            nav.append((tr(lang, "more"), f"g:{group}:{page + 1}"))
        if nav:
            rows.append(nav)
        if group == "games" or q:
            rows.append([(tr(lang, "search"), "s")])
        rows.append([(tr(lang, "home"), "h")])
        title = tr(lang, group) if group in GROUPS else "🔎"
        self.show(su["tg_id"], tr(lang, "pick_game", title=_e(title)), rows, edit=edit)

    def screen_hits(self, conn: sqlite3.Connection, su: sqlite3.Row, edit: int | None = None) -> None:
        lang = su["lang"]
        top = hits(conn) or game_list(conn, "games")[:PAGE]
        rows = [[(("🔥 " if i < 3 else "") + r["category_name"][:30], f"c:{r['rid']}:0")] for i, r in enumerate(top)]
        rows.append([(tr(lang, "home"), "h")])
        self.show(su["tg_id"], tr(lang, "hits_title"), rows, edit=edit)

    def screen_packs(self, conn: sqlite3.Connection, su: sqlite3.Row, category_id: str, page: int,
                     edit: int | None = None) -> None:
        lang, user = su["lang"], self._user(conn, su)
        items = packs(conn, category_id)
        if not items:
            self.screen_home(conn, su, edit)
            return
        rate = tjs_rate(conn, self.config)
        part = items[page * PACKS:(page + 1) * PACKS]
        rows: list[list[Btn]] = []
        for p in part:
            price = money(unit_price_micro(self.config, user, p), rate)
            if p["max_qty"] > 1 or p["kind"] == "steam_topup":
                price = "от " + price if lang != "tj" else "аз " + price
            rows.append([(f"{p['name'][:34]} — {price}", f"p:{p['rid']}")])
        nav: list[Btn] = []
        rid = items[0]["rid"]
        if page > 0:
            nav.append(("‹", f"c:{rid}:{page - 1}"))
        if (page + 1) * PACKS < len(items):
            nav.append((tr(lang, "more"), f"c:{rid}:{page + 1}"))
        if nav:
            rows.append(nav)
        rows.append([(tr(lang, "back"), f"g:{_group_of(items[0]['kind'])}:0"), (tr(lang, "home"), "h")])
        self.show(su["tg_id"], tr(lang, "pick_pack", game=_e(items[0]["category_name"])), rows, edit=edit)

    # покупка: поля → количество → подтверждение
    def start_product(self, conn: sqlite3.Connection, su: sqlite3.Row, rid: str, edit: int | None) -> None:
        p = product_by_rid(conn, rid)
        if p is None:
            self.screen_home(conn, su, edit)
            return
        self.state[su["tg_id"]] = {"step": "field", "rid": int(rid), "fields": {}, "fi": 0, "qty": 1,
                                   "msg": edit, "nonce": secrets.token_hex(6)}
        self.next_step(conn, su)

    def next_step(self, conn: sqlite3.Connection, su: sqlite3.Row) -> None:
        tg_id, lang = su["tg_id"], su["lang"]
        st = self.state.get(tg_id)
        p = product_by_rid(conn, st["rid"]) if st else None
        if p is None:
            self.state.pop(tg_id, None)
            self.screen_home(conn, su)
            return
        specs = p["fields"]
        if st["fi"] < len(specs):
            spec = specs[st["fi"]]
            st["step"] = "field"
            label = _e(spec.get("label") or spec["key"])
            rows: list[list[Btn]] = []
            if spec.get("options"):
                opts = spec["options"][:30]
                for i in range(0, len(opts), 2):
                    rows.append([(str(o)[:30], f"o:{st['fi']}:{i + j}") for j, o in enumerate(opts[i:i + 2])])
                text = tr(lang, "pick_field", product=_e(p["name"]), label=label)
            else:
                saved = saved_values(shop_user(conn, tg_id)).get(p["category_id"], {}).get(spec["key"])
                if saved:
                    rows.append([(tr(lang, "saved", value=saved[:30]), "sv", "primary")])
                text = tr(lang, "ask_field", product=_e(p["name"]), label=label)
            rows.append([(tr(lang, "cancel"), "x", "danger")])
            st["msg"] = self.show(tg_id, text, rows, edit=st.get("msg"))
            return
        if p["max_qty"] > 1 and p["min_qty"] < p["max_qty"] and st["step"] != "confirm" and not st.get("qty_set"):
            st["step"] = "qty"
            lo, hi = p["min_qty"], p["max_qty"]
            presets = sorted({v for v in (lo, 50, 100, 250, 500, 1000, 2500) if lo <= v <= hi})[:6]
            rows = [[(str(v), f"q:{v}") for v in presets[i:i + 3]] for i in range(0, len(presets), 3)]
            rows.append([(tr(lang, "cancel"), "x", "danger")])
            st["msg"] = self.show(tg_id, tr(lang, "ask_qty", product=_e(p["name"]), lo=lo, hi=hi), rows,
                                  edit=st.get("msg"))
            return
        self.screen_confirm(conn, su, p)

    def screen_confirm(self, conn: sqlite3.Connection, su: sqlite3.Row, p: dict[str, Any]) -> None:
        tg_id, lang = su["tg_id"], su["lang"]
        st = self.state[tg_id]
        user = self._user(conn, su)
        try:
            fields = orders._clean_fields(p, st["fields"])
            qty = orders._clean_quantity(p, st["qty"])
            total = orders.quote(self.config, user, p, orders._units(p, qty, fields))["total_micro"]
        except orders.OrderError as exc:
            st.update({"fi": 0, "fields": {}, "qty_set": False})
            self.show(tg_id, tr(lang, "error", text=_e(exc)), [[(tr(lang, "back"), f"p:{st['rid']}")],
                                                               [(tr(lang, "home"), "h")]], edit=st.get("msg"))
            return
        st["step"] = "confirm"
        rate = tjs_rate(conn, self.config)
        name = p["name"] + (f" × {qty}" if qty > 1 else "")
        lines = "\n".join(f"• {_e(s.get('label') or s['key'])}: <b>{_e(fields.get(s['key'], ''))}</b>"
                          for s in p["fields"])
        text = tr(lang, "confirm", product=f"<b>{_e(name)}</b>", fields=lines, total=money(total, rate),
                  balance=money(user["balance_micro"], rate))
        if user["balance_micro"] < total:
            text += tr(lang, "no_money", need=money(total - user["balance_micro"], rate))
            rows = [[(tr(lang, "topup"), "t", "success")], [(tr(lang, "cancel"), "x", "danger")]]
            st["resume"] = True
        else:
            rows = [[(tr(lang, "pay"), "ok", "success")], [(tr(lang, "cancel"), "x", "danger")]]
        st["msg"] = self.show(tg_id, text, rows, edit=st.get("msg"))

    def buy(self, conn: sqlite3.Connection, su: sqlite3.Row, edit: int | None) -> None:
        tg_id, lang = su["tg_id"], su["lang"]
        st = self.state.get(tg_id)
        p = product_by_rid(conn, st["rid"]) if st and st.get("step") == "confirm" else None
        if p is None:
            self.screen_home(conn, su, edit)
            return
        try:
            order, _ = orders.create_order(conn, self.config, self.supplier, self._user(conn, su),
                                           product_id=p["id"], quantity=st["qty"], fields=st["fields"],
                                           client_idem_key=f"shopbot-{tg_id}-{st['nonce']}", source=SOURCE)
        except orders.OrderError as exc:
            self.show(tg_id, tr(lang, "error", text=_e(exc)),
                      [[(tr(lang, "topup"), "t", "success")], [(tr(lang, "home"), "h")]], edit=edit)
            return
        self.state.pop(tg_id, None)
        remember_fields(conn, tg_id, p["category_id"], {k: str(v) for k, v in st["fields"].items()})
        rate = tjs_rate(conn, self.config)
        mid = self.show(tg_id, tr(lang, "created", id=order["public_id"], product=_e(order["product_name"]),
                                  total=money(order["total_micro"], rate)),
                        [[(tr(lang, "orders"), "my:0"), (tr(lang, "home"), "h")]], edit=edit)
        self.watch_add(conn, "order", order["id"], tg_id, mid, order["status"])

    def on_text(self, conn: sqlite3.Connection, su: sqlite3.Row, text: str) -> None:
        tg_id, lang = su["tg_id"], su["lang"]
        st = self.state.get(tg_id) or {}
        step = st.get("step")
        if step == "field":
            p = product_by_rid(conn, st["rid"])
            spec = p["fields"][st["fi"]] if p and st["fi"] < len(p["fields"]) else None
            if spec is None or spec.get("options"):
                self.next_step(conn, su)
                return
            st["fields"][spec["key"]] = text[:256]
            st["fi"] += 1
            st["msg"] = None   # ответ клиента ниже — новый экран отправим под ним
            self.next_step(conn, su)
        elif step == "qty":
            if text.isdigit():
                st["qty"], st["qty_set"], st["msg"] = int(text), True, None
            self.next_step(conn, su)
        elif step == "amount":
            st["msg"] = None
            self.create_topup(conn, su, text)
        elif step == "search":
            self.state.pop(tg_id, None)
            self.screen_games(conn, su, "games", 0, q=text[:40])
        elif step == "receipt":
            self.show(tg_id, tr(lang, "need_receipt", id=st["pid"]))
        else:
            hit = search_all(conn, text[:40])
            if hit:
                self.screen_games(conn, su, "games", 0, q=text[:40])
            else:
                self.screen_home(conn, su)

    def on_button(self, conn: sqlite3.Connection, su: sqlite3.Row, data: str, mid: int | None) -> None:
        tg_id, lang = su["tg_id"], su["lang"]
        parts = data.split(":")
        head = parts[0]
        st = self.state.get(tg_id)
        if head == "l" and len(parts) == 2 and parts[1] in ("ru", "tj"):
            conn.execute("UPDATE shop_users SET lang = ? WHERE tg_id = ?", (parts[1], tg_id))
            su = shop_user(conn, tg_id)
            after = (st or {}).get("after_lang")
            self.state.pop(tg_id, None)
            self.open_deep_link(conn, su, after, mid) if after else self.screen_home(conn, su, mid)
        elif head == "lang":
            self.show(tg_id, tr("", "lang_pick"), [[("🇷🇺 Русский", "l:ru"), ("🇹🇯 Тоҷикӣ", "l:tj")]], edit=mid)
        elif head == "h":
            self.state.pop(tg_id, None)
            self.screen_home(conn, su, mid)
        elif head == "g" and len(parts) == 3 and parts[1] in GROUPS and parts[2].isdigit():
            self.screen_games(conn, su, parts[1], int(parts[2]), mid)
        elif head == "hit":
            self.screen_hits(conn, su, mid)
        elif head == "s":
            self.state[tg_id] = {"step": "search"}
            self.show(tg_id, tr(lang, "search_ask"), [[(tr(lang, "home"), "h")]], edit=mid)
        elif head == "c" and len(parts) == 3 and parts[2].isdigit():
            p = product_by_rid(conn, parts[1])
            if p:
                self.screen_packs(conn, su, p["category_id"], int(parts[2]), mid)
        elif head == "p" and len(parts) == 2:
            self.start_product(conn, su, parts[1], mid)
        elif head == "o" and st and st.get("step") == "field" and len(parts) == 3:
            p = product_by_rid(conn, st["rid"])
            try:
                fi, oi = int(parts[1]), int(parts[2])
                spec = p["fields"][fi]
                value = spec["options"][oi]
            except (TypeError, ValueError, IndexError, KeyError):
                return
            if fi != st["fi"]:
                return
            st["fields"][spec["key"]] = str(value)
            st["fi"] += 1
            st["msg"] = mid
            self.next_step(conn, su)
        elif head == "sv" and st and st.get("step") == "field":
            p = product_by_rid(conn, st["rid"])
            spec = p["fields"][st["fi"]] if p and st["fi"] < len(p["fields"]) else None
            saved = saved_values(su).get(p["category_id"], {}).get(spec["key"]) if spec else None
            if saved:
                st["fields"][spec["key"]] = saved
                st["fi"] += 1
                st["msg"] = mid
            self.next_step(conn, su)
        elif head == "q" and st and st.get("step") == "qty" and len(parts) == 2 and parts[1].isdigit():
            st["qty"], st["qty_set"], st["msg"] = int(parts[1]), True, mid
            self.next_step(conn, su)
        elif head == "ok":
            self.buy(conn, su, mid)
        elif head == "x":
            self.state.pop(tg_id, None)
            self.screen_home(conn, su, mid)
        elif head == "b":
            self.screen_balance(conn, su, mid)
        elif head == "hist":
            self.screen_history(conn, su, mid)
        elif head == "t":
            self.screen_methods(conn, su, mid)
        elif head == "tm" and len(parts) == 2:
            self.pick_method(conn, su, parts[1], mid)
        elif head == "ta" and len(parts) == 2 and st and st.get("step") == "amount":
            st["msg"] = mid
            self.create_topup(conn, su, parts[1])
        elif head == "my" and len(parts) == 2 and parts[1].isdigit():
            self.screen_orders(conn, su, int(parts[1]), mid)
        elif head == "od" and len(parts) == 2:
            self.screen_order(conn, su, parts[1], mid)
        elif head == "rp" and len(parts) == 2:
            self.repeat(conn, su, parts[1], mid)
        elif head == "sup":
            from .supportbot import bot_username as support_name
            name = support_name(conn, self.config)
            contact = f"@{name}" if name else _e(self.config.support_contact or self.config.site_name)
            self.show(tg_id, tr(lang, "support_text", contact=contact), [[(tr(lang, "home"), "h")]], edit=mid)
        elif head == "unsub":
            conn.execute("UPDATE shop_users SET subscribed = 0 WHERE tg_id = ?", (tg_id,))
            self.show(tg_id, tr(lang, "unsubbed"), [[(tr(lang, "home"), "h")]], edit=mid)

    # баланс и пополнение
    def screen_balance(self, conn: sqlite3.Connection, su: sqlite3.Row, edit: int | None = None) -> None:
        lang, user = su["lang"], self._user(conn, su)
        rate = tjs_rate(conn, self.config)
        self.show(su["tg_id"], tr(lang, "balance_screen", balance=money(user["balance_micro"], rate)),
                  [[(tr(lang, "topup"), "t", "success")], [(tr(lang, "history"), "hist")],
                   [(tr(lang, "home"), "h")]], edit=edit)

    def screen_history(self, conn: sqlite3.Connection, su: sqlite3.Row, edit: int | None = None) -> None:
        lang = su["lang"]
        rate = tjs_rate(conn, self.config)
        rows = conn.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 10",
                            (su["user_id"],)).fetchall()
        lines = [tr(lang, "hist_title"), ""]
        for t in rows:
            sign = "➕" if t["amount_micro"] > 0 else "➖"
            lines.append(f"{sign} <b>{money(abs(t['amount_micro']), rate)}</b> · {_e(t['note'][:50])}\n"
                         f"    {money(t['balance_before'], rate)} → {money(t['balance_after'], rate)}")
        if not rows:
            lines.append("—")
        self.show(su["tg_id"], "\n".join(lines), [[(tr(lang, "balance"), "b"), (tr(lang, "home"), "h")]], edit=edit)

    def screen_methods(self, conn: sqlite3.Connection, su: sqlite3.Row, edit: int | None = None) -> None:
        tg_id, lang = su["tg_id"], su["lang"]
        waiting = payments.open_request(conn, su["user_id"])
        if waiting is not None:
            self.show(tg_id, tr(lang, "error", text=_e(payments.waiting_text(waiting))),
                      [[(tr(lang, "home"), "h")]], edit=edit)
            return
        methods = payments.methods(conn, self.config)
        if not methods:
            self.show(tg_id, tr(lang, "no_methods"), [[(tr(lang, "home"), "h")]], edit=edit)
            return
        resume = (self.state.get(tg_id) or {}) if (self.state.get(tg_id) or {}).get("resume") else None
        self.state[tg_id] = {"step": "method", "resume": resume}
        rows = [[(m["title"][:40], f"tm:{m['code']}")] for m in methods]
        rows.append([(tr(lang, "home"), "h")])
        self.show(tg_id, tr(lang, "pick_method"), rows, edit=edit)

    def pick_method(self, conn: sqlite3.Connection, su: sqlite3.Row, code: str, edit: int | None) -> None:
        tg_id, lang = su["tg_id"], su["lang"]
        method = next((m for m in payments.methods(conn, self.config) if m["code"] == code), None)
        if method is None:
            self.screen_methods(conn, su, edit)
            return
        prev = self.state.get(tg_id) or {}
        self.state[tg_id] = {"step": "amount", "method": code, "msg": edit, "resume": prev.get("resume")}
        rows = [[(f"{v} смн", f"ta:{v}") for v in (20, 50, 100)], [(f"{v} смн", f"ta:{v}") for v in (200, 500, 1000)],
                [(tr(lang, "cancel"), "x", "danger")]]
        self.show(tg_id, tr(lang, "ask_amount", method=_e(method["title"])), rows, edit=edit)

    def create_topup(self, conn: sqlite3.Connection, su: sqlite3.Row, amount: str) -> None:
        tg_id, lang = su["tg_id"], su["lang"]
        st = self.state.get(tg_id) or {}
        method = st.get("method", "")
        try:
            with db.tx(conn):
                pid = payments.create(conn, self.config, self._user(conn, su), method, "",
                                      "Telegram-бот", amount_tjs=amount.replace(" ", ""))
            payments.start_auto(conn, self.config, pid)
        except payments.PaymentError as exc:
            self.show(tg_id, tr(lang, "error", text=_e(exc)), [[(tr(lang, "topup"), "t")], [(tr(lang, "home"), "h")]],
                      edit=st.get("msg"))
            return
        p = conn.execute("SELECT * FROM payments WHERE id = ?", (pid,)).fetchone()
        view = payments.public(conn, self.config, p)
        amount_text = f"{view['pay_amount']} {view['pay_currency']}"
        rows = [[(tr(lang, "cancel"), "x", "danger")]]
        if p["auto_kind"]:
            if view["pay_url"]:
                rows.insert(0, [("💳 Binance Pay", None, view["pay_url"])])
            text = tr(lang, "pay_auto", id=pid, amount=amount_text, address=_e(view["address"] or view["details"]),
                      note=_e(view["auto_note"]))
            self.state.pop(tg_id, None)
            mid = self.show(tg_id, text, [[(tr(lang, "home"), "h")]] + rows[:-1], edit=st.get("msg"))
            self.watch_add(conn, "pay", pid, tg_id, mid, "pending")
            return
        self.state[tg_id] = {"step": "receipt", "pid": pid, "resume": st.get("resume")}
        text = tr(lang, "pay_details", id=pid, amount=amount_text, method=_e(view["method_title"]),
                  details=_e(view["details"]))
        if view["network_note"]:
            text += f"\n\n⚠️ {_e(view['network_note'])}"
        self.show(tg_id, text, [[(tr(lang, "home"), "h")]], edit=st.get("msg"))

    def on_receipt(self, conn: sqlite3.Connection, su: sqlite3.Row, msg: dict[str, Any]) -> None:
        tg_id, lang = su["tg_id"], su["lang"]
        st = self.state.get(tg_id) or {}
        pid = st.get("pid") if st.get("step") == "receipt" else None
        if pid is None:
            p = conn.execute("SELECT id FROM payments WHERE user_id = ? AND status = 'pending' "
                             "AND receipt_file IS NULL AND COALESCE(auto_kind, '') = '' ORDER BY id DESC LIMIT 1",
                             (su["user_id"],)).fetchone()
            if p is None:
                self.screen_home(conn, su)
                return
            pid = p["id"]
        file_id = (msg["photo"][-1]["file_id"] if msg.get("photo") else (msg.get("document") or {}).get("file_id"))
        try:
            data = self.api.download(file_id, max_bytes=payments.MAX_RECEIPT_BYTES)
        except Exception as exc:  # noqa: BLE001
            self.show(tg_id, tr(lang, "error", text=_e(exc)))
            return
        mid = self.show(tg_id, tr(lang, "checking"))
        try:
            payments.attach_receipt(conn, self.config, su["user_id"], pid, data)
        except payments.PaymentError as exc:
            self.show(tg_id, tr(lang, "error", text=_e(exc)), [[(tr(lang, "home"), "h")]], edit=mid)
            return
        from .tgbot import send_receipt
        try:
            send_receipt(conn, self.config, pid)
        except Exception:  # noqa: BLE001 — чек сохранён, админ увидит его на сайте
            log.exception("бот-магазин: чек %s админу", pid)
        resume = st.get("resume")
        self.state.pop(tg_id, None)
        if resume and resume.get("rid"):
            self.state[tg_id] = {**resume, "msg": None, "resume": None, "after_pay": True}
        self.watch_add(conn, "pay", pid, tg_id, mid, "pending")

    # заказы
    def screen_orders(self, conn: sqlite3.Connection, su: sqlite3.Row, page: int, edit: int | None = None) -> None:
        lang = su["lang"]
        rows_db = conn.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 8 OFFSET ?",
                               (su["user_id"], page * 8)).fetchall()
        if not rows_db and page == 0:
            self.show(su["tg_id"], tr(lang, "no_orders"), [[(tr(lang, "games"), "g:games:0")],
                                                          [(tr(lang, "home"), "h")]], edit=edit)
            return
        rows = []
        for o in rows_db:
            status = orders.client_status(o["status"])
            icon = {"completed": "✅", "failed": "❌"}.get(status, "⏳")
            rows.append([(f"{icon} {o['public_id']} · {o['product_name'][:28]}", f"od:{o['public_id']}")])
        nav = []
        if page > 0:
            nav.append(("‹", f"my:{page - 1}"))
        if len(rows_db) == 8:
            nav.append((tr(lang, "more"), f"my:{page + 1}"))
        if nav:
            rows.append(nav)
        rows.append([(tr(lang, "home"), "h")])
        self.show(su["tg_id"], tr(lang, "orders_title"), rows, edit=edit)

    def order_text(self, conn: sqlite3.Connection, lang: str, o: sqlite3.Row) -> str:
        rate = tjs_rate(conn, self.config)
        status = orders.client_status(o["status"])
        if status == "completed":
            return tr(lang, "done", id=o["public_id"], product=_e(o["product_name"])) + delivery_text(o)
        if status == "failed":
            return tr(lang, "failed", id=o["public_id"], product=_e(o["product_name"]),
                      reason=_e(o["error"] or ""), total=money(o["total_micro"], rate))
        return tr(lang, "created", id=o["public_id"], product=_e(o["product_name"]),
                  total=money(o["total_micro"], rate))

    def screen_order(self, conn: sqlite3.Connection, su: sqlite3.Row, public_id: str, edit: int | None) -> None:
        lang = su["lang"]
        o = orders.find_user_order(conn, su["user_id"], public_id)
        if o is None:
            self.screen_orders(conn, su, 0, edit)
            return
        rows = [[(tr(lang, "repeat"), f"rp:{o['public_id']}", "success")],
                [(tr(lang, "orders"), "my:0"), (tr(lang, "home"), "h")]]
        self.show(su["tg_id"], self.order_text(conn, lang, o), rows, edit=edit)

    def repeat(self, conn: sqlite3.Connection, su: sqlite3.Row, public_id: str, edit: int | None) -> None:
        """«Повторить»: тот же товар и те же данные — сразу экран подтверждения."""
        o = orders.find_user_order(conn, su["user_id"], public_id)
        row = conn.execute("SELECT rowid AS rid FROM products WHERE id = ?",
                           (o["product_id"],)).fetchone() if o else None
        if row is None or get_product(conn, o["product_id"]) is None:
            self.screen_home(conn, su, edit)
            return
        p = get_product(conn, o["product_id"])
        self.state[su["tg_id"]] = {"step": "field", "rid": row["rid"], "fields": json.loads(o["fields_json"] or "{}"),
                                   "fi": len(p["fields"]), "qty": o["quantity"], "qty_set": True, "msg": edit,
                                   "nonce": secrets.token_hex(6)}
        self.next_step(conn, su)

    # статусы: бот сам пишет, когда заказ готов и баланс пополнен
    def watch_add(self, conn: sqlite3.Connection, kind: str, obj_id: int, chat: int, mid: int | None,
                  status: str) -> None:
        conn.execute("INSERT INTO shop_watch (kind, obj_id, chat_id, message_id, last_status, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?)", (kind, obj_id, chat, mid, status, db.now()))

    def watch(self, conn: sqlite3.Connection, force: bool = False) -> int:
        now = time.monotonic()
        if not force and now - self._last_watch < WATCH_EVERY:
            return 0
        self._last_watch = now
        done = 0
        rows = conn.execute("SELECT w.*, s.lang, s.user_id FROM shop_watch w JOIN shop_users s ON s.tg_id = w.chat_id "
                            "ORDER BY w.id LIMIT 100").fetchall()
        for w in rows:
            if w["kind"] == "order":
                o = conn.execute("SELECT * FROM orders WHERE id = ?", (w["obj_id"],)).fetchone()
                status = orders.client_status(o["status"]) if o else "failed"
                if o is None or status not in ("completed", "failed"):
                    if w["created_at"] < _ago(3 * 86400):
                        conn.execute("DELETE FROM shop_watch WHERE id = ?", (w["id"],))
                    continue
                rows_kb = [[(tr(w["lang"], "repeat"), f"rp:{o['public_id']}", "success")],
                           [(tr(w["lang"], "home"), "h")]]
                self.show(w["chat_id"], self.order_text(conn, w["lang"], o), rows_kb)
            else:
                p = conn.execute("SELECT * FROM payments WHERE id = ?", (w["obj_id"],)).fetchone()
                if p is None or p["status"] == "pending":
                    if p is None or w["created_at"] < _ago(3 * 86400):
                        conn.execute("DELETE FROM shop_watch WHERE id = ?", (w["id"],))
                    continue
                self.payment_result(conn, w, p)
            conn.execute("DELETE FROM shop_watch WHERE id = ?", (w["id"],))
            done += 1
        return done

    def payment_result(self, conn: sqlite3.Connection, w: sqlite3.Row, p: sqlite3.Row) -> None:
        lang, chat = w["lang"], w["chat_id"]
        rate = tjs_rate(conn, self.config)
        if p["status"] != "paid":
            self.show(chat, tr(lang, "rejected", id=p["id"], reason=_e(p["admin_note"] or "")),
                      [[(tr(lang, "topup"), "t"), (tr(lang, "home"), "h")]])
            return
        user = accounts.get_user(conn, w["user_id"])
        self.show(chat, tr(lang, "paid", amount=money(p["amount_micro"], rate),
                           balance=money(user["balance_micro"], rate)), [[(tr(lang, "home"), "h")]])
        st = self.state.get(chat) or {}
        if st.get("after_pay"):   # пополнял, чтобы купить, — сразу к подтверждению заказа
            su = shop_user(conn, chat)
            st["after_pay"] = False
            st["msg"] = None
            p_ = product_by_rid(conn, st.get("rid"))
            if p_:
                self.screen_confirm(conn, su, p_)


def _group_of(kind: str) -> str:
    return next((g for g, ks in GROUPS.items() if kind in ks), "games")


def _ago(seconds: int) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%S")

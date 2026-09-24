"""Telegram-бот для админа: заявки и проблемы приходят с кнопками, ответ — одним нажатием.

Работает через long polling (getUpdates) в отдельном потоке — вебхук и открытый порт не нужны.
Слушается только чат из DONATIX_ALERT_TELEGRAM_CHAT_ID; сообщения из других чатов игнорируются."""

from __future__ import annotations

import html
import logging
import sqlite3
import threading
from typing import Any, Callable

import httpx

from . import accounts, db, orders, payments
from .config import PAY_METHODS, Config
from .money import fmt
from .notify import notify

log = logging.getLogger(__name__)

Buttons = list[list[tuple[str, str]]]  # ряды кнопок: (текст, callback_data)

MENU = [["📊 Сводка", "💳 Заявки"], ["👥 Новые партнёры", "⚠️ Проблемные заказы"]]


def keyboard(buttons: Buttons | None) -> dict[str, Any] | None:
    if not buttons:
        return None
    return {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]}


class TelegramApi:
    def __init__(self, token: str, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(base_url=f"https://api.telegram.org/bot{token}/", timeout=40,
                                    transport=transport)

    def __call__(self, method: str, **payload: Any) -> Any:
        payload = {k: v for k, v in payload.items() if v is not None}
        resp = self._client.post(method, json=payload)
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"telegram {method}: {data.get('description')}")
        return data.get("result")


# ── События, которые бот присылает сам ─────────────────────────


def payment_event(conn: sqlite3.Connection, payment_id: int, config: Config | None = None) -> tuple[str, Buttons]:
    p = conn.execute("SELECT p.*, u.login FROM payments p JOIN users u ON u.id = p.user_id WHERE p.id = ?",
                     (payment_id,)).fetchone()
    title = payments.title_for(conn, config, p["method"]) if config else PAY_METHODS.get(p["method"], (p["method"],))[0]
    text = (f"💳 <b>Заявка на пополнение #{p['id']}</b>\n"
            f"Клиент: {_e(p['login'])}\nСпособ: {_e(title)}\n"
            f"К переводу: <b>{_e(p['pay_amount'])} {_e(p['pay_currency'])}</b> (${fmt(p['amount_micro'])})"
            + (f"\nЧек / хэш: <code>{_e(p['reference'])}</code>" if p["reference"] else ""))
    return text, [[(f"✅ Зачислить ${fmt(p['amount_micro'])}", f"pay:ok:{p['id']}"),
                   ("❌ Отклонить", f"pay:no:{p['id']}")]]


def user_event(conn: sqlite3.Connection, user_id: int) -> tuple[str, Buttons]:
    u = accounts.get_user(conn, user_id)
    text = (f"🆕 <b>Новый партнёр</b>\n{_e(u['login'])} · {_e(u['email'])}"
            + (f"\nПроект: {_e(u['project'])}" if u["project"] else ""))
    return text, [[("✅ Одобрить", f"user:ok:{u['id']}"), ("⛔ Заблокировать", f"user:block:{u['id']}")]]


def order_event(conn: sqlite3.Connection, order_id: int) -> tuple[str, Buttons]:
    o = conn.execute("SELECT o.*, u.login FROM orders o JOIN users u ON u.id = o.user_id WHERE o.id = ?",
                     (order_id,)).fetchone()
    text = (f"⚠️ <b>Заказ {_e(o['public_id'])} требует внимания</b>\n"
            f"{_e(o['product_name'])} · ${fmt(o['total_micro'])} · клиент {_e(o['login'])}\n"
            f"{_e(o['error'] or 'Поставщик не подтвердил результат — проверьте заказ в панели FazerCards.')}")
    rows: Buttons = [[("💸 Вернуть деньги", f"ord:refund:{o['id']}"), ("✅ Выполнен", f"ord:done:{o['id']}")]]
    if o["supplier_order_id"]:
        rows.insert(0, [("🔄 Проверить у поставщика", f"ord:check:{o['id']}")])
    return text, rows


def summary(conn: sqlite3.Connection) -> str:
    from .worker import supplier_balance_cached

    def one(sql: str) -> int:
        return conn.execute(sql).fetchone()[0]

    today, month = orders.stats(conn, 1), orders.stats(conn, 30)
    bal = supplier_balance_cached(conn)
    owed = one("SELECT COALESCE(SUM(balance_micro), 0) FROM users WHERE role = 'client'")
    pays = one("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
    users = one("SELECT COUNT(*) FROM users WHERE status = 'pending'")
    problems = one("SELECT COUNT(*) FROM orders WHERE status = 'attention'")
    return (
        "📊 <b>Сводка</b>\n"
        f"Баланс FazerCards: <b>{'$' + str(bal) if bal is not None else '—'}</b>\n"
        f"Балансы клиентов: ${fmt(owed)}\n\n"
        f"Сегодня: {today['orders']} заказов, прибыль ${fmt(today['profit'])}\n"
        f"30 дней: {month['orders']} заказов, выручка ${fmt(month['revenue'])}, прибыль ${fmt(month['profit'])}\n\n"
        f"Заявок на пополнение: {pays}\nНовых партнёров: {users}\nПроблемных заказов: {problems}"
    )


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


# ── Обработка входящих ──────────────────────────────────────


class AdminBot:
    def __init__(self, config: Config, api: Callable[..., Any] | None = None):
        self.config = config
        self.chat_id = str(config.alert_telegram_chat_id).strip()
        self.api = api or TelegramApi(config.alert_telegram_token)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # отправка
    def send(self, text: str, buttons: Buttons | None = None, **extra: Any) -> None:
        self.api("sendMessage", chat_id=self.chat_id, text=text, parse_mode="HTML",
                 reply_markup=keyboard(buttons) or extra.get("reply_markup"), disable_web_page_preview=True)

    # цикл
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="donatix-tgbot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        conn = db.connect(self.config.db_path)
        offset = int(db.get_setting(conn, "tg_offset", "0") or 0)
        try:
            self.api("setMyCommands", commands=[
                {"command": "start", "description": "Меню"}, {"command": "stats", "description": "Сводка"},
                {"command": "payments", "description": "Заявки на пополнение"},
                {"command": "users", "description": "Новые партнёры"},
                {"command": "orders", "description": "Проблемные заказы"}])
        except Exception as exc:  # бот может быть ещё не настроен — не мешаем сайту
            log.warning("telegram-бот: %s", exc)
        try:
            while not self._stop.is_set():
                try:
                    updates = self.api("getUpdates", offset=offset, timeout=25,
                                       allowed_updates=["message", "callback_query"]) or []
                except Exception as exc:
                    log.warning("telegram-бот: %s", exc)
                    self._stop.wait(10)
                    continue
                for upd in updates:
                    offset = max(offset, int(upd["update_id"]) + 1)
                    try:
                        self.handle(conn, upd)
                    except Exception:
                        log.exception("telegram-бот: обработка %s", upd.get("update_id"))
                db.set_setting(conn, "tg_offset", str(offset))
        finally:
            conn.close()

    def handle(self, conn: sqlite3.Connection, upd: dict[str, Any]) -> None:
        if "callback_query" in upd:
            cq = upd["callback_query"]
            msg = cq.get("message") or {}
            if str((msg.get("chat") or {}).get("id")) != self.chat_id:
                self.api("answerCallbackQuery", callback_query_id=cq["id"], text="Нет доступа")
                return
            result = self.on_button(conn, str(cq.get("data") or ""))
            self.api("answerCallbackQuery", callback_query_id=cq["id"], text=result[:190])
            if msg.get("message_id"):
                # Кнопки убираем, а под сообщением пишем, что сделано — видно в истории чата
                self.api("editMessageText", chat_id=self.chat_id, message_id=msg["message_id"], parse_mode="HTML",
                         text=f"{_e(msg.get('text', ''))}\n\n<b>{_e(result)}</b>", disable_web_page_preview=True)
            return
        msg = upd.get("message") or {}
        if str((msg.get("chat") or {}).get("id")) != self.chat_id:
            return
        self.on_command(conn, (msg.get("text") or "").strip())

    def on_command(self, conn: sqlite3.Connection, text: str) -> None:
        cmd = text.split("@")[0].split()[0].lower() if text else ""
        if cmd in ("/stats", "📊"):
            self.send(summary(conn))
        elif cmd in ("/payments", "💳"):
            rows = conn.execute("SELECT id FROM payments WHERE status = 'pending' ORDER BY id LIMIT 10").fetchall()
            self._list(conn, rows, lambda c, i: payment_event(c, i, self.config), "Заявок на пополнение нет.")
        elif cmd in ("/users", "👥"):
            rows = conn.execute("SELECT id FROM users WHERE status = 'pending' ORDER BY id LIMIT 10").fetchall()
            self._list(conn, rows, user_event, "Новых партнёров нет.")
        elif cmd in ("/orders", "⚠️"):
            rows = conn.execute("SELECT id FROM orders WHERE status = 'attention' ORDER BY id LIMIT 10").fetchall()
            self._list(conn, rows, order_event, "Проблемных заказов нет.")
        else:
            self.send(f"Бот админки {_e(self.config.site_name)}. Сюда приходят заявки и проблемы — "
                      "отвечайте кнопками под сообщением.",
                      reply_markup={"keyboard": [[{"text": t} for t in row] for row in MENU], "resize_keyboard": True})

    def _list(self, conn, rows, make, empty: str) -> None:
        if not rows:
            self.send(empty)
        for r in rows:
            self.send(*make(conn, r["id"]))

    def on_button(self, conn: sqlite3.Connection, data: str) -> str:
        try:
            what, action, raw_id = data.split(":")
            obj_id = int(raw_id)
        except ValueError:
            return "Неизвестная кнопка"
        admin_id = _admin_id(conn)
        if what == "pay":
            if action == "ok":
                ok = payments.confirm(conn, self.config, obj_id, admin_id)
                return "Зачислено, клиент получил уведомление" if ok else "Заявка уже обработана"
            ok = payments.reject(conn, self.config, obj_id, admin_id, "Перевод не найден")
            return "Отклонено" if ok else "Заявка уже обработана"
        if what == "user":
            u = accounts.get_user(conn, obj_id)
            if u is None or u["role"] == "admin":
                return "Нельзя"
            status = "active" if action == "ok" else "blocked"
            accounts.update_user_admin(conn, obj_id, status=status, tier=u["tier"],
                                       markup_override=str(u["markup_override"] or ""))
            if status == "active" and u["status"] != "active":
                notify(conn, self.config, obj_id, "Аккаунт активирован — можно пополнять баланс и делать заказы.",
                       "/panel")
            return "Одобрен" if status == "active" else "Заблокирован"
        if what == "ord":
            if action == "refund":
                ok = orders.fail_and_refund(conn, obj_id, "Отменён администратором", by_admin=admin_id)
                return "Деньги возвращены клиенту" if ok else "Заказ уже закрыт"
            if action == "done":
                return "Отмечен выполненным" if orders.admin_complete(conn, obj_id, "") else "Заказ уже закрыт"
            if action == "check":
                orders.admin_recheck(conn, obj_id)
                return "Проверим у поставщика в ближайшую минуту"
        return "Неизвестная кнопка"


def _admin_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT id FROM users WHERE role = 'admin' ORDER BY id LIMIT 1").fetchone()
    return int(row["id"]) if row else 0

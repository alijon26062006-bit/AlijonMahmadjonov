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
from .config import PAY_METHODS, TIERS, Config
from .money import fmt
from .notify import notify

log = logging.getLogger(__name__)

Buttons = list[list[tuple[str, str]]]  # ряды кнопок: (текст, callback_data)

MENU = [["🏠 Меню", "📊 Сводка"], ["💳 Заявки", "👥 Новые партнёры"], ["⚠️ Проблемные заказы"]]
Screen = tuple[str, "Buttons"]  # экран: текст и кнопки — правится в том же сообщении


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
    def __init__(self, config: Config, api: Callable[..., Any] | None = None, supplier: Any = None):
        self.config = config
        self.supplier = supplier
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
                {"command": "start", "description": "Меню"}, {"command": "menu", "description": "Все разделы"},
                {"command": "stats", "description": "Сводка"},
                {"command": "payments", "description": "Заявки на пополнение"},
                {"command": "users", "description": "Новые партнёры"},
                {"command": "orders", "description": "Проблемные заказы"},
                {"command": "client", "description": "Клиент по логину: /client login"}])
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
            if isinstance(result, tuple):  # экран меню — правим то же сообщение
                self.api("answerCallbackQuery", callback_query_id=cq["id"])
                text, buttons = result
                if msg.get("message_id") and "text" in msg:
                    try:
                        self.api("editMessageText", chat_id=self.chat_id, message_id=msg["message_id"],
                                 parse_mode="HTML", text=text, reply_markup=keyboard(buttons),
                                 disable_web_page_preview=True)
                    except RuntimeError as exc:
                        if "not modified" not in str(exc):
                            raise
                else:
                    self.send(text, buttons)
                return
            self.api("answerCallbackQuery", callback_query_id=cq["id"], text=result[:190])
            if msg.get("message_id"):
                # Кнопки убираем, а под сообщением пишем, что сделано — видно в истории чата.
                # У сообщения с чеком (фото/файл) вместо текста — подпись.
                if "text" in msg:
                    self.api("editMessageText", chat_id=self.chat_id, message_id=msg["message_id"], parse_mode="HTML",
                             text=f"{_e(msg.get('text', ''))}\n\n<b>{_e(result)}</b>", disable_web_page_preview=True)
                else:
                    self.api("editMessageCaption", chat_id=self.chat_id, message_id=msg["message_id"],
                             parse_mode="HTML", caption=f"{_e(msg.get('caption', ''))}\n\n<b>{_e(result)}</b>"[:1000])
            return
        msg = upd.get("message") or {}
        if str((msg.get("chat") or {}).get("id")) != self.chat_id:
            return
        self.on_command(conn, (msg.get("text") or "").strip())

    def on_command(self, conn: sqlite3.Connection, text: str) -> None:
        cmd = text.split("@")[0].split()[0].lower() if text else ""
        if cmd in ("/menu", "🏠"):
            self.send(*screen_home(conn, self.config))
        elif cmd == "/client":
            login = text.split(maxsplit=1)[1].strip() if len(text.split()) > 1 else ""
            u = conn.execute("SELECT id FROM users WHERE login = ? OR email = ?", (login, login)).fetchone()
            self.send(*screen_client(conn, self.config, u["id"]) if u else ("Клиент не найден. Пример: /client shop1",
                                                                            [[("👤 Клиенты", "m:clients:0")]]))
        elif cmd in ("/stats", "📊"):
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
                      "отвечайте кнопками под сообщением. Всё остальное — в «🏠 Меню».",
                      reply_markup={"keyboard": [[{"text": t} for t in row] for row in MENU], "resize_keyboard": True})
            self.send(*screen_home(conn, self.config))

    def _list(self, conn, rows, make, empty: str) -> None:
        if not rows:
            self.send(empty)
        for r in rows:
            self.send(*make(conn, r["id"]))

    def on_button(self, conn: sqlite3.Connection, data: str) -> str | Screen:
        try:
            what, action, raw_id = data.split(":")
            obj_id = int(raw_id)
        except ValueError:
            return "Неизвестная кнопка"
        if what in MENU_HANDLERS:
            return MENU_HANDLERS[what](self, conn, action, obj_id)
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


def send_receipt(conn: sqlite3.Connection, config: Config, payment_id: int) -> None:
    """Заявка с приложенным чеком — админу фото/файлом с кнопками «Зачислить / Отклонить»."""
    from .payments import receipts_dir
    from .worker import notify_admin_file
    p = conn.execute("SELECT receipt_file FROM payments WHERE id = ?", (payment_id,)).fetchone()
    if not p or not p["receipt_file"]:
        return
    text, buttons = payment_event(conn, payment_id, config)
    path = receipts_dir(config) / p["receipt_file"]
    notify_admin_file(config, text + "\n🧾 Чек приложен", buttons, path, photo=not p["receipt_file"].endswith(".pdf"))


# ── Меню админа: все разделы сайта кнопками ────────────────


def _dot(b: dict) -> str:
    return "🟢 " if b.get("running") else ("🟡 " if b["enabled"] else "⚪ ")


def _back(to: str = "m:home:0") -> list[tuple[str, str]]:
    return [("‹ Назад", to)]


def screen_home(conn: sqlite3.Connection, config: Config) -> Screen:
    def one(sql: str) -> int:
        return conn.execute(sql).fetchone()[0]
    pays = one("SELECT COUNT(*) FROM payments WHERE status = 'pending'")
    users = one("SELECT COUNT(*) FROM users WHERE status = 'pending'")
    probs = one("SELECT COUNT(*) FROM orders WHERE status = 'attention'")
    return (f"🏠 <b>Админка {_e(config.site_name)}</b>\nВсё управление сайтом и ботами — здесь.", [
        [("📊 Сводка", "m:stats:0"), (f"💳 Заявки · {pays}", "m:pays:0")],
        [(f"👥 Новые · {users}", "m:users:0"), (f"⚠️ Проблемы · {probs}", "m:orders:0")],
        [("👤 Клиенты", "m:clients:0"), ("🤖 Боты клиентов", "m:bots:0")],
        [("💱 Курс", "m:rate:0"), ("🔄 Каталог", "m:cat:0")],
        [("⚙️ Настройки", "m:set:0")],
    ])


def screen_client(conn: sqlite3.Connection, config: Config, user_id: int) -> Screen:
    u = accounts.get_user(conn, user_id)
    if u is None:
        return "Клиент не найден.", [_back("m:clients:0")]
    n_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,)).fetchone()[0]
    n_bots = conn.execute("SELECT COUNT(*) FROM bots WHERE user_id = ?", (user_id,)).fetchone()[0]
    status = {"active": "✅ активен", "pending": "⏳ на проверке", "blocked": "⛔ заблокирован"}[u["status"]]
    markup = accounts.markup_for(u, config)
    text = (f"👤 <b>{_e(u['login'])}</b> · {_e(u['email'])}\n"
            + (f"Проект: {_e(u['project'])}\n" if u["project"] else "")
            + f"Статус: {status}\nБаланс: <b>${fmt(u['balance_micro'])}</b>\n"
            f"Уровень: {u['tier']} · наценка {markup}%\nЗаказов: {n_orders} · ботов: {n_bots}")
    rows: Buttons = []
    if u["role"] != "admin":
        rows.append([("⛔ Заблокировать", f"cl:block:{user_id}") if u["status"] == "active"
                     else ("✅ Активировать", f"cl:ok:{user_id}")])
        rows.append([(("• " if u["tier"] == t else "") + t, f"cl:{t}:{user_id}") for t in TIERS])
    rows.append(_back("m:clients:0"))
    return text, rows


def screen_bot(conn: sqlite3.Connection, bot_id: int) -> Screen:
    from . import bots
    b = next((x for x in bots.listing(conn) if x["id"] == bot_id), None)
    if b is None:
        return "Бот удалён.", [_back("m:bots:0")]
    state = "🟢 работает" if b.get("running") else ("🟡 запускается" if b["enabled"] else "⚪ остановлен")
    text = (f"🤖 <b>@{_e(b['username'])}</b>\n{state}\nКлиент: {_e(b['login'])} · баланс ${fmt(b['balance_micro'])}\n"
            f"Админы бота: <code>{_e(b['admin_ids'])}</code>"
            + ("\n⚠️ Токен запущен ещё где-то — бот отвечает дважды" if b.get("conflict") else ""))
    rows: Buttons = [[("🔁 Перезапустить", f"bot:restart:{bot_id}"), ("⏸ Остановить", f"bot:stop:{bot_id}")]
                     if b["enabled"] else [("▶️ Запустить", f"bot:start:{bot_id}")]]
    rows.append(_back("m:bots:0"))
    return text, rows


def screen_rate(conn: sqlite3.Connection, config: Config) -> Screen:
    from . import rates
    st = rates.status(conn, config)
    conf = payments.settings(conn, config)
    age = f"{st['age_seconds'] // 60} мин назад" if st["age_seconds"] is not None else "ещё не обновлялся"
    text = (f"💱 <b>Курс: 1 $ = {conf['tjs_rate']} сомони</b>\n"
            + (f"Рынок {st['market']} + запас {st['margin_pct']}% · {_e(st['source'])} · {age}\n"
               if st["auto"] and st["market"] else "")
            + ("Автообновление: ✅ каждые 5 минут" if st["auto"] else "Автообновление: ⛔ курс вручную (в веб-админке)")
            + (f"\n⚠️ {_e(st['error'][:200])}" if st["auto"] and st["error"] else ""))
    return text, [
        [("🔄 Обновить сейчас", "rate:refresh:0"), ("⛔ Выключить авто" if st["auto"] else "✅ Включить авто",
                                                  "rate:auto:0")],
        [("Запас −0.5%", "rate:margin:-5"), ("Запас +0.5%", "rate:margin:5")],
        _back(),
    ]


def screen_settings(conn: sqlite3.Connection, config: Config) -> Screen:
    from . import sitecfg
    v = sitecfg.view(conn, config)
    on = {True: "✅", False: "⛔"}
    text = ("⚙️ <b>Настройки</b>\n"
            "Наценка: " + " · ".join(f"{t} {v['markups'][t]}%" for t in TIERS) + "\n"
            f"Регистрация: {on[v['reg_open']]} · проверка новых: {on[v['require_approval']]}\n"
            f"Конструктор для клиентов: {on[v['client_bots']]} · до {v['max_bots']} ботов\n"
            f"Поддержка: {_e(v['support'] or '—')}")
    rows: Buttons = [[(f"{t} −0.5%", f"mk:{t}:-5"), (f"{t} +0.5%", f"mk:{t}:5")] for t in TIERS]
    rows += [
        [(f"{on[v['reg_open']]} Регистрация", "set:reg_open:0"),
         (f"{on[v['require_approval']]} Проверка новых", "set:require_approval:0")],
        [(f"{on[v['client_bots']]} Конструктор клиентам", "set:client_bots:0")],
        _back(),
    ]
    return text, rows


def _menu(bot: AdminBot, conn: sqlite3.Connection, action: str, _: int) -> str | Screen:
    cfg = bot.config
    if action == "home":
        return screen_home(conn, cfg)
    if action == "stats":
        return summary(conn), [_back()]
    if action in ("pays", "users", "orders"):
        bot.on_command(conn, {"pays": "/payments", "users": "/users", "orders": "/orders"}[action])
        return screen_home(conn, cfg)
    if action == "clients":
        rows = conn.execute("SELECT id, login, balance_micro, status FROM users WHERE role = 'client' "
                            "ORDER BY balance_micro DESC, id DESC LIMIT 12").fetchall()
        mark = {"active": "", "pending": "⏳ ", "blocked": "⛔ "}
        return ("👤 <b>Клиенты</b> — по балансу. Найти любого: <code>/client логин</code>",
                [[(f"{mark[r['status']]}{r['login']} · ${fmt(r['balance_micro'])}", f"cl:view:{r['id']}")]
                 for r in rows] + [_back()])
    if action == "bots":
        from . import bots
        items = bots.listing(conn)
        return (f"🤖 <b>Боты клиентов</b> — {len(items)}" if items else "🤖 Ботов пока нет.",
                [[(_dot(b) + f"@{b['username']} · {b['login']}", f"bot:view:{b['id']}")] for b in items[:15]]
                + [_back()])
    if action == "rate":
        return screen_rate(conn, cfg)
    if action == "cat":
        from . import catalog_job
        st = catalog_job.status()
        synced = db.get_setting(conn, "catalog_synced_at") or "—"
        n = conn.execute("SELECT COUNT(*) FROM products WHERE active = 1").fetchone()[0]
        state = ("⏳ идёт загрузка…" if st.get("running") else
                 f"последняя: {_e(synced[:16].replace('T', ' '))} UTC")
        return (f"🔄 <b>Каталог</b>\nТоваров: {n}\nЗагрузка: {state}",
                [[("🔄 Обновить каталог", "cat:sync:0"), ("🖼 + картинки", "cat:all:0")], _back()])
    if action == "set":
        return screen_settings(conn, cfg)
    return "Неизвестная кнопка"


def _client(bot: AdminBot, conn: sqlite3.Connection, action: str, user_id: int) -> str | Screen:
    u = accounts.get_user(conn, user_id)
    if u is None:
        return "Клиент не найден"
    if action != "view" and u["role"] != "admin":
        status, tier = u["status"], u["tier"]
        if action in ("ok", "block"):
            status = "active" if action == "ok" else "blocked"
        elif action in TIERS:
            tier = action
        accounts.update_user_admin(conn, user_id, status=status, tier=tier,
                                   markup_override=str(u["markup_override"] or ""))
        if status == "active" and u["status"] != "active":
            notify(conn, bot.config, user_id, "Аккаунт активирован — можно пополнять баланс и делать заказы.", "/panel")
    return screen_client(conn, bot.config, user_id)


def _bot(bot: AdminBot, conn: sqlite3.Connection, action: str, bot_id: int) -> str | Screen:
    from . import bots
    if action in ("stop", "start", "restart"):
        bots.set_enabled(conn, bot_id, action != "stop")
        if bots.RUNNER:
            bots.RUNNER.poke()
    return screen_bot(conn, bot_id)


def _rate(bot: AdminBot, conn: sqlite3.Connection, action: str, value: int) -> str | Screen:
    from decimal import Decimal

    from . import rates
    cfg = bot.config
    if action == "refresh":
        if not rates.auto_enabled(conn, cfg):
            return "Сначала включите автообновление"
        rates.reset()
        rates.refresh(conn, cfg, force=True)
    elif action == "auto":
        db.set_setting(conn, "pay.rate_auto", "0" if rates.auto_enabled(conn, cfg) else "1")
        if rates.auto_enabled(conn, cfg):
            rates.reset()
            rates.refresh(conn, cfg, force=True)
    elif action == "margin":
        margin = max(Decimal("-5"), min(Decimal("20"), rates.margin_pct(conn, cfg) + Decimal(value) / 10))
        db.set_setting(conn, "pay.rate_margin_pct", str(margin))
        market = db.get_setting(conn, "pay.rate_market")
        if rates.auto_enabled(conn, cfg) and market:
            db.set_setting(conn, "pay.tjs_rate", str(rates.apply_margin(Decimal(market), margin)))
    return screen_rate(conn, cfg)


def _catalog(bot: AdminBot, conn: sqlite3.Connection, action: str, _: int) -> str | Screen:
    from . import catalog_job
    if bot.supplier is None:
        return "Каталог обновляется только из веб-админки"
    started = catalog_job.start(bot.config, bot.supplier, sync=True, images=action == "all")
    text, rows = _menu(bot, conn, "cat", 0)
    return (text + ("\n\n✅ Запустил. Статус — снова кнопкой «🔄 Каталог»." if started else "\n\nУже идёт.")), rows


def _setting(bot: AdminBot, conn: sqlite3.Connection, key: str, _: int) -> str | Screen:
    from . import sitecfg
    if key in ("reg_open", "require_approval", "client_bots"):
        sitecfg.toggle(conn, bot.config, key)
    return screen_settings(conn, bot.config)


def _markup(bot: AdminBot, conn: sqlite3.Connection, tier: str, delta: int) -> str | Screen:
    from decimal import Decimal

    from . import sitecfg
    if tier in TIERS:
        sitecfg.bump_markup(conn, bot.config, tier, Decimal(delta) / 10)
    return screen_settings(conn, bot.config)


MENU_HANDLERS: dict[str, Callable[..., str | Screen]] = {
    "m": _menu, "cl": _client, "bot": _bot, "rate": _rate, "cat": _catalog, "set": _setting, "mk": _markup,
}

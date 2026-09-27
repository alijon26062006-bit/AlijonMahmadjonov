"""Бот поддержки клиентов Donatix с AI (OpenAI).

Клиент пишет в Telegram: «заказ не пришёл», «почему не пополнился баланс». AI:
1) узнаёт клиента только через личный кабинет: «Поддержка в Telegram» → кнопка
   «Открыть бота» (или код DX-XXXXXXXX с той страницы) — и Telegram привязан к аккаунту;
2) спрашивает номер заказа (dx-…) или заявки на пополнение (#N), сам смотрит,
   что с ними, и отвечает на языке клиента — по-таджикски или по-русски;
3) не может решить сам — передаёт обращение админу, ответ админа приходит клиенту
   в этот же чат.

Что AI видит: только то, что отдают функции ниже, и только по своему аккаунту.
Поставщик, закупочные цены, наценки, служебные ошибки и чужие данные в эти
функции не попадают — поэтому AI не может их выдать, даже если его попросят.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from . import accounts, db
from .config import Config
from .money import fmt

log = logging.getLogger(__name__)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
PROMPT_FILE = Path(__file__).with_name("support_prompt.txt")   # инструкции для AI — править можно без кода
HISTORY_TURNS = 16            # сколько последних сообщений помнит бот
MAX_TOOL_ROUNDS = 6           # шагов «спросил базу → подумал» на один ответ
MSG_LIMIT = (20, 600)         # не больше 20 сообщений за 10 минут от одного человека
MAX_INPUT = 1500

_ORDER = re.compile(r"(dx-[0-9a-f-]{6,})", re.I)
_TOKEN = re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b")


# ─────────────────────────────────────────── данные для AI (только своё и без внутренностей)


def _linked_user(conn: sqlite3.Connection, tg_id: int) -> sqlite3.Row | None:
    row = conn.execute("SELECT user_id FROM support_links WHERE tg_id = ?", (tg_id,)).fetchone()
    return accounts.get_user(conn, row["user_id"]) if row else None


def _order_reason(error: str | None) -> str:
    """Причина неудачи — категорией, без текста поставщика и служебных подробностей."""
    text = (error or "").lower()
    if any(w in text for w in ("player", "игрок", "user id", "uid", "invalid id", "not found user", "аккаунт",
                               "username", "account")):
        return "wrong_recipient"          # неверный ID игрока / @username
    if any(w in text for w in ("balance", "баланс", "insufficient", "stock", "недоступ", "unavailable",
                               "out of", "нет в наличии")):
        return "temporarily_unavailable"  # товар временно недоступен
    if any(w in text for w in ("region", "регион", "country", "стран")):
        return "wrong_region"
    return "not_completed"


def _minutes_since(ts: str | None) -> int | None:
    if not ts:
        return None
    try:
        dt = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return int((datetime.now(timezone.utc) - dt).total_seconds() // 60)


def _order_for_ai(o: sqlite3.Row) -> dict[str, Any]:
    from .deps import _pack_title
    from .orders import client_status
    status = client_status(o["status"])
    fields = json.loads(o["fields_json"] or "{}")
    refunded = status == "failed"
    return {
        "order_id": o["public_id"],
        "status": {"processing": "в обработке", "completed": "выполнен", "failed": "не выполнен"}.get(status, status),
        "product": _pack_title(o["product_name"], o["kind"]),
        "quantity": o["quantity"],
        "recipient": fields,
        "price_usd": fmt(o["total_micro"]),
        "created_at_utc": o["created_at"][:16].replace("T", " "),
        "minutes_since_created": _minutes_since(o["created_at"]),
        "money_returned_to_balance": refunded,
        "failure_reason": _order_reason(o["error"]) if refunded else None,
        "has_code_or_key": bool(o["delivery_json"]) and o["kind"] in ("gift_card", "game_key") and
        status == "completed",
        "page": f"/panel/orders/{o['public_id']}",
    }


def _payment_for_ai(conn: sqlite3.Connection, config: Config, p: sqlite3.Row) -> dict[str, Any]:
    from .payments import title_for
    return {
        "payment_id": p["id"],
        "status": {"pending": "на проверке", "paid": "зачислено", "rejected": "отклонено",
                   "cancelled": "отменено"}.get(p["status"], p["status"]),
        "method": title_for(conn, config, p["method"]),
        "amount_usd": fmt(p["amount_micro"]),
        "to_pay": f"{p['pay_amount']} {p['pay_currency']}",
        "receipt_attached": bool(p["receipt_file"]),
        "automatic_crypto": bool(p["auto_kind"]),
        "reject_reason": p["admin_note"] if p["status"] in ("rejected", "cancelled") else None,
        "created_at_utc": p["created_at"][:16].replace("T", " "),
        "minutes_since_created": _minutes_since(p["created_at"]),
    }


# ─────────────────────────────────────────── функции, которые может вызвать AI

TOOLS = [
    {"type": "function", "function": {
        "name": "get_my_account",
        "description": "Аккаунт клиента: логин, статус, баланс, число заказов. Только после подтверждения "
                       "через кабинет.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "get_order",
        "description": "Заказ клиента по номеру вида dx-… Только его собственные заказы.",
        "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"],
                       "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "list_my_orders",
        "description": "Последние заказы клиента (до 10). status: all | processing | failed | completed.",
        "parameters": {"type": "object", "properties": {"status": {"type": "string",
                       "enum": ["all", "processing", "failed", "completed"]}}, "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "get_payment",
        "description": "Заявка клиента на пополнение баланса по номеру (#N).",
        "parameters": {"type": "object", "properties": {"payment_id": {"type": "integer"}},
                       "required": ["payment_id"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "list_my_payments",
        "description": "Последние заявки клиента на пополнение (до 10).",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "my_bots_status",
        "description": "Свой Telegram-бот клиента (конструктор): можно ли подключить (и почему нет — сколько "
                       "заказов не хватает или запрет), и список его ботов с состоянием.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "escalate_to_admin",
        "description": "Передать обращение живому админу. Только если сам решить не можешь: деньги списаны, но "
                       "заказ не выполнен дольше 30 минут; заявка на пополнение висит дольше 2 часов с чеком; "
                       "спор; клиент настаивает на человеке. summary — кратко по-русски: суть, номера, что уже "
                       "проверено.",
        "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"],
                       "additionalProperties": False}}},
]


class Tools:
    """Исполнение функций AI для одного Telegram-пользователя."""

    def __init__(self, bot: "SupportBot", conn: sqlite3.Connection, tg_id: int, tg_name: str):
        self.bot, self.conn, self.config = bot, conn, bot.config
        self.tg_id, self.tg_name = tg_id, tg_name

    def run(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        fn = getattr(self, f"t_{name}", None)
        if fn is None:
            return {"error": "unknown_tool"}
        try:
            return fn(**args)
        except TypeError:
            return {"error": "bad_arguments"}

    def _user(self) -> sqlite3.Row | None:
        return _linked_user(self.conn, self.tg_id)

    def _need_user(self) -> sqlite3.Row | dict[str, Any]:
        u = self._user()
        if u is not None:
            return u
        return {"error": "not_verified", "how": LINK_HOWTO.format(site=self.config.base_url.rstrip("/"))}

    def t_get_my_account(self) -> dict[str, Any]:
        u = self._need_user()
        if isinstance(u, dict):
            return u
        n = self.conn.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (u["id"],)).fetchone()[0]
        return {"login": u["login"], "email": u["email"],
                "status": {"active": "активен", "pending": "ждёт одобрения", "blocked": "заблокирован"}.get(
                    u["status"], u["status"]),
                "balance_usd": fmt(u["balance_micro"]), "orders_total": n}

    def t_get_order(self, order_id: str) -> dict[str, Any]:
        u = self._need_user()
        if isinstance(u, dict):
            return u
        m = _ORDER.search(order_id or "")
        pid = m.group(1).lower() if m else (order_id or "").strip()
        o = self.conn.execute("SELECT * FROM orders WHERE user_id = ? AND public_id = ?", (u["id"], pid)).fetchone()
        return _order_for_ai(o) if o else {"error": "order_not_found_in_this_account"}

    def t_list_my_orders(self, status: str = "all") -> dict[str, Any]:
        u = self._need_user()
        if isinstance(u, dict):
            return u
        sql, args = "SELECT * FROM orders WHERE user_id = ?", [u["id"]]
        if status == "processing":
            sql += " AND status IN ('processing', 'attention')"
        elif status in ("failed", "completed"):
            sql += " AND status = ?"
            args.append(status)
        rows = self.conn.execute(sql + " ORDER BY id DESC LIMIT 10", args).fetchall()
        return {"orders": [_order_for_ai(o) for o in rows]}

    def t_get_payment(self, payment_id: int) -> dict[str, Any]:
        u = self._need_user()
        if isinstance(u, dict):
            return u
        p = self.conn.execute("SELECT * FROM payments WHERE user_id = ? AND id = ?", (u["id"], int(payment_id))
                              ).fetchone()
        return _payment_for_ai(self.conn, self.config, p) if p else {"error": "payment_not_found_in_this_account"}

    def t_list_my_payments(self) -> dict[str, Any]:
        u = self._need_user()
        if isinstance(u, dict):
            return u
        rows = self.conn.execute("SELECT * FROM payments WHERE user_id = ? ORDER BY id DESC LIMIT 10",
                                 (u["id"],)).fetchall()
        return {"payments": [_payment_for_ai(self.conn, self.config, p) for p in rows]}

    def t_my_bots_status(self) -> dict[str, Any]:
        from . import bots
        u = self._need_user()
        if isinstance(u, dict):
            return u
        e = bots.eligibility(self.conn, u)
        rows = self.conn.execute("SELECT username, enabled, disabled_reason, warn_count FROM bots WHERE user_id = ?",
                                 (u["id"],)).fetchall()
        return {
            "can_connect_new_bot": e["ok"], "why_not": e["reason"] or None,
            "completed_orders": e["done"], "orders_needed": e["need"],
            "bots": [{"username": "@" + (b["username"] or ""),
                      "state": "работает" if b["enabled"] else (
                          "отключён за отсутствие продаж — включает только админ" if b["disabled_reason"] == "inactive"
                          else "остановлен владельцем"),
                      "warnings_no_sales": b["warn_count"] if b["enabled"] else 0} for b in rows],
        }

    def t_escalate_to_admin(self, summary: str) -> dict[str, Any]:
        u = self._user()
        cur = self.conn.execute("INSERT INTO support_tickets (tg_id, user_id, summary, created_at) VALUES "
                                "(?, ?, ?, ?)", (self.tg_id, u["id"] if u else None, summary[:1500], db.now()))
        ticket = int(cur.lastrowid)
        self.bot.alert_admin(ticket, self.tg_id, self.tg_name, u, summary[:1500])
        return {"ok": True, "ticket": ticket}


# ─────────────────────────────────────────── вход только через кабинет
#
# Код делает сайт, а не AI: в кабинете «Поддержка в Telegram» кнопка открывает бота со
# ссылкой t.me/бот?start=КОД, а для другого устройства там же виден сам код — его можно
# просто отправить боту. Код одноразовый, живёт 15 минут, подобрать его нельзя (8 знаков,
# 10 неудачных попыток в час на Telegram-аккаунт).

LINK_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LINK_TTL = 15 * 60
LINK_TRIES_PER_HOUR = 10
_LINK = re.compile(r"\bDX[-\s]?([A-HJ-NP-Z2-9]{8})\b", re.I)
# Кириллица, похожая на латиницу: клиент перепечатал код с телефона — «DХ-АВС…» тоже поймём
_LOOKALIKE = str.maketrans("АВЕКМНРСТХУаеросхукмнвт", "ABEKMHPCTXYAEPOCXYKMHBT")


def find_code(text: str) -> str | None:
    """Код входа из сообщения: «DX-ABCD2345», «dx abcd 2345», пересланное уведомление, просто «ABCD2345»."""
    text = (text or "").translate(_LOOKALIKE)
    m = re.match(r"/start\s+([A-Za-z0-9]{8})$", text) or _LINK.search(text)
    if m:
        return m.group(1).upper()
    m = re.search(r"\bDX[\s:–—-]*((?:[A-HJ-NP-Z2-9][\s-]?){8})(?![A-Z0-9])", text, re.I)
    if m:
        return re.sub(r"[\s-]", "", m.group(1)).upper()
    bare = re.sub(r"[\s-]", "", text)
    # Одно слово из 8 знаков — код, если в нём есть цифра или оно набрано заглавными (не «balances»)
    if re.fullmatch(r"[A-HJ-NP-Z2-9]{8}", bare, re.I) and (re.search(r"\d", bare) or bare.isupper()):
        return bare.upper()
    return None
LINK_HOWTO = ("Чтобы я увидел ваши заказы и баланс, подтвердите аккаунт: войдите на {site}, откройте "
              "«Уведомления» 🔔 ({site}/panel/notifications) и нажмите «Получить код для бота поддержки» — код "
              "придёт в уведомления, отправьте его сюда (вид DX-XXXXXXXX). Или откройте {site}/panel/support "
              "и нажмите «Открыть бота».")


def make_link_code(conn: sqlite3.Connection, user_id: int) -> str:
    code = "".join(secrets.choice(LINK_ALPHABET) for _ in range(8))
    conn.execute("DELETE FROM support_link_codes WHERE user_id = ? OR expires_at < ?", (user_id, time.time()))
    conn.execute("INSERT INTO support_link_codes (code_hash, user_id, expires_at) VALUES (?, ?, ?)",
                 (_hash(code), user_id, time.time() + LINK_TTL))
    return code


def bot_username(conn: sqlite3.Connection, config: Config) -> str:
    """Имя бота поддержки: из базы, а если бот ещё не записал его — спросить Telegram по токену."""
    name = db.get_setting(conn, "support.bot_username") or ""
    if name or not config.support_bot_token:
        return name
    try:
        from .tgbot import TelegramApi
        name = (TelegramApi(config.support_bot_token)("getMe") or {}).get("username") or ""
    except Exception as exc:
        log.warning("бот поддержки: getMe: %s", exc)
        return ""
    if name:
        db.set_setting(conn, "support.bot_username", name)
    return name


def send_code_notification(conn: sqlite3.Connection, config: Config, user_id: int) -> str:
    """Новый код входа — в уведомления кабинета (и в почту/своего бота, если они есть)."""
    from .notify import notify
    code = make_link_code(conn, user_id)
    bot = bot_username(conn, config)
    where = f"боту @{bot}" if bot else "боту поддержки"
    notify(conn, config, user_id, f"🔐 Код для бота поддержки: DX-{code} — отправьте его {where}. "
                                  f"Действует {LINK_TTL // 60} минут. Никому другому не сообщайте.",
           "/panel/support")
    return code


def link_by_code(conn: sqlite3.Connection, tg_id: int, code: str) -> sqlite3.Row | None:
    """Привязать Telegram к аккаунту по коду из кабинета. None — код неверный или устарел."""
    row = conn.execute("SELECT user_id FROM support_link_codes WHERE code_hash = ? AND expires_at >= ?",
                       (_hash(code.upper()), time.time())).fetchone()
    if row is None:
        return None
    conn.execute("DELETE FROM support_link_codes WHERE code_hash = ?", (_hash(code.upper()),))
    conn.execute("INSERT INTO support_links (tg_id, user_id, linked_at) VALUES (?, ?, ?) "
                 "ON CONFLICT(tg_id) DO UPDATE SET user_id = excluded.user_id, linked_at = excluded.linked_at",
                 (tg_id, row["user_id"], db.now()))
    return accounts.get_user(conn, row["user_id"])


def _hash(code: str) -> str:
    return hashlib.sha256(("donatix-support:" + code).encode()).hexdigest()


# ─────────────────────────────────────────── что AI знает о сервисе


def _min_orders(conn: sqlite3.Connection) -> int:
    from .bots import min_orders
    return min_orders(conn)


def system_prompt(conn: sqlite3.Connection, config: Config) -> str:
    from . import payments, sitecfg
    methods = [m for m in payments.methods(conn, config)]
    manual = ", ".join(m["title"] for m in methods if not m["auto"]) or "—"
    auto = ", ".join(m["title"] for m in methods if m["auto"]) or "—"
    min_tjs = payments.settings(conn, config)["min_tjs"]
    bots = sitecfg.client_bots_enabled(conn)
    site = config.base_url.rstrip("/")
    return PROMPT_FILE.read_text(encoding="utf-8").format(
        site_name=config.site_name, site=site, manual=manual, auto=auto,
        bots_line=" или через свой Telegram-бот из конструктора" if bots else "",
        min_line=f" (минимум {min_tjs} сомони)" if min_tjs and float(min_tjs) > 0 else "",
        min_orders=_min_orders(conn),
    ).strip()


# ─────────────────────────────────────────── AI


class OpenAIChat:
    def __init__(self, api_key: str, model: str, transport: httpx.BaseTransport | None = None):
        self.model = model
        self._client = httpx.Client(timeout=60, transport=transport,
                                    headers={"Authorization": f"Bearer {api_key}"})

    def __call__(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        resp = self._client.post(OPENAI_URL, json={"model": self.model, "messages": messages, "tools": TOOLS,
                                                   "tool_choice": "auto", "temperature": 0.3})
        if resp.status_code >= 400:
            raise RuntimeError(f"openai {resp.status_code}: {resp.text[:300]}")
        return resp.json()["choices"][0]["message"]


def answer(conn: sqlite3.Connection, config: Config, chat: Callable[[list[dict[str, Any]]], dict[str, Any]],
           tools: Tools, text: str) -> str:
    """Один ответ AI: история + новое сообщение, с вызовами функций по дороге."""
    history = conn.execute(
        "SELECT role, content FROM (SELECT * FROM support_history WHERE tg_id = ? ORDER BY id DESC LIMIT ?) "
        "ORDER BY id", (tools.tg_id, HISTORY_TURNS)).fetchall()
    verified = _linked_user(conn, tools.tg_id)
    state = (f"[Статус: аккаунт подтверждён — логин {verified['login']}]" if verified else
             "[Статус: аккаунт не подтверждён]")
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt(conn, config)}]
    messages += [{"role": r["role"], "content": r["content"]} for r in history]
    messages.append({"role": "system", "content": state})
    messages.append({"role": "user", "content": text})
    reply = ""
    for _ in range(MAX_TOOL_ROUNDS):
        msg = chat(messages)
        calls = msg.get("tool_calls") or []
        if not calls:
            reply = (msg.get("content") or "").strip()
            break
        messages.append({"role": "assistant", "content": msg.get("content"), "tool_calls": calls})
        for call in calls:
            fn = call.get("function") or {}
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.run(str(fn.get("name")), args if isinstance(args, dict) else {})
            messages.append({"role": "tool", "tool_call_id": call.get("id"),
                             "content": json.dumps(result, ensure_ascii=False)})
    if not reply:
        reply = ("Не получилось ответить сразу — передал ваш вопрос администратору, ответ придёт сюда. / "
                 "Ҷавоб додан нашуд — саволи шумо ба админ фиристода шуд.")
    now = db.now()
    conn.execute("INSERT INTO support_history (tg_id, role, content, created_at) VALUES (?, 'user', ?, ?)",
                 (tools.tg_id, text, now))
    conn.execute("INSERT INTO support_history (tg_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)",
                 (tools.tg_id, reply, now))
    return reply


def connect_bot(conn: sqlite3.Connection, config: Config, tg_id: int, token: str) -> str:
    """Подключить бота клиента по токену из чата. Правила — те же, что в кабинете."""
    from . import bots
    from .worker import notify_admin
    user = _linked_user(conn, tg_id)
    if user is None:
        return (LINK_HOWTO.format(site=config.base_url.rstrip("/")) + " Токен после этого отправьте ещё раз."
                "\n\nАввал ҳисобро тасдиқ кунед: дар кабинет «Поддержка в Telegram»-ро кушоед.")
    e = bots.eligibility(conn, user)
    if not e["ok"]:
        return e["reason"]
    try:
        username = bots.check_token(token)
        bots.create(conn, config, user_id=user["id"], token=token, admin_ids=str(tg_id), username=username)
    except bots.BotError as exc:
        return f"Не получилось подключить: {exc}"
    if bots.RUNNER:
        bots.RUNNER.poke()
    notify_admin(config, f"🤖 Клиент {user['login']} подключил бота @{username} через бота поддержки.")
    return (f"✅ Бот @{username} подключён и запустится в течение минуты. Вы — его админ.\n"
            f"Откройте @{username}, нажмите /start, затем /panel — там игры, цены и реквизиты.\n\n"
            f"✅ Бот @{username} пайваст шуд. Онро кушоед, /start ва баъд /panel-ро пахш кунед.")


# ─────────────────────────────────────────── Telegram


class SupportBot:
    def __init__(self, config: Config, api: Callable[..., Any] | None = None,
                 chat: Callable[[list[dict[str, Any]]], dict[str, Any]] | None = None):
        from .tgbot import TelegramApi
        self.config = config
        self.api = api or TelegramApi(config.support_bot_token)
        self.chat = chat or OpenAIChat(config.openai_api_key, config.support_model)
        self.admin_chat = str(config.support_admin_id or config.alert_telegram_chat_id or "").strip()
        self.username = ""
        self._link_fails: dict[int, list[float]] = {}
        self._hits: dict[int, list[float]] = {}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="donatix-support", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        conn = db.connect(self.config.db_path)
        offset = int(db.get_setting(conn, "support.tg_offset", "0") or 0)
        try:
            try:   # webhook от прежнего использования токена не даёт получать сообщения — снимаем
                self.api("deleteWebhook", drop_pending_updates=False)
            except Exception as exc:
                log.warning("бот поддержки: deleteWebhook: %s", exc)
            me = self.api("getMe") or {}
            self.username = me.get("username") or ""
            log.info("бот поддержки запущен: @%s, модель %s", self.username, self.config.support_model)
            if self.username:
                # Контакт поддержки на сайте — этот бот, а не личный аккаунт админа
                self.config.support_contact = "@" + self.username
                db.set_setting(conn, "support.bot_username", self.username)
            self.api("setMyCommands", commands=[{"command": "start", "description": "Начать / Оғоз"},
                                                {"command": "logout", "description": "Выйти из аккаунта"}])
        except Exception as exc:
            log.warning("бот поддержки: %s", exc)
        try:
            while not self._stop.is_set():
                try:
                    updates = self.api("getUpdates", offset=offset, timeout=25, allowed_updates=["message"]) or []
                except Exception as exc:
                    log.warning("бот поддержки: %s", exc)
                    self._stop.wait(10)
                    continue
                for upd in updates:
                    offset = max(offset, int(upd["update_id"]) + 1)
                    try:
                        self.handle(conn, upd)
                    except Exception:
                        log.exception("бот поддержки: сообщение %s", upd.get("update_id"))
                db.set_setting(conn, "support.tg_offset", str(offset))
        finally:
            conn.close()

    def send(self, chat_id: int | str, text: str) -> None:
        for i in range(0, len(text), 4000):  # длинный ответ — частями
            self.api("sendMessage", chat_id=chat_id, text=text[i:i + 4000], disable_web_page_preview=True)

    def _limited(self, tg_id: int) -> bool:
        count, window = MSG_LIMIT
        now = time.time()
        hits = [t for t in self._hits.get(tg_id, []) if now - t < window]
        hits.append(now)
        self._hits[tg_id] = hits
        return len(hits) > count

    def handle(self, conn: sqlite3.Connection, upd: dict[str, Any]) -> None:
        msg = upd.get("message") or {}
        chat = msg.get("chat") or {}
        if chat.get("type") != "private":
            return
        tg_id = int(chat.get("id"))
        user = msg.get("from") or {}
        name = ("@" + user["username"]) if user.get("username") else (user.get("first_name") or str(tg_id))
        text = (msg.get("text") or msg.get("caption") or "").strip()

        # Админ: reply на обращение уходит клиенту; всё остальное бот понимает как от обычного клиента
        is_admin = bool(self.admin_chat) and str(tg_id) == self.admin_chat
        if is_admin and msg.get("reply_to_message"):
            self._admin_reply(conn, msg, text)
            return
        code = find_code(text)
        if code:
            self._link(conn, tg_id, code)
            return
        if is_admin and (text.startswith("/admin") or text == "/start"):
            self.send(tg_id, "👋 Вы — админ поддержки. Обращения клиентов (🆘) приходят сюда; чтобы ответить, "
                             "сделайте reply на обращение. Остальные ваши сообщения бот понимает как от клиента — "
                             "можно проверить его: пришлите код из уведомлений или задайте вопрос.")
            return
        if text in ("/test", "/admin"):
            text = "/start"
        if text.startswith("/start"):
            self.send(tg_id, "Салом! Ман ёрдамчии Donatix ҳастам. Саволи худро нависед — масалан, «фармоиш "
                             "нарасид» ё «баланс пур нашуд».\n\nЗдравствуйте! Я помощник Donatix. Напишите "
                             "вопрос — например, «заказ не пришёл» или «баланс не пополнился».")
            return
        if text.startswith("/logout"):
            conn.execute("DELETE FROM support_links WHERE tg_id = ?", (tg_id,))
            conn.execute("DELETE FROM support_history WHERE tg_id = ?", (tg_id,))
            self.send(tg_id, "Вы вышли из аккаунта. / Шумо аз ҳисоб баромадед.")
            return
        if not text:
            self.send(tg_id, "Напишите вопрос текстом. / Саволро бо матн нависед.")
            return
        if _TOKEN.search(text):
            # Токен бота в AI и в историю не уходит: подключаем сами, по тем же правилам, что в кабинете
            reply = connect_bot(conn, self.config, tg_id, _TOKEN.search(text).group(0))
            conn.execute("INSERT INTO support_history (tg_id, role, content, created_at) VALUES "
                         "(?, 'user', '[клиент прислал токен бота]', ?), (?, 'assistant', ?, ?)",
                         (tg_id, db.now(), tg_id, reply, db.now()))
            self.send(tg_id, reply)
            return
        if self._limited(tg_id):
            self.send(tg_id, "Слишком много сообщений — подождите несколько минут. / Каме сабр кунед.")
            return
        try:
            self.api("sendChatAction", chat_id=tg_id, action="typing")
        except Exception:
            pass
        try:
            reply = answer(conn, self.config, self.chat, Tools(self, conn, tg_id, name), text[:MAX_INPUT])
        except Exception as exc:
            log.exception("бот поддержки: AI")
            reply = ("Сейчас не могу ответить — попробуйте через минуту. / Ҳоло ҷавоб дода наметавонам — "
                     "пас аз як дақиқа боз нависед.")
            if is_admin:   # админу — настоящая причина (ключ, лимит, модель)
                reply += f"\n\n⚙️ Для админа: {str(exc)[:500]}"
        self.send(tg_id, reply)

    def _link(self, conn: sqlite3.Connection, tg_id: int, code: str) -> None:
        now = time.time()
        fails = [t for t in self._link_fails.get(tg_id, []) if now - t < 3600]
        if len(fails) >= LINK_TRIES_PER_HOUR:
            self.send(tg_id, "Слишком много неверных кодов — попробуйте через час. / Пас аз як соат кӯшиш кунед.")
            return
        user = link_by_code(conn, tg_id, code)
        if user is None:
            self._link_fails[tg_id] = fails + [now]
            self.send(tg_id, "Код неверный или устарел (живёт 15 минут, работает один раз). На сайте откройте "
                             f"🔔 Уведомления → «Получить код для бота поддержки» и пришлите новый код сюда.\n{self.config.base_url}"
                             "/panel/notifications\n\nКод нодуруст ё кӯҳна аст. Дар сайт 🔔 → «Получить код» "
                             "пахш кунед ва коди навро ин ҷо фиристед.")
            return
        self.send(tg_id, f"✅ Аккаунт подтверждён: {user['login']}. Теперь напишите вопрос — вижу ваши заказы, "
                         "пополнения и баланс.\n\n✅ Ҳисоб тасдиқ шуд. Акнун саволи худро нависед.")

    def alert_admin(self, ticket: int, tg_id: int, tg_name: str, user: sqlite3.Row | None, summary: str) -> None:
        who = f"{user['login']} · {user['email']}" if user else "аккаунт не подтверждён"
        text = (f"🆘 Обращение #{ticket} · tg{tg_id}\nКлиент: {tg_name} ({who})\n\n{summary}\n\n"
                f"Ответить: сделайте reply на это сообщение в боте @{self.username or 'поддержки'} — ответ уйдёт "
                "клиенту.")
        sent = False
        if self.admin_chat:
            try:
                self.api("sendMessage", chat_id=self.admin_chat, text=text)
                sent = True
            except Exception as exc:  # админ ещё не нажал /start в боте поддержки
                log.warning("бот поддержки: админу не доставлено: %s", exc)
        if not sent:
            from .worker import notify_admin
            notify_admin(self.config, text + "\n\n(Нажмите /start в боте поддержки, чтобы отвечать клиентам.)")

    def _admin_reply(self, conn: sqlite3.Connection, msg: dict[str, Any], text: str) -> None:
        original = (msg.get("reply_to_message") or {}).get("text") or ""
        m = re.search(r"tg(\d+)", original)
        if not m or not text:
            self.send(self.admin_chat, "Чтобы ответить клиенту, сделайте reply на его обращение (🆘 …).")
            return
        client_id = int(m.group(1))
        self.send(client_id, f"👤 Ответ администратора / Ҷавоби админ:\n{text}")
        conn.execute("INSERT INTO support_history (tg_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)",
                     (client_id, f"[Ответ администратора] {text}", db.now()))
        t = re.search(r"#(\d+)", original)
        if t:
            conn.execute("UPDATE support_tickets SET status = 'answered' WHERE id = ?", (int(t.group(1)),))
        self.send(self.admin_chat, "✅ Отправлено клиенту.")

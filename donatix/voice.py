"""Голосовой помощник админки: спрашиваешь голосом — отвечает голосом.

Основной режим — голосовой режим OpenAI Realtime, как голос в приложении ChatGPT: модель сама слушает и сама
говорит живым голосом (marin), её можно перебить. Браузер соединяется с OpenAI напрямую (WebRTC) по
одноразовому ключу на минуту (realtime_session); настоящий ключ (DONATIX_OPENAI_API_KEY) остаётся на сервере.
Цифры магазина модель спрашивает инструментами — их выполняет наш сервер (run_tool).

Запасной режим, если Realtime недоступен: запись голоса → текст → ответ с инструментами → озвучка (ask).

Помощник только смотрит и подсказывает: деньги, заказы и настройки голосом не меняются — для этого он
открывает нужный раздел. Работает только в админке и только для админа.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import sqlite3
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from .config import Config

log = logging.getLogger(__name__)

OPENAI = "https://api.openai.com/v1"
TIMEOUT = httpx.Timeout(45, connect=10)
MAX_AUDIO = 8 * 1024 * 1024
MAX_TOOL_ROUNDS = 4

#: Разделы админки — что в каждом и где лежит. Помощник отвечает по ним на «как…», «где…», «что это…».
GUIDE = """
РАЗДЕЛЫ АДМИНКИ DONATIX (сайт пополнения игр и сервисов, Таджикистан; деньги клиентов — в долларах на балансе,
платят в сомони по курсу):
- Сводка (/admin): приветствие, баланс у поставщика, прибыль и заказы сегодня (сравнение со вчера), выручка за
  14 дней (сегодня — красный столбик), кольца: маржа, выполненные заказы, покрыты ли деньги клиентов, сегодня
  к среднему дню, доля бота-магазина. Внизу последние заказы и лучшие клиенты.
- Учёт денег (/admin/money): все деньги за период — сколько пришло, продано, закупка, прибыль, рефералы, D-коин,
  кассиры. Кнопки «Скачать» — файл Excel для ИП: оборот и прибыль по дням, налог с прибыли (ставку задаёт владелец
  там же), все заказы (убыточные — красным), все поступления. Каждое утро файл за вчера приходит в админ-бот.
  Блок «В минусе N заказов» — продали дешевле закупки.
- Деньги за сутки (/admin/finance): итог суток с 00:00 до 00:00 по Душанбе, сколько отправить поставщику.
- Аналитика продаж (/admin/stats) и Посещаемость (/admin/traffic): графики заказов и посетителей.
- Прайс-лист картинкой (/admin/pricelist).
- Заказы (/admin/orders): поиск по номеру dx-…, ID игрока, логину; статусы: выполнен, в работе, требует внимания,
  не выполнен (деньги вернулись). В заказе — закупка (точно от поставщика или по каталогу), курс, прибыль и наценка.
- Пополнения (/admin/payments): заявки клиентов с чеками — подтвердить или отклонить. ИИ читает чек; уже принятый
  чек второй раз не принимается.
- Отзывы (/admin/reviews), Акция на главной (/admin/promo), Подарки Telegram (/admin/gifts), Конкурс (/admin/contest).
- Баннеры рекламы (/admin/banners): лента рекламы вверху сайта, кабинета и мини-приложения, а также в Telegram-ботах
  (наш магазин, бот Stars, боты партнёров — не больше 2 раз в день человеку). Клиенты подают заявки в кабинете
  (/panel/ads): 7 сомони в день, 1–3 дня, оплата с баланса; админ одобряет (показ ровно оплаченные сутки) или
  отклоняет (деньги возвращаются). Нельзя: азартные игры, конкуренты, чужие бренды, 18+, обман. Баннер со ссылкой
  /panel/ads («Здесь может быть ваша реклама») всегда последний. Честный счёт просмотров и нажатий.
- Реквизиты (/admin/pay-settings): карты и способы оплаты, курс сомони.
- Ошибки (/admin/errors): что сломалось у поставщика и платежей.
- Клиенты (/admin/users) и Заявки (/admin/users?status=pending): баланс, наценка, блокировка, пополнить вручную.
- Каталог (/admin/products) и Загрузка каталога (/admin/catalog-sync): товары и цены поставщика, картинки.
- Бот-магазин (/admin/shopbot) и Конструктор ботов (/admin/bots): боты партнёров — свой магазин в Telegram на
  товарах Donatix; партнёр задаёт наценку и цену Glory; при обновлении сайта боты доделывают начатые заказы.
- Glory — боты для гильдии (клан FF): набирают славу клану; продаётся на сайте, по API и в ботах партнёров.
- Настройки (/admin/settings): наценки по уровням, для API, регистрация, контакты.
Кнопка «+» внизу — быстрые действия; шарик в поиске — я, голосовой помощник.
""".strip()

PAGES = {
    "сводка": "/admin", "учёт денег": "/admin/money", "деньги за сутки": "/admin/finance", "аналитика": "/admin/stats",
    "посещаемость": "/admin/traffic", "прайс-лист": "/admin/pricelist", "заказы": "/admin/orders",
    "пополнения": "/admin/payments", "отзывы": "/admin/reviews", "акция": "/admin/promo", "баннеры": "/admin/banners",
    "подарки": "/admin/gifts", "конкурс": "/admin/contest", "реквизиты": "/admin/pay-settings",
    "ошибки": "/admin/errors", "клиенты": "/admin/users", "заявки": "/admin/users?status=pending",
    "каталог": "/admin/products", "загрузка каталога": "/admin/catalog-sync", "бот-магазин": "/admin/shopbot",
    "боты партнёров": "/admin/bots", "настройки": "/admin/settings",
}

SYSTEM = (
    "Ты — голосовой помощник админки магазина Donatix. Тебя слушают ушами, поэтому отвечай КОРОТКО: 1–3 "
    "предложения, живым разговорным языком, без списков, ссылок, звёздочек и эмодзи. Отвечай на языке вопроса "
    "(русский или таджикский). Цифры о магазине бери ТОЛЬКО из инструментов — не выдумывай. Деньги называй "
    "округлённо: доллары и, если есть, примерно в сомони. Ты ничего не меняешь сам (деньги, заказы, настройки) — "
    "если просят что-то сделать, скажи, где это нажать, и открой раздел инструментом open_page. "
    "Если спрашивают «как», «где», «что это» — отвечай по описанию разделов ниже.\n\n" + GUIDE
)

TOOLS = [
    {"type": "function", "function": {
        "name": "shop_summary",
        "description": "Цифры магазина за период: поступления, продажи, закупка, прибыль, заказы, баланс поставщика, "
                       "деньги клиентов, что ждёт проверки.",
        "parameters": {"type": "object", "properties": {
            "period": {"type": "string", "enum": ["today", "yesterday", "7d", "30d", "month"]}},
            "required": ["period"]}}},
    {"type": "function", "function": {
        "name": "find_order",
        "description": "Найти заказы: по номеру (dx-123), ID игрока, названию товара или логину клиента.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "find_client",
        "description": "Найти клиента по логину, почте или номеру: баланс, заказы, когда покупал.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "pending",
        "description": "Что ждёт админа сейчас: заявки на пополнение, заказы с проблемой, заявки на рекламу, новые клиенты.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "top_products",
        "description": "Что больше всего продаётся за последние дни (по выручке).",
        "parameters": {"type": "object", "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 90}},
                       "required": ["days"]}}},
    {"type": "function", "function": {
        "name": "open_page",
        "description": "Открыть раздел админки после ответа.",
        "parameters": {"type": "object", "properties": {"page": {"type": "string", "enum": list(PAGES)}},
                       "required": ["page"]}}},
]


class VoiceError(Exception):
    pass


def enabled(config: Config) -> bool:
    return bool(config.openai_api_key)


# ── Инструменты: только чтение ───────────────────────────────


def _usd(micro: Any) -> float:
    return round(int(micro or 0) / 10_000, 2)


def _rate(conn: sqlite3.Connection, config: Config) -> Decimal:
    from .payments import settings
    try:
        return Decimal(str(settings(conn, config)["tjs_rate"] or 0))
    except Exception:  # noqa: BLE001
        return Decimal(0)


def _money(micro: Any, rate: Decimal) -> dict[str, Any]:
    usd = _usd(micro)
    return {"usd": usd, "tjs": round(float(Decimal(str(usd)) * rate)) if rate else None}


def _period(conn: sqlite3.Connection, key: str) -> tuple[datetime, datetime]:
    from . import finance, periods, timez
    if key in ("today", "yesterday"):
        return finance.window(conn, days_back=1 if key == "yesterday" else 0)
    pr = periods.resolve(timez.zone(timez.site_zone_name(conn)), key, default="30d")
    return pr.start, pr.end


def shop_summary(conn: sqlite3.Connection, config: Config, period: str = "today") -> dict[str, Any]:
    from . import finance, worker
    start, end = _period(conn, period if period in ("today", "yesterday", "7d", "30d", "month") else "today")
    s = finance.summary(conn, config, start, end)
    rate = s["rate"] or _rate(conn, config)
    supplier = worker.supplier_balance_cached(conn)
    one = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    return {
        "period": period, "from": start.strftime("%d.%m.%Y"), "to_exclusive": end.strftime("%d.%m.%Y %H:%M"),
        "rate_tjs_per_usd": float(rate) if rate else None,
        "received_from_clients": _money(s["received"], rate), "payments": s["payments"],
        "orders_completed": s["orders"], "sales": _money(s["revenue"], rate), "supplier_cost": _money(s["cost"], rate),
        "gross_profit": _money(s["gross_profit"], rate), "net_profit": _money(s["profit"], rate),
        "owner_profit": _money(s["owner_profit"], rate),
        "supplier_balance_usd": float(supplier) if supplier is not None else None,
        "clients_balance": _money(s["clients_balance"], rate),
        "waiting": {"payments": one("SELECT COUNT(*) FROM payments WHERE status = 'pending'"),
                    "orders_attention": one("SELECT COUNT(*) FROM orders WHERE status = 'attention'"),
                    "orders_processing": one("SELECT COUNT(*) FROM orders WHERE status = 'processing'")},
    }


def _local(ts: Any, conn: sqlite3.Connection) -> str:
    from . import timez
    return timez.local(ts, timez.site_zone_name(conn)) if ts else ""


def find_order(conn: sqlite3.Connection, config: Config, query: str) -> dict[str, Any]:
    from . import orders
    q = (query or "").strip()
    if not q:
        return {"found": 0, "orders": []}
    m = re.search(r"(?:dx-?)?(\d{1,9})$", q.lower().replace(" ", ""))
    rows = []
    if m:
        rows = conn.execute("SELECT o.*, u.login FROM orders o JOIN users u ON u.id = o.user_id "
                            "WHERE o.public_id = ? OR o.id = ? LIMIT 3", (f"dx-{m.group(1)}", int(m.group(1)))).fetchall()
    if not rows:
        like = f"%{q[:60]}%"
        rows = conn.execute("SELECT o.*, u.login FROM orders o JOIN users u ON u.id = o.user_id WHERE o.product_name LIKE ? "
                            "OR o.fields_json LIKE ? OR u.login LIKE ? ORDER BY o.id DESC LIMIT 5",
                            (like, like, like)).fetchall()
    rate = _rate(conn, config)
    return {"found": len(rows), "orders": [{
        "id": r["public_id"], "status": orders.client_status(r["status"]), "status_raw": r["status"],
        "product": r["product_name"], "client": r["login"], "paid": _money(r["total_micro"], rate),
        "profit": _money(r["total_micro"] - r["cost_micro"], rate), "created": _local(r["created_at"], conn),
        "problem": (r["error"] or "")[:160]} for r in rows]}


def find_client(conn: sqlite3.Connection, config: Config, query: str) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"found": 0, "clients": []}
    like = f"%{q[:60]}%"
    rows = conn.execute("SELECT * FROM users WHERE login LIKE ? OR email LIKE ? OR CAST(id AS TEXT) = ? "
                        "ORDER BY id DESC LIMIT 5", (like, like, q)).fetchall()
    rate = _rate(conn, config)
    out = []
    for u in rows:
        o = conn.execute("SELECT COUNT(*), COALESCE(SUM(total_micro), 0), MAX(created_at) FROM orders "
                         "WHERE user_id = ? AND status = 'completed'", (u["id"],)).fetchone()
        out.append({"login": u["login"], "status": u["status"], "role": u["role"], "balance": _money(u["balance_micro"], rate),
                    "orders_completed": o[0], "spent": _money(o[1], rate), "last_order": _local(o[2], conn)})
    return {"found": len(out), "clients": out}


def pending(conn: sqlite3.Connection, config: Config) -> dict[str, Any]:
    rate = _rate(conn, config)
    pays = conn.execute("SELECT p.id, p.amount_micro, p.pay_amount, p.pay_currency, p.created_at, u.login FROM payments p "
                        "JOIN users u ON u.id = p.user_id WHERE p.status = 'pending' ORDER BY p.id LIMIT 5").fetchall()
    attention = conn.execute("SELECT o.public_id, o.product_name, o.error, u.login FROM orders o JOIN users u "
                             "ON u.id = o.user_id WHERE o.status = 'attention' ORDER BY o.id LIMIT 5").fetchall()
    try:
        ads = conn.execute("SELECT COUNT(*) FROM banners WHERE status = 'pending'").fetchone()[0]
    except sqlite3.OperationalError:
        ads = 0
    users = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'").fetchone()[0]
    return {
        "payments": [{"id": p["id"], "client": p["login"], "amount": f"{p['pay_amount']} {p['pay_currency']}",
                      "credit": _money(p["amount_micro"], rate), "since": _local(p["created_at"], conn)} for p in pays],
        "orders_attention": [{"id": o["public_id"], "product": o["product_name"], "client": o["login"],
                              "problem": (o["error"] or "")[:120]} for o in attention],
        "ad_requests": ads, "new_clients_waiting": users,
    }


def top_products(conn: sqlite3.Connection, config: Config, days: int = 30) -> dict[str, Any]:
    from . import orders
    since, _ = orders._local_start(conn, max(1, min(int(days or 30), 90)))
    rate = _rate(conn, config)
    rows = conn.execute("SELECT product_name, COUNT(*) AS n, SUM(total_micro) AS rev, SUM(total_micro - cost_micro) AS pr "
                        "FROM orders WHERE status = 'completed' AND created_at >= ? GROUP BY product_name "
                        "ORDER BY rev DESC LIMIT 5", (since,)).fetchall()
    return {"days": days, "top": [{"product": r["product_name"], "orders": r["n"], "sales": _money(r["rev"], rate),
                                   "profit": _money(r["pr"], rate)} for r in rows]}


def run_tool(conn: sqlite3.Connection, config: Config, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Выполнить инструмент. Вернёт (данные для модели, адрес раздела, если надо его открыть)."""
    if name == "open_page":
        url = PAGES.get(str(args.get("page", "")).lower())
        return ({"ok": True, "opened": url} if url else {"ok": False}), url
    funcs = {"shop_summary": lambda: shop_summary(conn, config, str(args.get("period", "today"))),
             "find_order": lambda: find_order(conn, config, str(args.get("query", ""))),
             "find_client": lambda: find_client(conn, config, str(args.get("query", ""))),
             "pending": lambda: pending(conn, config),
             "top_products": lambda: top_products(conn, config, int(args.get("days") or 30))}
    if name not in funcs:
        return {"error": "нет такого инструмента"}, None
    try:
        return funcs[name](), None
    except Exception as exc:  # noqa: BLE001 — сломанный инструмент не должен ронять ответ
        log.exception("помощник: инструмент %s", name)
        return {"error": f"не получилось: {exc}"[:200]}, None


# ── OpenAI: голос → текст → ответ → голос ────────────────────


def _client(transport: httpx.BaseTransport | None) -> httpx.Client:
    return httpx.Client(timeout=TIMEOUT, transport=transport)


def _headers(config: Config) -> dict[str, str]:
    return {"Authorization": f"Bearer {config.openai_api_key}"}


def transcribe(config: Config, audio: bytes, filename: str, transport: httpx.BaseTransport | None = None) -> str:
    """Голос → текст. Сначала новая модель распознавания, не вышло — whisper-1."""
    last = ""
    for model in dict.fromkeys((config.voice_stt_model, "whisper-1")):
        with _client(transport) as c:
            r = c.post(f"{OPENAI}/audio/transcriptions", headers=_headers(config),
                       files={"file": (filename, audio)}, data={"model": model, "response_format": "json"})
        if r.status_code == 200:
            return str((r.json() or {}).get("text") or "").strip()
        last = f"{r.status_code} {r.text[:160]}"
        log.warning("помощник: распознавание (%s): %s", model, last)
        if r.status_code in (401, 429):
            break
    raise VoiceError(_human(last, "распознать голос"))


def think(conn: sqlite3.Connection, config: Config, question: str, history: list[dict[str, str]], page: str = "",
          transport: httpx.BaseTransport | None = None) -> tuple[str, str | None]:
    """Ответ на вопрос (с инструментами). Вернёт (текст ответа, адрес раздела, который открыть)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM + f"\n\nСейчас {now}. Админ на странице {page or '/admin'}."}]
    for h in history[-8:]:
        if h.get("role") in ("user", "assistant") and h.get("text"):
            messages.append({"role": h["role"], "content": str(h["text"])[:600]})
    messages.append({"role": "user", "content": question[:1500]})
    go: str | None = None
    for _ in range(MAX_TOOL_ROUNDS + 1):
        body = {"model": config.voice_model, "messages": messages, "tools": TOOLS, "temperature": 0.4, "max_tokens": 400}
        with _client(transport) as c:
            r = c.post(f"{OPENAI}/chat/completions", headers=_headers(config), json=body)
        if r.status_code != 200:
            log.warning("помощник: ответ %s %s", r.status_code, r.text[:200])
            raise VoiceError(_human(f"{r.status_code} {r.text[:160]}", "ответить"))
        msg = r.json()["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        if not calls:
            return (msg.get("content") or "").strip() or "Не понял вопрос — скажите ещё раз, пожалуйста.", go
        messages.append({"role": "assistant", "content": msg.get("content"), "tool_calls": calls})
        for call in calls:
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            data, url = run_tool(conn, config, call["function"]["name"], args if isinstance(args, dict) else {})
            go = url or go
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(data, ensure_ascii=False, default=str)[:6000]})
    return "Слишком долго искал ответ — спросите, пожалуйста, проще.", go


#: Старые модели озвучки знают не все голоса: marin/cedar (как в ChatGPT) — только новые. Не принят голос — берём
#: ближайший из классических.
CLASSIC_VOICES = ("coral", "nova")


def speak(config: Config, text: str, transport: httpx.BaseTransport | None = None) -> bytes:
    """Текст → голос (mp3). Сначала новая модель озвучки голосом из настроек (marin — как в ChatGPT),
    не вышло — запасной голос, потом tts-1."""
    last = ""
    tries = [(config.voice_tts_model, v) for v in dict.fromkeys((config.voice_name,) + CLASSIC_VOICES)]
    tries += [("tts-1", v) for v in CLASSIC_VOICES]
    for model, voice_ in tries:
        body: dict[str, Any] = {"model": model, "voice": voice_, "input": text[:1500], "response_format": "mp3"}
        if model != "tts-1":
            body["instructions"] = "Говори дружелюбно и бодро, как живой помощник, в среднем темпе."
        with _client(transport) as c:
            r = c.post(f"{OPENAI}/audio/speech", headers=_headers(config), json=body)
        if r.status_code == 200 and r.content:
            return r.content
        last = f"{r.status_code} {r.text[:160]}"
        log.warning("помощник: озвучка (%s, %s): %s", model, voice_, last)
        if r.status_code in (401, 429):
            break
    raise VoiceError(_human(last, "озвучить ответ"))


# ── Realtime: голос как в ChatGPT ────────────────────────────

REALTIME_INSTRUCTIONS = (
    "Ты — голосовой помощник админки магазина Donatix, говоришь как живой человек: тепло, бодро, коротко "
    "(1–3 предложения). Отвечай на языке собеседника (русский или таджикский). Цифры о магазине бери ТОЛЬКО "
    "из инструментов — не выдумывай; деньги называй округлённо. Ничего не меняешь сам — если просят что-то "
    "сделать, скажи, где это нажать, и открой раздел инструментом open_page. Если тебя перебили — замолчи и слушай.\n\n"
    + GUIDE
)


def realtime_tools() -> list[dict[str, Any]]:
    """Те же инструменты, но в формате Realtime: без обёртки «function»."""
    return [{"type": "function", **t["function"]} for t in TOOLS]


def realtime_session(config: Config, transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    """Одноразовый ключ для браузера (живёт минуту) с готовыми настройками: модель, голос, инструкции,
    инструменты, распознавание реплик для подписи на экране. Сначала полные настройки, не приняли — проще,
    потом старый адрес (бета). Вернёт {ok, key, model, mode: ga|beta} или {ok: False, error}."""
    model = config.voice_realtime_model
    full = {"type": "realtime", "model": model, "instructions": REALTIME_INSTRUCTIONS, "tools": realtime_tools(),
            "tool_choice": "auto",
            "audio": {"input": {"transcription": {"model": config.voice_stt_model},
                                "turn_detection": {"type": "semantic_vad"}},
                      "output": {"voice": config.voice_name}}}
    simple = {"type": "realtime", "model": model, "instructions": REALTIME_INSTRUCTIONS, "tools": realtime_tools(),
              "audio": {"output": {"voice": config.voice_name}}}
    last = ""
    for session in (full, simple):
        with _client(transport) as c:
            r = c.post(f"{OPENAI}/realtime/client_secrets", headers=_headers(config),
                       json={"expires_after": {"anchor": "created_at", "seconds": 60}, "session": session})
        if r.status_code == 200:
            data = r.json() or {}
            key = data.get("value") or (data.get("client_secret") or {}).get("value")
            if key:
                return {"ok": True, "key": key, "model": model, "mode": "ga"}
        last = f"{r.status_code} {r.text[:200]}"
        log.warning("помощник: realtime-ключ: %s", last)
        if r.status_code in (401, 429):
            return {"ok": False, "error": _human(last, "включить голосовой режим")}
    with _client(transport) as c:   # старый адрес (бета) — на случай, если новый ещё не включён для аккаунта
        r = c.post(f"{OPENAI}/realtime/sessions", headers={**_headers(config), "OpenAI-Beta": "realtime=v1"},
                   json={"model": model, "voice": config.voice_name, "instructions": REALTIME_INSTRUCTIONS,
                         "tools": realtime_tools(), "input_audio_transcription": {"model": "whisper-1"}})
    if r.status_code == 200:
        key = ((r.json() or {}).get("client_secret") or {}).get("value")
        if key:
            return {"ok": True, "key": key, "model": model, "mode": "beta"}
    log.warning("помощник: realtime (бета): %s %s", r.status_code, r.text[:200])
    return {"ok": False, "error": _human(last or f"{r.status_code}", "включить голосовой режим")}


def _human(raw: str, what: str) -> str:
    if raw.startswith("401"):
        return "Ключ OpenAI не подходит — проверьте его на сервере (deploy/openai.sh)."
    if raw.startswith("429"):
        return "У OpenAI закончился баланс или слишком много запросов — пополните счёт OpenAI или подождите минуту."
    return f"Не получилось {what}. Попробуйте ещё раз."


def ask(conn: sqlite3.Connection, config: Config, *, audio: bytes = b"", filename: str = "voice.webm", text: str = "",
        history: list[dict[str, str]] | None = None, page: str = "", transport: httpx.BaseTransport | None = None
        ) -> dict[str, Any]:
    """Одна реплика: голос (или текст) → ответ текстом и голосом. Ошибки — понятным текстом, без голоса."""
    started = time.monotonic()
    try:
        heard = text.strip() or (transcribe(config, audio, filename, transport) if audio else "")
        if not heard:
            return {"ok": True, "heard": "", "reply": "", "audio": None, "go": None, "silent": True}
        reply, go = think(conn, config, heard, history or [], page, transport)
        sound = speak(config, reply, transport)
    except VoiceError as exc:
        return {"ok": False, "error": str(exc)}
    except httpx.HTTPError:
        log.exception("помощник: нет связи с OpenAI")
        return {"ok": False, "error": "Нет связи с OpenAI — попробуйте через минуту."}
    log.info("помощник: ответ за %.1f с", time.monotonic() - started)
    return {"ok": True, "heard": heard, "reply": reply, "audio": base64.b64encode(sound).decode(), "go": go}

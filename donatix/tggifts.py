"""Подарки Telegram (Bot API: getAvailableGifts / sendGift) — продаются в мини-приложении /tg.

Подарок отправляет бот мини-приложения (DONATIX_GIFT_BOT_TOKEN) со своего баланса Stars. Пополнить
баланс бота можно только вручную: админ пишет боту /topup 500 и оплачивает счёт в Stars.

Заказ (gift_orders):
  awaiting_recipient — оплачен с баланса Donatix, ждём, пока получатель нажмёт Start в боте
                       (не нажал за RECIPIENT_HOURS — деньги вернутся сами);
  paid      — получатель известен, ждёт отправки (воркер);
  sending   — воркер забрал заказ и вызывает sendGift (захват атомарный — двойной отправки нет);
  sent      — подарок ушёл;
  unknown   — сеть/таймаут/5xx: дошёл ли запрос, неизвестно. Вслепую НЕ повторяем: ищем покупку
              в истории Stars бота (getStarTransactions). Нашли — sent, нет через UNKNOWN_MINUTES — снова paid;
  failed    — Telegram отказал (400/403): деньги клиенту вернулись, админу — сообщение;
  refunded  — вернули вручную из админки.
"""

from __future__ import annotations

import json
import logging
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any

import httpx

from . import accounts, db
from .config import Config

log = logging.getLogger("donatix.gifts")

RECIPIENT_HOURS = 72          # получатель не нажал Start — возврат
UNKNOWN_MINUTES = 15          # «неизвестно, ушёл ли» — сколько ищем в истории Stars, потом повтор
SYNC_SECONDS = 15 * 60        # каталог подарков — раз в 15 минут
LOW_ALERT_SECONDS = 3600      # «мало Stars» — не чаще раза в час
TEXT_MAX = 128

SCHEMA = """
CREATE TABLE IF NOT EXISTS tg_gifts (
    id          TEXT PRIMARY KEY,
    star_count  INTEGER NOT NULL,
    emoji       TEXT,
    remaining   INTEGER,              -- лимитированный: сколько осталось (NULL — без лимита)
    total       INTEGER,
    premium     INTEGER NOT NULL DEFAULT 0,
    img         TEXT,                 -- превью на нашем сервере (data/gifts/<id>.webp)
    active      INTEGER NOT NULL DEFAULT 1,
    hidden      INTEGER NOT NULL DEFAULT 0,   -- скрыт админом
    sort        INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gift_orders (
    id            INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id),   -- кто купил (баланс Donatix)
    gift_id       TEXT NOT NULL,
    star_count    INTEGER NOT NULL,
    price_micro   INTEGER NOT NULL,
    cost_micro    INTEGER NOT NULL DEFAULT 0,
    recipient_id  INTEGER,                                 -- Telegram ID получателя
    recipient     TEXT,                                    -- как показать: имя или @ник
    text          TEXT,
    link_token    TEXT UNIQUE,                             -- ссылка t.me/<бот>?start=g_<token> для друга
    status        TEXT NOT NULL,
    error         TEXT,
    tx_id         TEXT UNIQUE,                             -- транзакция Stars, найденная при сверке
    sending_at    REAL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS gift_orders_status ON gift_orders(status, id);
CREATE INDEX IF NOT EXISTS gift_orders_user ON gift_orders(user_id, id DESC);
CREATE TABLE IF NOT EXISTS gift_users (          -- кто нажимал Start в боте: @ник → ID (Bot API ник не ищет)
    tg_id       INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    lang        TEXT,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS gift_users_username ON gift_users(username);
CREATE TABLE IF NOT EXISTS gift_tx (             -- исходящие покупки подарков из истории Stars бота
    tx_id       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    gift_id     TEXT,
    date        INTEGER NOT NULL
);
"""


def ensure(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def enabled(config: Config) -> bool:
    return bool(config.gift_bot_token)


# ── Telegram Bot API ─────────────────────────────────────────


class NetError(Exception):
    """Сеть, таймаут или 5xx: дошёл ли запрос до Telegram — неизвестно."""


class ApiError(Exception):
    def __init__(self, code: int, description: str, retry_after: int = 0):
        super().__init__(f"{code}: {description}")
        self.code, self.description, self.retry_after = code, description, retry_after


def call(config: Config, method: str, _timeout: float = 20, **payload: Any) -> Any:
    """Вызов Bot API бота мини-приложения. Ошибки — по error_code (тексты Telegram не документированы)."""
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        # _timeout — сколько ждать ответа; timeout в payload — параметр самого Telegram (getUpdates)
        r = httpx.post(f"https://api.telegram.org/bot{config.gift_bot_token}/{method}", json=payload, timeout=_timeout)
    except httpx.HTTPError as exc:
        raise NetError(exc.__class__.__name__) from None
    if r.status_code >= 500:
        raise NetError(f"HTTP {r.status_code}")
    try:
        body = r.json()
    except ValueError:
        raise NetError("не JSON") from None
    if not body.get("ok"):
        code = int(body.get("error_code") or r.status_code or 400)
        if code >= 500:
            raise NetError(f"{code}: {body.get('description')}")
        raise ApiError(code, str(body.get("description") or ""),
                       int((body.get("parameters") or {}).get("retry_after") or 0))
    return body.get("result")


def star_balance(config: Config) -> int | None:
    try:
        return int((call(config, "getMyStarBalance", _timeout=10) or {}).get("amount") or 0)
    except (NetError, ApiError) as exc:
        log.warning("баланс Stars бота: %s", exc)
        return None


# ── Каталог ──────────────────────────────────────────────────


def img_dir(config: Config) -> Path:
    return Path(config.db_path).parent / "gifts"


def _download_preview(config: Config, gift: dict[str, Any]) -> str | None:
    """Превью стикера — к себе на сервер: в адресе файла Telegram токен бота, в HTML его быть не должно."""
    sticker = gift.get("sticker") or {}
    thumb = (sticker.get("thumbnail") or {}).get("file_id")
    if not thumb:
        return None
    folder = img_dir(config)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{''.join(ch for ch in str(gift['id']) if ch.isalnum())[:40]}.webp"
    path = folder / name
    if path.exists() and path.stat().st_size > 0:
        return name
    try:
        info = call(config, "getFile", file_id=thumb) or {}
        r = httpx.get(f"https://api.telegram.org/file/bot{config.gift_bot_token}/{info.get('file_path', '')}",
                      timeout=20)
        if r.status_code == 200 and 0 < len(r.content) < 2_000_000:
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(r.content)
            tmp.replace(path)
            return name
    except (NetError, ApiError, httpx.HTTPError, OSError) as exc:
        log.warning("превью подарка %s: %s", gift.get("id"), exc.__class__.__name__)
    return None


def sync(conn: sqlite3.Connection, config: Config, *, force: bool = False) -> int:
    """Каталог подарков из Telegram. Премиальные и распроданные — не показываем. Вернёт, сколько в продаже."""
    ensure(conn)
    if not enabled(config):
        return 0
    if not force and time.time() - float(db.get_setting(conn, "gifts.sync_ts") or 0) < SYNC_SECONDS:
        return -1
    db.set_setting(conn, "gifts.sync_ts", str(time.time()))
    try:
        gifts = (call(config, "getAvailableGifts") or {}).get("gifts") or []
    except (NetError, ApiError) as exc:
        log.warning("каталог подарков: %s", exc)
        return -1
    seen = []
    for i, g in enumerate(gifts):
        gid = str(g.get("id") or "")
        if not gid:
            continue
        seen.append(gid)
        sold_out = g.get("remaining_count") is not None and int(g["remaining_count"]) <= 0
        img = _download_preview(config, g)
        conn.execute(
            "INSERT INTO tg_gifts (id, star_count, emoji, remaining, total, premium, img, active, sort, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET star_count = excluded.star_count, "
            "emoji = excluded.emoji, remaining = excluded.remaining, total = excluded.total, "
            "premium = excluded.premium, img = COALESCE(excluded.img, tg_gifts.img), active = excluded.active, "
            "sort = excluded.sort, updated_at = excluded.updated_at",
            (gid, int(g.get("star_count") or 0), (g.get("sticker") or {}).get("emoji"), g.get("remaining_count"),
             g.get("total_count"), 1 if g.get("is_premium") else 0, img,
             0 if (sold_out or g.get("is_premium")) else 1, i, db.now()))
    if seen:
        conn.execute(f"UPDATE tg_gifts SET active = 0 WHERE id NOT IN ({','.join('?' * len(seen))})", seen)
    return conn.execute("SELECT COUNT(*) FROM tg_gifts WHERE active = 1 AND hidden = 0").fetchone()[0]


# ── Цены ─────────────────────────────────────────────────────


def settings(conn: sqlite3.Connection) -> dict[str, Decimal]:
    def num(key: str, default: str) -> Decimal:
        try:
            return Decimal(db.get_setting(conn, key) or default)
        except Exception:  # noqa: BLE001
            return Decimal(default)
    return {"markup_pct": num("gifts.markup_pct", "0"),        # сверх цены Stars на сайте
            "star_cost_usd": num("gifts.star_cost_usd", "0.013"),  # почём вам обходится 1 Star (для прибыли)
            "low_stars": num("gifts.low_stars", "100")}


def star_price_usd(conn: sqlite3.Connection, config: Config, user: Any) -> Decimal:
    """Цена 1 Star для покупателя — та же, что у Telegram Stars в каталоге (с его наценкой)."""
    from . import catalog
    from .money import apply_markup, to_decimal
    p = catalog.get_product(conn, "tg-stars")
    if p is None:
        return Decimal("0.016")
    markup = (accounts.markup_for(user, config, p["kind"]) if user is not None
              else config.kind_markups.get(p["kind"], config.markups["bronze"]))
    return apply_markup(to_decimal(p["base_price"]), markup)


def price_micro(conn: sqlite3.Connection, config: Config, user: Any, star_count: int) -> int:
    s = settings(conn)
    usd = star_price_usd(conn, config, user) * star_count * (1 + s["markup_pct"] / 100)
    return int((usd * 10_000).to_integral_value(rounding=ROUND_CEILING))


def listing(conn: sqlite3.Connection, config: Config, user: Any) -> list[dict[str, Any]]:
    ensure(conn)
    rows = conn.execute("SELECT * FROM tg_gifts WHERE active = 1 AND hidden = 0 ORDER BY star_count, sort").fetchall()
    return [{"id": r["id"], "stars": r["star_count"], "emoji": r["emoji"] or "🎁",
             "img": f"/tg/gift/{r['img']}" if r["img"] else "", "left": r["remaining"], "total": r["total"],
             "price_micro": price_micro(conn, config, user, r["star_count"])} for r in rows]


# ── Получатели ───────────────────────────────────────────────


def remember_user(conn: sqlite3.Connection, tg: dict[str, Any]) -> None:
    """Кто открыл бота или мини-приложение — запоминаем @ник → ID (по нику можно будет дарить сразу)."""
    ensure(conn)
    if not tg.get("id"):
        return
    conn.execute("INSERT INTO gift_users (tg_id, username, first_name, lang, updated_at) VALUES (?, ?, ?, ?, ?) "
                 "ON CONFLICT(tg_id) DO UPDATE SET username = excluded.username, first_name = excluded.first_name, "
                 "lang = excluded.lang, updated_at = excluded.updated_at",
                 (int(tg["id"]), (tg.get("username") or "").lower() or None, (tg.get("first_name") or "")[:64],
                  (tg.get("language_code") or "")[:8], db.now()))


def find_username(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    ensure(conn)
    name = username.strip().lstrip("@").lower()
    return conn.execute("SELECT * FROM gift_users WHERE username = ?", (name,)).fetchone() if name else None


# ── Заказ ────────────────────────────────────────────────────


class GiftError(Exception):
    pass


def buy(conn: sqlite3.Connection, config: Config, user: Any, gift_id: str, *, recipient_id: int | None = None,
        recipient: str = "", text: str = "") -> dict[str, Any]:
    """Купить подарок с баланса. recipient_id известен — сразу в очередь отправки, иначе — ссылка для друга."""
    ensure(conn)
    if not enabled(config):
        raise GiftError("Подарки сейчас недоступны.")
    g = conn.execute("SELECT * FROM tg_gifts WHERE id = ? AND active = 1 AND hidden = 0", (gift_id,)).fetchone()
    if g is None:
        raise GiftError("Этого подарка больше нет — выберите другой.")
    text = (text or "").strip()[:TEXT_MAX]
    price = price_micro(conn, config, user, g["star_count"])
    cost = int(settings(conn)["star_cost_usd"] * g["star_count"] * 10_000)
    token = secrets.token_hex(16)
    status = "paid" if recipient_id else "awaiting_recipient"
    now = db.now()
    with db.tx(conn):
        try:
            accounts.post_ledger(conn, user["id"], -price, f"Подарок Telegram ⭐{g['star_count']}")
        except accounts.InsufficientBalance:
            raise GiftError("На балансе не хватает денег — пополните баланс.") from None
        oid = int(conn.execute(
            "INSERT INTO gift_orders (user_id, gift_id, star_count, price_micro, cost_micro, recipient_id, recipient, "
            "text, link_token, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user["id"], g["id"], g["star_count"], price, cost, recipient_id, recipient[:64] or None, text or None,
             token, status, now, now)).lastrowid)
    return get(conn, oid)


def get(conn: sqlite3.Connection, oid: int) -> dict[str, Any]:
    r = conn.execute("SELECT o.*, g.emoji, g.img FROM gift_orders o LEFT JOIN tg_gifts g ON g.id = o.gift_id "
                     "WHERE o.id = ?", (oid,)).fetchone()
    return dict(r) if r else {}


def claim_link(conn: sqlite3.Connection, token: str, tg: dict[str, Any]) -> dict[str, Any] | None:
    """Получатель нажал Start по ссылке подарка — знаем его ID, подарок уходит в очередь отправки."""
    ensure(conn)
    remember_user(conn, tg)
    name = (tg.get("first_name") or "") + (f" (@{tg['username']})" if tg.get("username") else "")
    changed = conn.execute(
        "UPDATE gift_orders SET recipient_id = ?, recipient = COALESCE(recipient, ?), status = 'paid', updated_at = ? "
        "WHERE link_token = ? AND status = 'awaiting_recipient'",
        (int(tg["id"]), name[:64], db.now(), token)).rowcount
    row = conn.execute("SELECT id FROM gift_orders WHERE link_token = ?", (token,)).fetchone()
    return get(conn, row["id"]) | {"claimed": bool(changed)} if row else None


def refund(conn: sqlite3.Connection, oid: int, reason: str, *, status: str = "refunded",
           allowed: tuple[str, ...] = ("awaiting_recipient", "paid", "failed", "unknown")) -> bool:
    """Вернуть деньги на баланс покупателя. Один раз: статус меняется в той же транзакции."""
    with db.tx(conn):
        o = conn.execute("SELECT * FROM gift_orders WHERE id = ?", (oid,)).fetchone()
        if o is None or o["status"] not in allowed:
            return False
        if not conn.execute(f"UPDATE gift_orders SET status = ?, error = COALESCE(?, error), updated_at = ? "
                            f"WHERE id = ? AND status IN ({','.join('?' * len(allowed))})",
                            (status, reason, db.now(), oid, *allowed)).rowcount:
            return False
        accounts.post_ledger(conn, o["user_id"], o["price_micro"], f"Возврат: подарок Telegram #{oid}")
    return True


def retry(conn: sqlite3.Connection, oid: int) -> bool:
    return bool(conn.execute("UPDATE gift_orders SET status = 'paid', error = NULL, updated_at = ? "
                             "WHERE id = ? AND status IN ('failed', 'unknown') AND recipient_id IS NOT NULL",
                             (db.now(), oid)).rowcount)


# ── Отправка (воркер) ────────────────────────────────────────


def _alert(config: Config, text: str) -> None:
    from .worker import notify_admin
    notify_admin(config, f"🎁 Подарки: {text}")


def send_pending(conn: sqlite3.Connection, config: Config, limit: int = 10) -> int:
    """Оплаченные подарки → sendGift. Захват заказа атомарный (UPDATE … WHERE status='paid')."""
    ensure(conn)
    rows = conn.execute("SELECT * FROM gift_orders WHERE status = 'paid' AND recipient_id IS NOT NULL "
                        "ORDER BY id LIMIT ?", (limit,)).fetchall()
    if not rows:
        return 0
    balance = star_balance(config)
    if balance is None:
        return 0
    sent = 0
    for o in rows:
        if balance < o["star_count"]:
            _low_alert(conn, config, balance, need=o["star_count"])
            break   # Stars не хватает — заказы ждут, админ пополнит бота
        if not conn.execute("UPDATE gift_orders SET status = 'sending', sending_at = ?, updated_at = ? "
                            "WHERE id = ? AND status = 'paid'", (time.time(), db.now(), o["id"])).rowcount:
            continue   # забрал другой процесс
        try:
            call(config, "sendGift", user_id=int(o["recipient_id"]), gift_id=o["gift_id"], text=o["text"] or None)
        except ApiError as exc:
            if exc.code == 429:
                conn.execute("UPDATE gift_orders SET status = 'paid', updated_at = ? WHERE id = ?", (db.now(), o["id"]))
                break
            log.warning("подарок #%s: %s", o["id"], exc)
            refund(conn, o["id"], exc.description[:300], status="failed", allowed=("sending",))
            _alert(config, f"заказ #{o['id']} не отправлен ({exc.code}: {exc.description[:200]}). Деньги клиенту вернулись.")
            continue
        except NetError as exc:
            conn.execute("UPDATE gift_orders SET status = 'unknown', error = ?, updated_at = ? WHERE id = ?",
                         (f"нет ответа: {exc}", db.now(), o["id"]))
            continue
        conn.execute("UPDATE gift_orders SET status = 'sent', error = NULL, updated_at = ? WHERE id = ?",
                     (db.now(), o["id"]))
        balance -= o["star_count"]
        sent += 1
        _notify_sent(conn, config, o)
    _low_alert(conn, config, balance)
    return sent


def _notify_sent(conn: sqlite3.Connection, config: Config, o: sqlite3.Row) -> None:
    from .notify import notify
    try:
        notify(conn, config, o["user_id"], f"🎁 Подарок ⭐{o['star_count']} отправлен: {o['recipient'] or 'получателю'}.", "/tg")
    except Exception:  # noqa: BLE001 — уведомление не важнее отправки
        log.exception("уведомление о подарке")


def _low_alert(conn: sqlite3.Connection, config: Config, balance: int, need: int = 0) -> None:
    low = int(settings(conn)["low_stars"])
    if balance >= max(low, need):
        return
    if time.time() - float(db.get_setting(conn, "gifts.low_alert_ts") or 0) < LOW_ALERT_SECONDS:
        return
    db.set_setting(conn, "gifts.low_alert_ts", str(time.time()))
    _alert(config, f"на боте осталось ⭐{balance}" + (f", нужно ⭐{need} — заказы ждут" if need else "")
           + ". Пополните: напишите боту /topup 500")


# ── Сверка «неизвестно, ушёл ли» ─────────────────────────────


def _load_transactions(conn: sqlite3.Connection, config: Config) -> None:
    """История Stars бота идёт по порядку: читаем с запомненного места до конца, покупки подарков — в gift_tx."""
    offset = int(db.get_setting(conn, "gifts.tx_offset") or 0)
    for _ in range(20):
        try:
            res = call(config, "getStarTransactions", offset=offset, limit=100) or {}
        except (NetError, ApiError) as exc:
            log.warning("история Stars: %s", exc)
            return
        txs = res.get("transactions") or []
        for t in txs:
            rc = t.get("receiver") or {}
            if rc.get("type") == "user" and rc.get("transaction_type") == "gift_purchase":
                conn.execute("INSERT OR IGNORE INTO gift_tx (tx_id, user_id, gift_id, date) VALUES (?, ?, ?, ?)",
                             (str(t.get("id")), int((rc.get("user") or {}).get("id") or 0),
                              str((rc.get("gift") or {}).get("id") or ""), int(t.get("date") or 0)))
        offset += len(txs)
        db.set_setting(conn, "gifts.tx_offset", str(offset))
        if len(txs) < 100:
            return


def reconcile(conn: sqlite3.Connection, config: Config) -> int:
    ensure(conn)
    rows = conn.execute("SELECT * FROM gift_orders WHERE status IN ('unknown', 'sending') ORDER BY id").fetchall()
    stale_sending = [r for r in rows if r["status"] == "sending" and time.time() - (r["sending_at"] or 0) > 120]
    rows = [r for r in rows if r["status"] == "unknown"] + stale_sending   # «sending» дольше 2 минут — процесс упал
    if not rows:
        return 0
    _load_transactions(conn, config)
    fixed = 0
    for o in rows:
        since = int((o["sending_at"] or 0) - 60)
        tx = conn.execute("SELECT t.tx_id FROM gift_tx t LEFT JOIN gift_orders g ON g.tx_id = t.tx_id "
                          "WHERE t.user_id = ? AND t.gift_id = ? AND t.date >= ? AND g.id IS NULL ORDER BY t.date LIMIT 1",
                          (o["recipient_id"], o["gift_id"], since)).fetchone()
        if tx:
            conn.execute("UPDATE gift_orders SET status = 'sent', tx_id = ?, error = NULL, updated_at = ? WHERE id = ?",
                         (tx["tx_id"], db.now(), o["id"]))
            _notify_sent(conn, config, o)
            fixed += 1
        elif time.time() - (o["sending_at"] or 0) > UNKNOWN_MINUTES * 60:
            conn.execute("UPDATE gift_orders SET status = 'paid', updated_at = ? WHERE id = ?", (db.now(), o["id"]))
            _alert(config, f"заказ #{o['id']}: отправка не подтвердилась за {UNKNOWN_MINUTES} мин — отправим ещё раз.")
    return fixed


def expire(conn: sqlite3.Connection, config: Config) -> int:
    """Получатель так и не нажал Start — деньги покупателю."""
    ensure(conn)
    edge = datetime.fromtimestamp(time.time() - RECIPIENT_HOURS * 3600, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    n = 0
    for o in conn.execute("SELECT id FROM gift_orders WHERE status = 'awaiting_recipient' AND created_at < ?",
                          (edge,)).fetchall():
        n += refund(conn, o["id"], "получатель не открыл бота", status="refunded", allowed=("awaiting_recipient",))
    return n


def tick(conn: sqlite3.Connection, config: Config) -> None:
    """Из воркера: каталог, отправка, сверка, возвраты."""
    if not enabled(config):
        return
    for step in (lambda: sync(conn, config), lambda: send_pending(conn, config),
                 lambda: reconcile(conn, config), lambda: expire(conn, config)):
        try:
            step()
        except Exception:  # noqa: BLE001 — один шаг не должен останавливать остальные
            log.exception("подарки")


# ── Для админки и профиля ────────────────────────────────────

STATUS_TITLES = {"awaiting_recipient": "ждём получателя", "paid": "в очереди", "sending": "отправляется",
                 "sent": "отправлен", "unknown": "проверяем", "failed": "ошибка, деньги вернулись",
                 "refunded": "возврат"}


def orders(conn: sqlite3.Connection, *, status: str = "", user_id: int | None = None, limit: int = 100) -> list[dict]:
    ensure(conn)
    where, args = "1=1", []
    if status:
        where += " AND o.status = ?"
        args.append(status)
    if user_id is not None:
        where += " AND o.user_id = ?"
        args.append(user_id)
    rows = conn.execute(f"SELECT o.*, g.emoji, g.img, u.login FROM gift_orders o LEFT JOIN tg_gifts g ON g.id = o.gift_id "
                        f"LEFT JOIN users u ON u.id = o.user_id WHERE {where} ORDER BY o.id DESC LIMIT ?",
                        (*args, limit)).fetchall()
    return [dict(r) | {"status_title": STATUS_TITLES.get(r["status"], r["status"])} for r in rows]


def save_settings(conn: sqlite3.Connection, markup_pct: str, star_cost_usd: str, low_stars: str) -> None:
    for key, raw, lo, hi in (("gifts.markup_pct", markup_pct, 0, 200), ("gifts.star_cost_usd", star_cost_usd, 0, 1),
                             ("gifts.low_stars", low_stars, 0, 1_000_000)):
        try:
            v = Decimal(raw.replace(",", ".").strip())
        except Exception:  # noqa: BLE001
            raise ValueError("Числа — цифрами.") from None
        if not lo <= v <= hi:
            raise ValueError(f"Значение вне границ: {raw}")
        db.set_setting(conn, key, str(v))


def payload_topup(n: int) -> str:
    return json.dumps({"t": "topup", "n": n})

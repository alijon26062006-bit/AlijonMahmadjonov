"""D-коин — бонусная монета Donatix. Всё зависит только от покупок.

Как устроено и почему сайт никогда не уходит в минус:
  • Монеты. За каждый выполненный заказ клиент получает D-коины ровно по сумме заказа:
    100 D за $1, за $0.50 — 50 D.
  • Копилка. С того же заказа в копилку идёт часть НАШЕЙ ПРИБЫЛИ с него: обычный заказ — 10%,
    заказ крупнее обычного — больше (до 20%), мельче — меньше (от 5%). «Обычный» — средний
    заказ за последние сутки. Заказ без прибыли копилку не пополняет.
  • Цена 1 D = копилка ÷ все монеты у людей. Крупная покупка поднимает цену (зелёная свеча),
    мелкая опускает (красная), без покупок цена стоит. Одна покупка сдвигает цену не больше
    чем на 3%: рост сильнее — в копилку идёт меньше, падение сильнее — чуть больше (в пределах
    потолка), поэтому график идёт мягко. Ничего не подкручено: цена — это
    ровно те деньги, что лежат в копилке.
  • Обмен на баланс сайта по цене минус 5%: эти 5% остаются в копилке, и цена для остальных
    растёт. Больше, чем лежит в копилке, забрать невозможно, поэтому сайт отдаёт максимум
    20% прибыли заказа (в среднем около 10%), остальное всегда наше.
"""

from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from . import accounts, db

UNIT = 100                        # монеты храним в сотых долях
DEFAULT_PER_USD = 100             # D за $1 в самом начале
DEFAULT_POOL_PCT = 10             # % прибыли обычного заказа — в копилку
MIN_SHARE, MAX_SHARE = 0.5, 2.0   # мелкий заказ — ×0.5 (5%), крупный — ×2 (20%)
MAX_STEP = 0.03                   # одна покупка двигает цену не больше чем на 3% — график мягкий
DEFAULT_OPEN_DAYS = 30            # обмен открывается через месяц после запуска
EXCHANGE_FEE_PCT = 5              # остаются в копилке — цена растёт для остальных
MIN_EXCHANGE = 10_000             # от $1 (микро-доллары)
TIMEFRAMES = {"1s": 1, "5s": 5, "1m": 60, "5m": 300, "15m": 900, "1h": 3600, "1d": 86400}
CANDLES = 80


# ── Настройки ───────────────────────────────────────────────────
def _int_setting(conn: sqlite3.Connection, key: str, default: int, lo: int, hi: int) -> int:
    raw = db.get_setting(conn, key)
    try:
        return max(lo, min(hi, int(raw))) if raw not in (None, "") else default
    except ValueError:
        return default


def per_usd(conn: sqlite3.Connection) -> int:
    return _int_setting(conn, "dcoin.per_usd", DEFAULT_PER_USD, 0, 10_000)


def pool_pct(conn: sqlite3.Connection) -> int:
    return _int_setting(conn, "dcoin.pool_pct", DEFAULT_POOL_PCT, 0, 25)


def open_days(conn: sqlite3.Connection) -> int:
    return _int_setting(conn, "dcoin.open_days", DEFAULT_OPEN_DAYS, 0, 365)


def enabled(conn: sqlite3.Connection) -> bool:
    return per_usd(conn) > 0 and pool_pct(conn) > 0


def started_at(conn: sqlite3.Connection) -> datetime:
    raw = db.get_setting(conn, "dcoin.started_at")
    if not raw:
        raw = db.now()
        db.set_setting(conn, "dcoin.started_at", raw)
    return _parse(raw)


def exchange_opens(conn: sqlite3.Connection) -> datetime:
    return started_at(conn) + timedelta(days=open_days(conn))


def exchange_open(conn: sqlite3.Connection, now: datetime | None = None) -> bool:
    return (now or _now()) >= exchange_opens(conn)


# ── Время и формат ──────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def fmt_d(units: int) -> str:
    """Сотые доли → «12 345.67»."""
    sign = "-" if units < 0 else ""
    units = abs(int(units))
    return f"{sign}{units // UNIT:,}".replace(",", " ") + f".{units % UNIT:02d}"


# ── Копилка и монеты ────────────────────────────────────────────
def state(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute("SELECT pool, supply FROM dcoin_points ORDER BY id DESC LIMIT 1").fetchone()
    return {"pool": int(row["pool"]), "supply": int(row["supply"])} if row else {"pool": 0, "supply": 0}


def price_of(pool: int, supply: int) -> float:
    """$ за 1 D. pool — микро-доллары, supply — сотые доли монеты. До первой покупки — 0."""
    return (pool / 10_000) / (supply / UNIT) if supply > 0 else 0.0


def price(conn: sqlite3.Connection) -> float:
    s = state(conn)
    return price_of(s["pool"], s["supply"])


def _point(conn: sqlite3.Connection, pool: int, supply: int, reason: str, when: str | None = None) -> None:
    conn.execute("INSERT INTO dcoin_points (ts, pool, supply, price, reason) VALUES (?, ?, ?, ?, ?)",
                 (when or db.now(), pool, supply, price_of(pool, supply), reason))


def reward_units(conn: sqlite3.Connection, usd: float) -> int:
    """Сколько монет (сотые) дать за покупку на usd: 100 D за $1, за $0.50 — 50 D."""
    return int(usd * per_usd(conn) * UNIT)


def share_factor(conn: sqlite3.Connection, usd: float, order_id: int) -> float:
    """Крупнее обычного — больше в копилку, мельче — меньше. Обычный = средний заказ за сутки."""
    since = _iso(_now() - timedelta(days=1))
    row = conn.execute("SELECT AVG(total_micro) FROM orders WHERE status = 'completed' AND id != ? "
                       "AND COALESCE(completed_at, created_at) >= ?", (order_id, since)).fetchone()
    usual = (row[0] or 0) / 10_000
    if usual <= 0 or usd <= 0:
        return 1.0
    return max(MIN_SHARE, min(MAX_SHARE, math.sqrt(usd / usual)))


def award(conn: sqlite3.Connection, order_id: int) -> int:
    """За выполненный заказ: монеты клиенту и часть прибыли в копилку. Один раз за заказ.
    Возвращает начисленные монеты (сотые) или 0."""
    if not enabled(conn):
        return 0
    row = conn.execute("SELECT id, public_id, user_id, total_micro, cost_micro, status FROM orders WHERE id = ?",
                       (order_id,)).fetchone()
    if row is None or row["status"] != "completed" or row["total_micro"] <= 0:
        return 0
    if conn.execute("SELECT 1 FROM dcoin_ledger WHERE order_id = ?", (order_id,)).fetchone():
        return 0
    started_at(conn)
    usd = row["total_micro"] / 10_000
    cur = state(conn)
    units = reward_units(conn, usd)
    if units <= 0:
        return 0
    profit = max(0, int(row["total_micro"]) - int(row["cost_micro"] or 0))
    to_pool = int(profit * pool_pct(conn) / 100 * share_factor(conn, usd, order_id))
    cap = profit * pool_pct(conn) * 2 // 100                      # никогда больше 2× процента прибыли
    to_pool = smooth(cur["pool"], cur["supply"], units, min(to_pool, cap), cap)
    added = conn.execute(
        "INSERT OR IGNORE INTO dcoin_ledger (user_id, amount, pool_micro, reason, order_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (row["user_id"], units, to_pool, f"Заказ {row['public_id']}", order_id, db.now())).rowcount
    if not added:
        return 0
    conn.execute("UPDATE users SET dcoin = dcoin + ? WHERE id = ?", (units, row["user_id"]))
    _point(conn, cur["pool"] + to_pool, cur["supply"] + units, "buy")
    return units


def smooth(pool: int, supply: int, units: int, to_pool: int, cap: int) -> int:
    """Мягкий график: одна покупка двигает цену не больше чем на ±MAX_STEP.
    Рост сильнее — в копилку кладём меньше (экономия сайта); падение сильнее — добавляем,
    но не больше cap (потолок доли прибыли), так что минуса не бывает."""
    if pool <= 0 or supply <= 0:
        return to_pool                                  # первая покупка задаёт стартовую цену
    total = supply + units
    hi = int(pool * (1 + MAX_STEP) * total / supply) - pool
    lo = math.ceil(pool * (1 - MAX_STEP) * total / supply) - pool
    if to_pool > hi:
        return max(0, hi)
    if to_pool < lo:
        return max(to_pool, min(lo, cap))
    return to_pool


class ExchangeError(Exception):
    pass


def quote(conn: sqlite3.Connection, units: int) -> int:
    """Сколько микро-долларов дадут за units монет сейчас (с комиссией, округление в пользу копилки)."""
    s = state(conn)
    if units <= 0 or s["supply"] <= 0:
        return 0
    return units * s["pool"] * (100 - EXCHANGE_FEE_PCT) // (s["supply"] * 100)


def exchange(conn: sqlite3.Connection, user_id: int, units: int, now: datetime | None = None) -> int:
    """Обменять монеты на баланс сайта. Возвращает зачисленное (микро)."""
    now = now or _now()
    if not exchange_open(conn, now):
        raise ExchangeError(f"Обмен откроется {exchange_opens(conn):%d.%m.%Y} — пока копим, цена растёт.")
    with db.tx(conn):
        row = conn.execute("SELECT dcoin FROM users WHERE id = ?", (user_id,)).fetchone()
        have = int(row["dcoin"]) if row else 0
        if units <= 0 or units > have:
            raise ExchangeError("Столько D-коинов у вас нет.")
        last = conn.execute("SELECT created_at FROM dcoin_ledger WHERE user_id = ? AND amount < 0 "
                            "ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
        if last and now - _parse(last["created_at"]) < timedelta(hours=24):
            raise ExchangeError("Обменивать можно раз в сутки.")
        s = state(conn)
        pay = quote(conn, units)
        if pay < MIN_EXCHANGE:
            raise ExchangeError("Обмен — от $1 по текущей цене.")
        if pay > s["pool"]:   # не бывает при цене = копилка ÷ монеты, но защищаемся
            raise ExchangeError("Сейчас столько обменять нельзя.")
        conn.execute("UPDATE users SET dcoin = dcoin - ? WHERE id = ?", (units, user_id))
        conn.execute("INSERT INTO dcoin_ledger (user_id, amount, pool_micro, reason, created_at) "
                     "VALUES (?, ?, ?, ?, ?)", (user_id, -units, -pay, "Обмен на баланс", _iso(now)))
        _point(conn, s["pool"] - pay, s["supply"] - units, "exchange")
        accounts.post_ledger(conn, user_id, pay, f"Обмен {fmt_d(units)} D-коинов на баланс")
    return pay


# ── График: свечи ───────────────────────────────────────────────
def candles(conn: sqlite3.Connection, tf: str = "5m", now: datetime | None = None) -> dict[str, Any]:
    """Свечи [время_мс, открытие, максимум, минимум, закрытие] за последние CANDLES интервалов.
    Пустой интервал — ровная свеча по последней цене."""
    tf = tf if tf in TIMEFRAMES else "5m"
    step = TIMEFRAMES[tf]
    now = now or _now()
    end = int(now.timestamp()) // step * step
    start = end - (CANDLES - 1) * step
    since = datetime.fromtimestamp(start, timezone.utc)
    before = conn.execute("SELECT price FROM dcoin_points WHERE ts < ? ORDER BY id DESC LIMIT 1",
                          (_iso(since),)).fetchone()
    last = float(before["price"]) if before else 0.0
    rows = conn.execute("SELECT ts, price FROM dcoin_points WHERE ts >= ? ORDER BY id", (_iso(since),)).fetchall()
    buckets: dict[int, list[float]] = {}
    for r in rows:
        t = int(_parse(r["ts"]).timestamp()) // step * step
        buckets.setdefault(t, []).append(float(r["price"]))
    out = []
    for t in range(start, end + step, step):
        vals = buckets.get(t, [])
        o = last
        c = vals[-1] if vals else last
        out.append([t * 1000, o, max([o, *vals]), min([o, *vals]), c])
        last = c
    return {"tf": tf, "step": step, "candles": out}


def change_24h(conn: sqlite3.Connection) -> float:
    since = _iso(_now() - timedelta(days=1))
    row = conn.execute("SELECT price FROM dcoin_points WHERE ts < ? ORDER BY id DESC LIMIT 1", (since,)).fetchone()
    if row is None:
        row = conn.execute("SELECT price FROM dcoin_points ORDER BY id LIMIT 1").fetchone()
    first, now_p = (float(row["price"]) if row else 0.0), price(conn)
    if first <= 0:
        return 0.0
    return round((now_p - first) / first * 100, 2)


# ── Для страниц ─────────────────────────────────────────────────
def balance(conn: sqlite3.Connection, user_id: int) -> int:
    row = conn.execute("SELECT dcoin FROM users WHERE id = ?", (user_id,)).fetchone()
    return int(row["dcoin"]) if row else 0


def summary(conn: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    bal = balance(conn, user_id)
    s = state(conn)
    return {"balance": bal, "balance_text": fmt_d(bal), "worth_micro": quote(conn, bal),
            "price": price_of(s["pool"], s["supply"]), "change": change_24h(conn),
            "per_usd": per_usd(conn), "pool_pct": pool_pct(conn),
            "fee_pct": EXCHANGE_FEE_PCT, "open": exchange_open(conn), "opens": exchange_opens(conn),
            "enabled": enabled(conn)}


def history(conn: sqlite3.Connection, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    return [{"amount": fmt_d(r["amount"]), "plus": r["amount"] > 0, "reason": r["reason"],
             "created_at": r["created_at"]}
            for r in conn.execute("SELECT amount, reason, created_at FROM dcoin_ledger WHERE user_id = ? "
                                  "ORDER BY id DESC LIMIT ?", (user_id, limit))]


def top(conn: sqlite3.Connection, limit: int = 10) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT login, dcoin FROM users WHERE dcoin > 0 ORDER BY dcoin DESC, id LIMIT ?",
                        (limit,)).fetchall()
    return [{"login": (r["login"][:2] + "•••" + r["login"][-1:]) if len(r["login"]) > 3 else r["login"],
             "coins": fmt_d(r["dcoin"])} for r in rows]


def pool_added(conn: sqlite3.Connection, a: str, b: str) -> int:
    """Сколько прибыли ушло в копилку за [a, b) — для отчёта о финансах."""
    return int(conn.execute("SELECT COALESCE(SUM(pool_micro), 0) FROM dcoin_ledger WHERE pool_micro > 0 "
                            "AND created_at >= ? AND created_at < ?", (a, b)).fetchone()[0])

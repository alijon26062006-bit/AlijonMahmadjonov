"""Несколько карт на один банк: каждому клиенту — своя карта, суммы по картам ровные, чек — хозяину карты.

Как работает:
- у банка (способа оплаты, например «Душанбе Сити» или «Алиф») может быть несколько карт; у каждой — хозяин:
  кассир (его Telegram ID) или владелец магазина (0);
- клиент открывает пополнение → ему показывается карта, на которую СЕГОДНЯ пришло меньше всего денег
  (с учётом ещё не оплаченных заявок); при равенстве — случайная. Так за день у всех карт почти одинаковые суммы;
- выбранная карта держится за клиентом 2 часа (форма → заявка → чек — одна и та же карта) и записывается в заявку;
- чек приходит ТОЛЬКО хозяину этой карты (владельцу — в админ-чат, кассиру — ему одному);
- ИИ читает в чеке номер получателя: клиент по привычке перевёл на другую нашу карту — заявка сама уходит
  хозяину ТОЙ карты, и сумма засчитывается ей.
Нет ни одной включённой карты у банка — всё как раньше: реквизиты из настроек способа и кассиры по банкам.
"""

from __future__ import annotations

import random
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db

HOLD_HOURS = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS pay_cards (
    id         INTEGER PRIMARY KEY,
    method     TEXT NOT NULL,
    details    TEXT NOT NULL,
    owner_tg   INTEGER NOT NULL DEFAULT 0,
    active     INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pay_card_hold (
    user_id INTEGER NOT NULL,
    method  TEXT NOT NULL,
    card_id INTEGER NOT NULL,
    at      TEXT NOT NULL,
    PRIMARY KEY (user_id, method)
);
"""


class CardError(ValueError):
    pass


def ensure(conn: sqlite3.Connection) -> None:
    # executescript сам закрывает открытую транзакцию — поэтому только если таблиц ещё нет (обычно их создаёт db.init)
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'pay_card_hold'").fetchone():
        conn.executescript(SCHEMA)
    if "card_id" not in {r[1] for r in conn.execute("PRAGMA table_info(payments)")}:
        conn.execute("ALTER TABLE payments ADD COLUMN card_id INTEGER")


# ── список карт (админка) ──

def listing(conn: sqlite3.Connection, method: str = "") -> list[sqlite3.Row]:
    ensure(conn)
    if method:
        return conn.execute("SELECT * FROM pay_cards WHERE method = ? ORDER BY id", (method,)).fetchall()
    return conn.execute("SELECT * FROM pay_cards ORDER BY method, id").fetchall()


def get(conn: sqlite3.Connection, card_id: int | None) -> sqlite3.Row | None:
    if not card_id:
        return None
    ensure(conn)
    return conn.execute("SELECT * FROM pay_cards WHERE id = ?", (int(card_id),)).fetchone()


def numbers(details: str) -> list[str]:
    """Номера в реквизитах: карты (16–19 цифр), счета и телефоны (от 9 цифр)."""
    return [d for d in (re.sub(r"\D", "", m) for m in re.findall(r"\+?\d[\d \-]{7,}\d", details or "")) if len(d) >= 9]


def add(conn: sqlite3.Connection, method: str, details: str, owner_tg: int = 0) -> int:
    ensure(conn)
    details = (details or "").strip()[:500]
    if not method:
        raise CardError("Выберите банк.")
    if not numbers(details):
        raise CardError("В реквизитах нет номера карты или телефона.")
    return int(conn.execute("INSERT INTO pay_cards (method, details, owner_tg, active, created_at) VALUES (?, ?, ?, 1, ?)",
                            (method, details, int(owner_tg or 0), db.now())).lastrowid)


def set_active(conn: sqlite3.Connection, card_id: int, on: bool) -> None:
    ensure(conn)
    conn.execute("UPDATE pay_cards SET active = ? WHERE id = ?", (1 if on else 0, card_id))
    if not on:
        conn.execute("DELETE FROM pay_card_hold WHERE card_id = ?", (card_id,))


def delete(conn: sqlite3.Connection, card_id: int) -> None:
    ensure(conn)
    conn.execute("DELETE FROM pay_card_hold WHERE card_id = ?", (card_id,))
    conn.execute("DELETE FROM pay_cards WHERE id = ?", (card_id,))


# ── какую карту показать ──

def _day_start(tz_offset: int) -> str:
    now = datetime.now(timezone.utc) + timedelta(hours=tz_offset)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(hours=tz_offset)
    return start.strftime("%Y-%m-%dT%H:%M:%S")


def load(conn: sqlite3.Connection, card_id: int, tz_offset: int = 5) -> int:
    """Сколько пришло на карту сегодня + сколько ждёт оплаты (за последние 2 часа), в micro-USD."""
    ensure(conn)
    since = _day_start(tz_offset)
    recent = (datetime.now(timezone.utc) - timedelta(hours=HOLD_HOURS)).strftime("%Y-%m-%dT%H:%M:%S")
    return int(conn.execute(
        "SELECT COALESCE(SUM(amount_micro), 0) FROM payments WHERE card_id = ? AND ("
        "(status = 'paid' AND resolved_at >= ?) OR (status = 'pending' AND created_at >= ?))",
        (card_id, since, recent)).fetchone()[0])


def rest_on(conn: sqlite3.Connection) -> bool:
    """Отдых карт: у банка с 2+ картами каждый день одна карта не показывается (по кругу). Выключается в админке."""
    return db.get_setting(conn, "cards.rest", "1") == "1"


def resting_id(conn: sqlite3.Connection, method: str, tz_offset: int = 5) -> int:
    """Какая карта этого банка сегодня отдыхает: включённые карты по порядку, сегодня — следующая по кругу.
    Меньше двух карт — не отдыхает никто (иначе клиенту нечего показать)."""
    ensure(conn)
    if not rest_on(conn):
        return 0
    ids = [r[0] for r in conn.execute("SELECT id FROM pay_cards WHERE method = ? AND active = 1 ORDER BY id", (method,))]
    if len(ids) < 2:
        return 0
    day = (datetime.now(timezone.utc) + timedelta(hours=tz_offset)).date().toordinal()
    return ids[day % len(ids)]


def pick(conn: sqlite3.Connection, user_id: int, method: str, tz_offset: int = 5) -> sqlite3.Row | None:
    """Карта для этого клиента и банка: держим прежнюю 2 часа, иначе — та, на которую сегодня пришло меньше.
    Отдыхающую сегодня карту не показываем никому."""
    ensure(conn)
    rest = resting_id(conn, method, tz_offset)
    cards = [c for c in conn.execute("SELECT * FROM pay_cards WHERE method = ? AND active = 1", (method,)).fetchall()
             if c["id"] != rest]
    if not cards:
        return None
    fresh = (datetime.now(timezone.utc) - timedelta(hours=HOLD_HOURS)).strftime("%Y-%m-%dT%H:%M:%S")
    if user_id:
        held = conn.execute("SELECT card_id FROM pay_card_hold WHERE user_id = ? AND method = ? AND at >= ?",
                            (user_id, method, fresh)).fetchone()
        if held:
            card = next((c for c in cards if c["id"] == held["card_id"]), None)
            if card is not None:
                return card
    loads = {c["id"]: load(conn, c["id"], tz_offset) for c in cards}
    low = min(loads.values())
    card = random.choice([c for c in cards if loads[c["id"]] == low])
    if user_id:
        conn.execute("INSERT INTO pay_card_hold (user_id, method, card_id, at) VALUES (?, ?, ?, ?) "
                     "ON CONFLICT(user_id, method) DO UPDATE SET card_id = excluded.card_id, at = excluded.at",
                     (user_id, method, card["id"], db.now()))
    return card


def details_for(conn: sqlite3.Connection, user_id: int, method: str, default: str, tz_offset: int = 5) -> str:
    card = pick(conn, user_id, method, tz_offset)
    return card["details"] if card else default


def all_details(conn: sqlite3.Connection, method: str, default: str = "") -> str:
    """Все наши реквизиты этого банка одной строкой — для ИИ: «получатель наш?» сверяется с любой нашей картой."""
    ensure(conn)
    rows = conn.execute("SELECT details FROM pay_cards WHERE method = ?", (method,)).fetchall()
    return "\n".join([default] + [r["details"] for r in rows]).strip()


def match(conn: sqlite3.Connection, recipient: str) -> sqlite3.Row | None:
    """Наша карта по номеру получателя из чека: совпадение последних 4 цифр (карта) или телефона/счёта целиком.
    Подходит несколько карт — не гадаем (None)."""
    ensure(conn)
    seen = re.sub(r"\D", "", recipient or "")
    if len(seen) < 4:
        return None
    found = []
    for c in conn.execute("SELECT * FROM pay_cards").fetchall():
        for num in numbers(c["details"]):
            if (len(seen) >= 9 and (num.endswith(seen[-9:]) or seen.endswith(num[-9:]))) or \
               (len(num) >= 16 and seen[-4:] == num[-4:]):
                found.append(c)
                break
    return found[0] if len(found) == 1 else None


def reroute(conn: sqlite3.Connection, payment_id: int, recipient: str) -> str:
    """Клиент перевёл не на показанную карту, а на другую нашу — переписываем заявку на ту карту.
    Возвращает пометку для чека (или пустую строку)."""
    p = conn.execute("SELECT card_id FROM payments WHERE id = ?", (payment_id,)).fetchone()
    if p is None or not p["card_id"]:
        return ""
    real = match(conn, recipient)
    if real is None or real["id"] == p["card_id"]:
        return ""
    shown = get(conn, p["card_id"])
    conn.execute("UPDATE payments SET card_id = ? WHERE id = ?", (real["id"], payment_id))
    return (f"↪️ Клиент перевёл на карту ****{tail(real)} вместо показанной ****{tail(shown)} — "
            f"заявка у хозяина карты ****{tail(real)}" if shown else "")


def tail(card: sqlite3.Row) -> str:
    return (numbers(card["details"]) or ["????"])[0][-4:]


def report(conn: sqlite3.Connection, tz_offset: int = 5) -> list[dict[str, Any]]:
    """Для админки: по каждой карте — чья, сколько заявок и денег сегодня."""
    ensure(conn)
    since = _day_start(tz_offset)
    out = []
    resting = {m: resting_id(conn, m, tz_offset) for m in {c["method"] for c in listing(conn)}}
    for c in listing(conn):
        r = conn.execute("SELECT COUNT(*) AS n, COALESCE(SUM(amount_micro), 0) AS s FROM payments "
                         "WHERE card_id = ? AND status = 'paid' AND resolved_at >= ?", (c["id"], since)).fetchone()
        owner = "" if not c["owner_tg"] else (conn.execute("SELECT name FROM cashiers WHERE tg_id = ?",
                                                           (c["owner_tg"],)).fetchone() or {"name": str(c["owner_tg"])})["name"]
        out.append({**dict(c), "tail": tail(c), "owner_name": owner or "Вы (владелец)", "today_n": r["n"], "today_micro": r["s"],
                    "resting": resting.get(c["method"]) == c["id"]})
    return out

"""Гонка в мини-приложении Telegram: до 6 машин, живые игроки + боты на свободных местах.

Как устроено. Игрок жмёт «Старт» → попадает в комнату, которая стартует через несколько секунд
(или в уже набирающуюся). Каждый телефон сам считает свою машину и 4 раза в секунду сообщает серверу,
где она (tick); сервер раздаёт позиции остальных. Боты и препятствия считаются из «зерна» комнаты по
одной формуле на всех телефонах и на сервере — поэтому все видят одно и то же.

Правила заезда (на телефоне): врезался сзади в машину — теряешь скорость ты; препятствие на дороге —
резкое торможение; нитро — короткий разгон, 3 заряда.

Деньги не участвуют: за места дают игровые монеты (лимит в день), на них меняют цвет машины.
Монеты — не D-коин и не баланс: их нельзя вывести или продать, поэтому накрутка ничего не стоит магазину.
Сервер проверяет финиш: время не меньше физически возможного и сходится с часами сервера.
"""

from __future__ import annotations

import json
import random
import sqlite3
import time
from typing import Any

TRACK = 2400.0            # длина трассы, игровых метров
VMAX = 52.0               # обычная максимальная скорость, м/с
VNITRO = 78.0             # с нитро
MAX_CARS = 6
WAIT = 8.0                # сколько комната ждёт игроков до старта, сек
JOIN_GAP = 2.5            # за сколько до старта в комнату уже не пускаем
MIN_MS = int(TRACK / VNITRO * 1000)        # быстрее проехать нельзя даже на одном нитро
PRIZES = {1: 10, 2: 5, 3: 3}
DAY_CAP = 30              # монет в день со всех заездов
ONLINE_SEC = 25
#: Цвета машины: код → (название ru, название tj, цвет краски или None для заводского, цена в монетах)
COLORS: dict[str, tuple[str, str, str | None, int]] = {
    "violet": ("Фиолетовый", "Бунафш", None, 0),
    "red": ("Красный", "Сурх", "#e3262d", 20),
    "blue": ("Синий", "Кабуд", "#1f6bff", 20),
    "green": ("Зелёный", "Сабз", "#18b86a", 30),
    "orange": ("Оранжевый", "Норинҷӣ", "#ff7a1a", 30),
    "white": ("Белый", "Сафед", "#f2f4f8", 40),
    "black": ("Чёрный", "Сиёҳ", "#23242b", 40),
    "gold": ("Золотой", "Тиллоӣ", "#f2b318", 80),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS race_rooms (
    id        INTEGER PRIMARY KEY,
    seed      INTEGER NOT NULL,
    start_at  REAL NOT NULL,
    created   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS race_players (
    room_id   INTEGER NOT NULL,
    user_id   INTEGER NOT NULL,
    name      TEXT NOT NULL,
    color     TEXT NOT NULL,
    z         REAL NOT NULL DEFAULT 0,
    x         REAL NOT NULL DEFAULT 0,
    v         REAL NOT NULL DEFAULT 0,
    fin_ms    INTEGER,
    place     INTEGER,
    upd       REAL NOT NULL,
    PRIMARY KEY (room_id, user_id)
);
CREATE INDEX IF NOT EXISTS race_players_upd ON race_players(upd);
CREATE TABLE IF NOT EXISTS race_wallet (
    user_id   INTEGER PRIMARY KEY,
    name      TEXT NOT NULL DEFAULT '',
    coins     INTEGER NOT NULL DEFAULT 0,
    wins      INTEGER NOT NULL DEFAULT 0,
    races     INTEGER NOT NULL DEFAULT 0,
    day       TEXT NOT NULL DEFAULT '',
    day_coins INTEGER NOT NULL DEFAULT 0,
    color     TEXT NOT NULL DEFAULT 'violet',
    owned     TEXT NOT NULL DEFAULT '["violet"]'
);
"""


class RaceError(Exception):
    pass


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def rnd(seed: int, i: int) -> float:
    """Случайное число 0..1 из зерна — та же формула в игре (JS), поэтому боты у всех одинаковые."""
    m = 0xFFFFFFFF
    x = (seed ^ ((i * 374761393) & m)) & m
    x = ((x ^ (x >> 15)) * 2246822519) & m
    x = ((x ^ (x >> 13)) * 3266489917) & m
    x = (x ^ (x >> 16)) & m
    return x / 4294967296


def bot_speed(seed: int, i: int) -> float:
    return 41.0 + rnd(seed, i) * 7.5        # 41–48.5 м/с: внимательный игрок обгонит, невнимательный — нет


def bot_finish_ms(seed: int, i: int) -> int:
    """Бот разгоняется 3 секунды, дальше едет ровно: z = v·(t − 1.5) → финиш = длина/v + 1.5 с."""
    return int((TRACK / bot_speed(seed, i) + 1.5) * 1000)


def _today(tz_offset: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() + tz_offset * 3600))


def wallet(conn: sqlite3.Connection, user_id: int, name: str = "", tz_offset: int = 5) -> dict[str, Any]:
    init(conn)
    conn.execute("INSERT OR IGNORE INTO race_wallet (user_id, name) VALUES (?, ?)", (user_id, name[:32]))
    if name:
        conn.execute("UPDATE race_wallet SET name = ? WHERE user_id = ? AND name != ?", (name[:32], user_id, name[:32]))
    w = dict(conn.execute("SELECT * FROM race_wallet WHERE user_id = ?", (user_id,)).fetchone())
    try:
        w["owned"] = [c for c in json.loads(w["owned"]) if c in COLORS] or ["violet"]
    except ValueError:
        w["owned"] = ["violet"]
    if w["color"] not in w["owned"]:
        w["color"] = "violet"
    w["day_left"] = DAY_CAP - (w["day_coins"] if w["day"] == _today(tz_offset) else 0)
    return w


def online(conn: sqlite3.Connection) -> int:
    init(conn)
    return conn.execute("SELECT COUNT(DISTINCT user_id) FROM race_players WHERE upd > ?",
                        (time.time() - ONLINE_SEC,)).fetchone()[0]


def profile(conn: sqlite3.Connection, user_id: int, name: str, tz_offset: int = 5) -> dict[str, Any]:
    w = wallet(conn, user_id, name, tz_offset)
    return {"coins": w["coins"], "wins": w["wins"], "races": w["races"], "color": w["color"], "owned": w["owned"],
            "day_left": max(0, w["day_left"]), "day_cap": DAY_CAP, "online": online(conn),
            "colors": [{"code": c, "ru": ru, "tj": tj, "hex": hx, "price": price} for c, (ru, tj, hx, price) in COLORS.items()],
            "prizes": PRIZES, "track": TRACK, "vmax": VMAX, "vnitro": VNITRO, "max_cars": MAX_CARS}


def _players(conn: sqlite3.Connection, room_id: int) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(
        "SELECT user_id, name, color, z, x, v, fin_ms, place FROM race_players WHERE room_id = ? ORDER BY user_id",
        (room_id,))]


def join(conn: sqlite3.Connection, user_id: int, name: str, tz_offset: int = 5) -> dict[str, Any]:
    """В набирающуюся комнату или в новую. Возвращает зерно, время до старта и игроков."""
    init(conn)
    w = wallet(conn, user_id, name, tz_offset)
    now = time.time()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("DELETE FROM race_players WHERE room_id IN (SELECT id FROM race_rooms WHERE created < ?)", (now - 3600,))
        conn.execute("DELETE FROM race_rooms WHERE created < ?", (now - 3600,))
        room = conn.execute(
            "SELECT r.* FROM race_rooms r WHERE r.start_at > ? AND (SELECT COUNT(*) FROM race_players p "
            "WHERE p.room_id = r.id) < ? AND NOT EXISTS (SELECT 1 FROM race_players p WHERE p.room_id = r.id "
            "AND p.user_id = ?) ORDER BY r.start_at LIMIT 1", (now + JOIN_GAP, MAX_CARS, user_id)).fetchone()
        if room is None:
            rid = conn.execute("INSERT INTO race_rooms (seed, start_at, created) VALUES (?, ?, ?)",
                               (random.getrandbits(31), now + WAIT, now)).lastrowid
            room = conn.execute("SELECT * FROM race_rooms WHERE id = ?", (rid,)).fetchone()
        conn.execute("INSERT INTO race_players (room_id, user_id, name, color, upd) VALUES (?, ?, ?, ?, ?)",
                     (room["id"], user_id, (name or "Игрок")[:16], w["color"], now))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"room": room["id"], "seed": room["seed"], "start_in": room["start_at"] - time.time(), "now": time.time(),
            "players": _players(conn, room["id"])}


def tick(conn: sqlite3.Connection, user_id: int, room_id: int, z: float, x: float, v: float) -> dict[str, Any]:
    """Моя позиция → позиции остальных."""
    init(conn)
    z, x, v = max(0.0, min(TRACK + 50, float(z))), max(-6.0, min(6.0, float(x))), max(0.0, min(VNITRO + 5, float(v)))
    now = time.time()
    done = conn.execute("UPDATE race_players SET z = ?, x = ?, v = ?, upd = ? WHERE room_id = ? AND user_id = ? "
                        "AND fin_ms IS NULL", (z, x, v, now, room_id, user_id)).rowcount
    if not done:
        conn.execute("UPDATE race_players SET upd = ? WHERE room_id = ? AND user_id = ?", (now, room_id, user_id))
    room = conn.execute("SELECT start_at FROM race_rooms WHERE id = ?", (room_id,)).fetchone()
    if room is None:
        raise RaceError("Комната закрыта.")
    return {"start_in": room["start_at"] - now, "now": now,
            "players": [p for p in _players(conn, room_id) if p["user_id"] != user_id]}


def finish(conn: sqlite3.Connection, user_id: int, room_id: int, ms: int, tz_offset: int = 5) -> dict[str, Any]:
    """Финиш: место среди людей и ботов, монеты (с дневным лимитом). Проверяем, что время честное."""
    init(conn)
    now = time.time()
    room = conn.execute("SELECT * FROM race_rooms WHERE id = ?", (room_id,)).fetchone()
    me = conn.execute("SELECT * FROM race_players WHERE room_id = ? AND user_id = ?", (room_id, user_id)).fetchone()
    if room is None or me is None:
        raise RaceError("Заезд не найден.")
    if me["fin_ms"] is not None:
        raise RaceError("Финиш уже засчитан.")
    ms = int(ms)
    real_ms = (now - room["start_at"]) * 1000
    if ms < MIN_MS or abs(real_ms - ms) > 6000:      # быстрее физики или не сходится с часами сервера
        raise RaceError("Результат не засчитан.")
    humans = conn.execute("SELECT COUNT(*) FROM race_players WHERE room_id = ?", (room_id,)).fetchone()[0]
    ahead = conn.execute("SELECT COUNT(*) FROM race_players WHERE room_id = ? AND fin_ms IS NOT NULL AND fin_ms < ?",
                         (room_id, ms)).fetchone()[0]
    ahead += sum(1 for i in range(max(0, MAX_CARS - humans)) if bot_finish_ms(room["seed"], i) < ms)
    place = ahead + 1
    w = wallet(conn, user_id, "", tz_offset)
    today = _today(tz_offset)
    won = min(PRIZES.get(place, 0), max(0, w["day_left"]))
    conn.execute("BEGIN IMMEDIATE")
    try:
        if not conn.execute("UPDATE race_players SET fin_ms = ?, place = ?, z = ?, upd = ? WHERE room_id = ? "
                            "AND user_id = ? AND fin_ms IS NULL", (ms, place, TRACK, now, room_id, user_id)).rowcount:
            raise RaceError("Финиш уже засчитан.")
        conn.execute(
            "UPDATE race_wallet SET coins = coins + ?, wins = wins + ?, races = races + 1, day = ?, "
            "day_coins = CASE WHEN day = ? THEN day_coins ELSE 0 END + ? WHERE user_id = ?",
            (won, 1 if place == 1 else 0, today, today, won, user_id))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    w = wallet(conn, user_id, "", tz_offset)
    return {"place": place, "of": MAX_CARS, "ms": ms, "won": won, "coins": w["coins"], "wins": w["wins"],
            "day_left": max(0, w["day_left"])}


def shop(conn: sqlite3.Connection, user_id: int, color: str, tz_offset: int = 5) -> dict[str, Any]:
    """Купить цвет за монеты (если ещё не куплен) и поставить его."""
    if color not in COLORS:
        raise RaceError("Такого цвета нет.")
    w = wallet(conn, user_id, "", tz_offset)
    price = COLORS[color][3]
    conn.execute("BEGIN IMMEDIATE")
    try:
        if color not in w["owned"]:
            if not conn.execute("UPDATE race_wallet SET coins = coins - ? WHERE user_id = ? AND coins >= ?",
                                (price, user_id, price)).rowcount:
                raise RaceError(f"Не хватает монет: нужно {price}. / Танга кам аст.")
            w["owned"].append(color)
        conn.execute("UPDATE race_wallet SET color = ?, owned = ? WHERE user_id = ?",
                     (color, json.dumps(w["owned"]), user_id))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    w = wallet(conn, user_id, "", tz_offset)
    return {"coins": w["coins"], "color": w["color"], "owned": w["owned"]}


def top(conn: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    init(conn)
    return [dict(r) for r in conn.execute(
        "SELECT name, wins, races, color FROM race_wallet WHERE races > 0 ORDER BY wins DESC, races LIMIT ?", (limit,))]

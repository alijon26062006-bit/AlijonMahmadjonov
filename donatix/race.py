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

TRACK = 3600.0            # длина трассы, игровых метров (заезд ~1 минута)
VMAX = 52.0               # обычная максимальная скорость без тюнинга, м/с
NITRO_K = 1.5             # нитро: во сколько раз быстрее
#: Тюнинг за монеты: что → (шаг за уровень). Уровней UPG_MAX, цена уровня — UPG_COST × (уровень + 1)
UPG = {"engine": 2.0, "accel": 0.10, "nitro": 0.3}      # +2 м/с к скорости · +10% к разгону · +0.3 с нитро
UPG_MAX = 5
UPG_COST = 15
VNITRO = (VMAX + UPG["engine"] * UPG_MAX) * NITRO_K     # быстрее не едет никто
MAX_CARS = 6
WAIT = 25.0               # заезд «с людьми» ждёт соперников до старта, сек (все в сети видят приглашение)
WAIT_PAIR = 10.0          # как только в комнате двое живых — старт не позже чем через столько секунд
WAIT_FULL = 4.0           # комната полная — стартуем почти сразу
WAIT_SOLO = 4.0           # заезд только с ботами — стартует сразу
JOIN_GAP = 2.5            # за сколько до старта в комнату уже не пускаем
MIN_MS = int(TRACK / VNITRO * 1000)        # быстрее проехать нельзя даже на одном нитро
PRIZES = {1: 10, 2: 5, 3: 3}
DAY_CAP = 30              # монет в день со всех заездов
ONLINE_SEC = 45           # «в сети» — кто открыл мини-приложение или гонку за последние столько секунд
POINTS = {1: 10, 2: 6, 3: 4}   # очки рейтинга за место; за любой другой финиш — 1
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
CREATE TABLE IF NOT EXISTS race_seen (
    user_id   INTEGER PRIMARY KEY,
    name      TEXT NOT NULL DEFAULT '',
    at        REAL NOT NULL,
    place     TEXT NOT NULL DEFAULT 'app'
);
CREATE TABLE IF NOT EXISTS race_results (
    id        INTEGER PRIMARY KEY,
    user_id   INTEGER NOT NULL,
    room_id   INTEGER NOT NULL,
    place     INTEGER NOT NULL,
    ms        INTEGER NOT NULL,
    humans    INTEGER NOT NULL,
    points    INTEGER NOT NULL,
    at        REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS race_results_at ON race_results(at);
CREATE INDEX IF NOT EXISTS race_results_user ON race_results(user_id);
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
    if "upg" not in {r[1] for r in conn.execute("PRAGMA table_info(race_wallet)")}:
        conn.execute("ALTER TABLE race_wallet ADD COLUMN upg TEXT NOT NULL DEFAULT '{}'")      # тюнинг
    if "solo" not in {r[1] for r in conn.execute("PRAGMA table_info(race_rooms)")}:
        conn.execute("ALTER TABLE race_rooms ADD COLUMN solo INTEGER NOT NULL DEFAULT 0")     # заезд только с ботами


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
    try:
        raw = json.loads(w.get("upg") or "{}")
    except ValueError:
        raw = {}
    w["upg"] = {k: max(0, min(UPG_MAX, int(raw.get(k) or 0))) for k in UPG}
    w["day_left"] = DAY_CAP - (w["day_coins"] if w["day"] == _today(tz_offset) else 0)
    return w


def seen(conn: sqlite3.Connection, user_id: int, name: str, place: str = "app") -> None:
    """Отметка «я в сети»: мини-приложение и гонка шлют её каждые ~15 секунд, пока открыты."""
    init(conn)
    place = place if place in ("app", "garage", "race") else "app"
    conn.execute("INSERT INTO race_seen (user_id, name, at, place) VALUES (?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE "
                 "SET name = excluded.name, at = excluded.at, place = excluded.place", (user_id, name[:16], time.time(), place))


def online(conn: sqlite3.Connection) -> int:
    """Сколько людей сейчас в мини-приложении (магазин, гараж или заезд)."""
    init(conn)
    return conn.execute("SELECT COUNT(*) FROM race_seen WHERE at > ?", (time.time() - ONLINE_SEC,)).fetchone()[0]


def lobby(conn: sqlite3.Connection, user_id: int = 0) -> dict[str, Any]:
    """Кто сейчас ждёт соперников: открытые заезды «с людьми». Видят все в мини-приложении — так собираются живые игроки."""
    init(conn)
    now = time.time()
    rooms = []
    for r in conn.execute("SELECT id, start_at FROM race_rooms WHERE solo = 0 AND start_at > ? ORDER BY start_at",
                          (now + JOIN_GAP,)).fetchall():
        names = [x["name"] for x in conn.execute("SELECT name FROM race_players WHERE room_id = ? ORDER BY upd", (r["id"],))]
        mine = bool(conn.execute("SELECT 1 FROM race_players WHERE room_id = ? AND user_id = ?", (r["id"], user_id)).fetchone())
        if names and len(names) < MAX_CARS:
            rooms.append({"room": r["id"], "start_in": round(r["start_at"] - now, 1), "players": names, "mine": mine})
    places = dict(conn.execute("SELECT place, COUNT(*) FROM race_seen WHERE at > ? GROUP BY place",
                               (now - ONLINE_SEC,)).fetchall())
    return {"rooms": rooms, "online": sum(places.values()), "garage": places.get("garage", 0),
            "racing": places.get("race", 0)}


def profile(conn: sqlite3.Connection, user_id: int, name: str, tz_offset: int = 5) -> dict[str, Any]:
    w = wallet(conn, user_id, name, tz_offset)
    return {"coins": w["coins"], "wins": w["wins"], "races": w["races"], "color": w["color"], "owned": w["owned"],
            "day_left": max(0, w["day_left"]), "day_cap": DAY_CAP, "online": online(conn),
            "colors": [{"code": c, "ru": ru, "tj": tj, "hex": hx, "price": price} for c, (ru, tj, hx, price) in COLORS.items()],
            "prizes": PRIZES, "track": TRACK, "vmax": VMAX, "nitro_k": NITRO_K, "max_cars": MAX_CARS,
            "upg": w["upg"], "upg_step": UPG, "upg_max": UPG_MAX, "upg_cost": UPG_COST}


def _players(conn: sqlite3.Connection, room_id: int) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(
        "SELECT user_id, name, color, z, x, v, fin_ms, place FROM race_players WHERE room_id = ? ORDER BY user_id",
        (room_id,))]


def join(conn: sqlite3.Connection, user_id: int, name: str, tz_offset: int = 5, solo: bool = False) -> dict[str, Any]:
    """В набирающуюся комнату или в новую (solo — своя комната только с ботами). Зерно, время до старта, игроки."""
    init(conn)
    w = wallet(conn, user_id, name, tz_offset)
    seen(conn, user_id, name, "race")
    now = time.time()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("DELETE FROM race_players WHERE room_id IN (SELECT id FROM race_rooms WHERE created < ?)", (now - 3600,))
        conn.execute("DELETE FROM race_rooms WHERE created < ?", (now - 3600,))
        room = None if solo else conn.execute(
            "SELECT r.* FROM race_rooms r WHERE r.solo = 0 AND r.start_at > ? AND (SELECT COUNT(*) FROM race_players p "
            "WHERE p.room_id = r.id) < ? AND NOT EXISTS (SELECT 1 FROM race_players p WHERE p.room_id = r.id "
            "AND p.user_id = ?) ORDER BY r.start_at LIMIT 1", (now + JOIN_GAP, MAX_CARS, user_id)).fetchone()
        if room is None:
            rid = conn.execute("INSERT INTO race_rooms (seed, start_at, created, solo) VALUES (?, ?, ?, ?)",
                               (random.getrandbits(31), now + (WAIT_SOLO if solo else WAIT), now, 1 if solo else 0)).lastrowid
            room = conn.execute("SELECT * FROM race_rooms WHERE id = ?", (rid,)).fetchone()
        conn.execute("INSERT INTO race_players (room_id, user_id, name, color, upd) VALUES (?, ?, ?, ?, ?)",
                     (room["id"], user_id, (name or "Игрок")[:16], w["color"], now))
        if not solo:      # собрались живые — ждать дольше незачем
            n = conn.execute("SELECT COUNT(*) FROM race_players WHERE room_id = ?", (room["id"],)).fetchone()[0]
            soon = now + (WAIT_FULL if n >= MAX_CARS else WAIT_PAIR if n >= 2 else WAIT)
            conn.execute("UPDATE race_rooms SET start_at = MIN(start_at, ?) WHERE id = ?", (soon, room["id"]))
            room = conn.execute("SELECT * FROM race_rooms WHERE id = ?", (room["id"],)).fetchone()
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
        conn.execute("INSERT INTO race_results (user_id, room_id, place, ms, humans, points, at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (user_id, room_id, place, ms, humans, POINTS.get(place, 1), now))
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


def upgrade(conn: sqlite3.Connection, user_id: int, key: str, tz_offset: int = 5) -> dict[str, Any]:
    """Тюнинг: +1 уровень двигателя, разгона или нитро за монеты."""
    if key not in UPG:
        raise RaceError("Такого улучшения нет.")
    w = wallet(conn, user_id, "", tz_offset)
    level = w["upg"][key]
    if level >= UPG_MAX:
        raise RaceError("Уже максимум. / Аллакай ҳадди аксар.")
    price = UPG_COST * (level + 1)
    w["upg"][key] = level + 1
    if not conn.execute("UPDATE race_wallet SET coins = coins - ?, upg = ? WHERE user_id = ? AND coins >= ?",
                        (price, json.dumps(w["upg"]), user_id, price)).rowcount:
        raise RaceError(f"Не хватает монет: нужно {price}. / Танга кам аст.")
    w = wallet(conn, user_id, "", tz_offset)
    return {"coins": w["coins"], "upg": w["upg"]}


def _since(period: str, tz_offset: int) -> float:
    if period == "day":
        return time.time() - (time.time() + tz_offset * 3600) % 86400
    if period == "week":
        return time.time() - 7 * 86400
    return 0.0


def top(conn: sqlite3.Connection, limit: int = 20, period: str = "week", tz_offset: int = 5) -> list[dict[str, Any]]:
    """Рейтинг: очки за места (1-е — 10, 2-е — 6, 3-е — 4, любой финиш — 1) за день, неделю или всё время."""
    init(conn)
    return [dict(r) for r in conn.execute(
        "SELECT r.user_id, COALESCE(w.name, '') AS name, COALESCE(w.color, 'violet') AS color, SUM(r.points) AS points, "
        "COUNT(*) AS races, SUM(r.place = 1) AS wins, MIN(r.ms) AS best_ms FROM race_results r "
        "LEFT JOIN race_wallet w ON w.user_id = r.user_id WHERE r.at >= ? GROUP BY r.user_id "
        "ORDER BY points DESC, wins DESC, best_ms LIMIT ?", (_since(period, tz_offset), limit))]


def stats(conn: sqlite3.Connection, user_id: int, tz_offset: int = 5) -> dict[str, Any]:
    """Моя статистика: заезды, победы, подиумы, лучшее время, очки и место в рейтинге недели и всех времён."""
    init(conn)
    w = wallet(conn, user_id, "", tz_offset)
    r = conn.execute("SELECT COUNT(*) AS n, SUM(place = 1) AS wins, SUM(place <= 3) AS podium, MIN(ms) AS best, "
                     "AVG(place) AS avg_place, SUM(points) AS points, SUM(humans > 1) AS vs_people "
                     "FROM race_results WHERE user_id = ?", (user_id,)).fetchone()

    def rank(since: float) -> int:
        mine = conn.execute("SELECT COALESCE(SUM(points), 0) FROM race_results WHERE user_id = ? AND at >= ?",
                            (user_id, since)).fetchone()[0]
        if not mine:
            return 0
        return 1 + conn.execute("SELECT COUNT(*) FROM (SELECT SUM(points) AS p FROM race_results WHERE at >= ? "
                                "GROUP BY user_id HAVING p > ?)", (since, mine)).fetchone()[0]
    week = conn.execute("SELECT COALESCE(SUM(points), 0) FROM race_results WHERE user_id = ? AND at >= ?",
                        (user_id, _since("week", tz_offset))).fetchone()[0]
    races = max(w["races"], r["n"] or 0)
    return {"races": races, "wins": max(w["wins"], r["wins"] or 0), "podium": r["podium"] or 0,
            "best_ms": r["best"] or 0, "avg_place": round(r["avg_place"] or 0, 1), "points": r["points"] or 0,
            "week_points": week, "vs_people": r["vs_people"] or 0,
            "win_rate": round((r["wins"] or 0) * 100 / r["n"]) if r["n"] else 0,
            "rank_week": rank(_since("week", tz_offset)), "rank_all": rank(0.0)}

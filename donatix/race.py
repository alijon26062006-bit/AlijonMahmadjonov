"""Гонка в мини-приложении Telegram: до 6 машин, живые игроки + боты на свободных местах.

Устройство кода (ООП). RaceGame — одна игра на одно соединение с базой; в ней четыре части:
  Garage   — кошелёк игрока: монеты, цвета, тюнинг;
  Presence — кто сейчас в сети и кто ждёт соперников;
  Rooms    — заезды: быстрый «с людьми», «с ботами» и СВОЯ ГРУППА (код, свои игроки, старт по кнопке хозяина);
  Rating   — очки, рейтинг, статистика.
Track — математика трассы и ботов (одна формула в Python и в игре на телефоне).
Функции внизу файла (join, tick, finish…) — короткие обёртки над RaceGame для остального кода и тестов.

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
GROUP_WAIT = 5.0          # своя группа: хозяин нажал «Старт» — у всех один и тот же отсчёт, сек
GROUP_TTL = 1800.0        # группа, которую так и не запустили, живёт столько секунд
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
    if "code" not in {r[1] for r in conn.execute("PRAGMA table_info(race_rooms)")}:              # своя группа
        conn.execute("ALTER TABLE race_rooms ADD COLUMN code TEXT")
        conn.execute("ALTER TABLE race_rooms ADD COLUMN host INTEGER")
        conn.execute("ALTER TABLE race_rooms ADD COLUMN started INTEGER NOT NULL DEFAULT 1")


class Track:
    """Трасса и боты: всё считается из «зерна» комнаты, одинаково на сервере и на каждом телефоне."""

    @staticmethod
    def rnd(seed: int, i: int) -> float:
        """Случайное число 0..1 из зерна — та же формула в игре (JS), поэтому боты у всех одинаковые."""
        m = 0xFFFFFFFF
        x = (seed ^ ((i * 374761393) & m)) & m
        x = ((x ^ (x >> 15)) * 2246822519) & m
        x = ((x ^ (x >> 13)) * 3266489917) & m
        x = (x ^ (x >> 16)) & m
        return x / 4294967296

    @staticmethod
    def bot_speed(seed: int, i: int) -> float:
        return 41.0 + Track.rnd(seed, i) * 7.5        # 41–48.5 м/с: внимательный игрок обгонит, невнимательный — нет

    @staticmethod
    def bot_finish_ms(seed: int, i: int) -> int:
        """Бот разгоняется 3 секунды, дальше едет ровно: z = v·(t − 1.5) → финиш = длина/v + 1.5 с."""
        return int((TRACK / Track.bot_speed(seed, i) + 1.5) * 1000)


rnd, bot_speed, bot_finish_ms = Track.rnd, Track.bot_speed, Track.bot_finish_ms


class _Part:
    """Часть игры: знает свою игру, её соединение с базой и часовой пояс."""

    def __init__(self, game: "RaceGame"):
        self.game, self.conn, self.tz = game, game.conn, game.tz


class Garage(_Part):
    """Кошелёк игрока: игровые монеты, купленные цвета, тюнинг."""

    def wallet(self, user_id: int, name: str = "") -> dict[str, Any]:
        self.conn.execute("INSERT OR IGNORE INTO race_wallet (user_id, name) VALUES (?, ?)", (user_id, name[:32]))
        if name:
            self.conn.execute("UPDATE race_wallet SET name = ? WHERE user_id = ? AND name != ?", (name[:32], user_id, name[:32]))
        w = dict(self.conn.execute("SELECT * FROM race_wallet WHERE user_id = ?", (user_id,)).fetchone())
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
        w["day_left"] = DAY_CAP - (w["day_coins"] if w["day"] == self.game.today() else 0)
        return w

    def profile(self, user_id: int, name: str) -> dict[str, Any]:
        w = self.game.garage.wallet(user_id, name)
        return {"coins": w["coins"], "wins": w["wins"], "races": w["races"], "color": w["color"], "owned": w["owned"],
                "day_left": max(0, w["day_left"]), "day_cap": DAY_CAP, "online": self.game.presence.online(),
                "colors": [{"code": c, "ru": ru, "tj": tj, "hex": hx, "price": price} for c, (ru, tj, hx, price) in COLORS.items()],
                "prizes": PRIZES, "track": TRACK, "vmax": VMAX, "nitro_k": NITRO_K, "max_cars": MAX_CARS,
                "upg": w["upg"], "upg_step": UPG, "upg_max": UPG_MAX, "upg_cost": UPG_COST}

    def shop(self, user_id: int, color: str) -> dict[str, Any]:
        """Купить цвет за монеты (если ещё не куплен) и поставить его."""
        if color not in COLORS:
            raise RaceError("Такого цвета нет.")
        w = self.game.garage.wallet(user_id, "")
        price = COLORS[color][3]
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            if color not in w["owned"]:
                if not self.conn.execute("UPDATE race_wallet SET coins = coins - ? WHERE user_id = ? AND coins >= ?",
                                    (price, user_id, price)).rowcount:
                    raise RaceError(f"Не хватает монет: нужно {price}. / Танга кам аст.")
                w["owned"].append(color)
            self.conn.execute("UPDATE race_wallet SET color = ?, owned = ? WHERE user_id = ?",
                         (color, json.dumps(w["owned"]), user_id))
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        w = self.game.garage.wallet(user_id, "")
        return {"coins": w["coins"], "color": w["color"], "owned": w["owned"]}

    def upgrade(self, user_id: int, key: str) -> dict[str, Any]:
        """Тюнинг: +1 уровень двигателя, разгона или нитро за монеты."""
        if key not in UPG:
            raise RaceError("Такого улучшения нет.")
        w = self.game.garage.wallet(user_id, "")
        level = w["upg"][key]
        if level >= UPG_MAX:
            raise RaceError("Уже максимум. / Аллакай ҳадди аксар.")
        price = UPG_COST * (level + 1)
        w["upg"][key] = level + 1
        if not self.conn.execute("UPDATE race_wallet SET coins = coins - ?, upg = ? WHERE user_id = ? AND coins >= ?",
                            (price, json.dumps(w["upg"]), user_id, price)).rowcount:
            raise RaceError(f"Не хватает монет: нужно {price}. / Танга кам аст.")
        w = self.game.garage.wallet(user_id, "")
        return {"coins": w["coins"], "upg": w["upg"]}


class Presence(_Part):
    """Кто сейчас в сети и какие заезды ждут соперников."""

    def seen(self, user_id: int, name: str, place: str = "app") -> None:
        """Отметка «я в сети»: мини-приложение и гонка шлют её каждые ~15 секунд, пока открыты."""
        place = place if place in ("app", "garage", "race") else "app"
        self.conn.execute("INSERT INTO race_seen (user_id, name, at, place) VALUES (?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE "
                     "SET name = excluded.name, at = excluded.at, place = excluded.place", (user_id, name[:16], time.time(), place))

    def online(self) -> int:
        """Сколько людей сейчас в мини-приложении (магазин, гараж или заезд)."""
        return self.conn.execute("SELECT COUNT(*) FROM race_seen WHERE at > ?", (time.time() - ONLINE_SEC,)).fetchone()[0]

    def lobby(self, user_id: int = 0) -> dict[str, Any]:
        """Кто сейчас ждёт соперников: открытые заезды «с людьми». Видят все в мини-приложении — так собираются живые игроки."""
        now = time.time()
        rooms = []
        for r in self.conn.execute("SELECT id, start_at FROM race_rooms WHERE solo = 0 AND code IS NULL AND start_at > ? ORDER BY start_at",
                              (now + JOIN_GAP,)).fetchall():
            names = [x["name"] for x in self.conn.execute("SELECT name FROM race_players WHERE room_id = ? ORDER BY upd", (r["id"],))]
            mine = bool(self.conn.execute("SELECT 1 FROM race_players WHERE room_id = ? AND user_id = ?", (r["id"], user_id)).fetchone())
            if names and len(names) < MAX_CARS:
                rooms.append({"room": r["id"], "start_in": round(r["start_at"] - now, 1), "players": names, "mine": mine})
        places = dict(self.conn.execute("SELECT place, COUNT(*) FROM race_seen WHERE at > ? GROUP BY place",
                                   (now - ONLINE_SEC,)).fetchall())
        return {"rooms": rooms, "online": sum(places.values()), "garage": places.get("garage", 0),
                "racing": places.get("race", 0)}


class Rooms(_Part):
    """Заезды: вход, позиции машин, финиш; своя группа со стартом по кнопке хозяина."""

    def players(self, room_id: int) -> list[dict[str, Any]]:
        return [dict(r) for r in self.conn.execute(
            "SELECT user_id, name, color, z, x, v, fin_ms, place FROM race_players WHERE room_id = ? ORDER BY user_id",
            (room_id,))]

    def join(self, user_id: int, name: str, solo: bool = False) -> dict[str, Any]:
        """В набирающуюся комнату или в новую (solo — своя комната только с ботами). Зерно, время до старта, игроки."""
        w = self.game.garage.wallet(user_id, name)
        self.game.presence.seen(user_id, name, "race")
        now = time.time()
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.conn.execute("DELETE FROM race_players WHERE room_id IN (SELECT id FROM race_rooms WHERE created < ?)", (now - 3600,))
            self.conn.execute("DELETE FROM race_rooms WHERE created < ?", (now - 3600,))
            room = None if solo else self.conn.execute(
                "SELECT r.* FROM race_rooms r WHERE r.solo = 0 AND r.code IS NULL AND r.start_at > ? AND (SELECT COUNT(*) FROM race_players p "
                "WHERE p.room_id = r.id) < ? AND NOT EXISTS (SELECT 1 FROM race_players p WHERE p.room_id = r.id "
                "AND p.user_id = ?) ORDER BY r.start_at LIMIT 1", (now + JOIN_GAP, MAX_CARS, user_id)).fetchone()
            if room is None:
                rid = self.conn.execute("INSERT INTO race_rooms (seed, start_at, created, solo) VALUES (?, ?, ?, ?)",
                                   (random.getrandbits(31), now + (WAIT_SOLO if solo else WAIT), now, 1 if solo else 0)).lastrowid
                room = self.conn.execute("SELECT * FROM race_rooms WHERE id = ?", (rid,)).fetchone()
            self.conn.execute("INSERT INTO race_players (room_id, user_id, name, color, upd) VALUES (?, ?, ?, ?, ?)",
                         (room["id"], user_id, (name or "Игрок")[:16], w["color"], now))
            if not solo:      # собрались живые — ждать дольше незачем
                n = self.conn.execute("SELECT COUNT(*) FROM race_players WHERE room_id = ?", (room["id"],)).fetchone()[0]
                soon = now + (WAIT_FULL if n >= MAX_CARS else WAIT_PAIR if n >= 2 else WAIT)
                self.conn.execute("UPDATE race_rooms SET start_at = MIN(start_at, ?) WHERE id = ?", (soon, room["id"]))
                room = self.conn.execute("SELECT * FROM race_rooms WHERE id = ?", (room["id"],)).fetchone()
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        return {"room": room["id"], "seed": room["seed"], "start_in": room["start_at"] - time.time(), "now": time.time(),
                "players": self.game.rooms.players(room["id"])}

    def tick(self, user_id: int, room_id: int, z: float, x: float, v: float) -> dict[str, Any]:
        """Моя позиция → позиции остальных."""
        z, x, v = max(0.0, min(TRACK + 50, float(z))), max(-6.0, min(6.0, float(x))), max(0.0, min(VNITRO + 5, float(v)))
        now = time.time()
        done = self.conn.execute("UPDATE race_players SET z = ?, x = ?, v = ?, upd = ? WHERE room_id = ? AND user_id = ? "
                            "AND fin_ms IS NULL", (z, x, v, now, room_id, user_id)).rowcount
        if not done:
            self.conn.execute("UPDATE race_players SET upd = ? WHERE room_id = ? AND user_id = ?", (now, room_id, user_id))
        room = self.conn.execute("SELECT start_at, started, host FROM race_rooms WHERE id = ?", (room_id,)).fetchone()
        if room is None:
            raise RaceError("Комната закрыта.")
        return {"start_in": room["start_at"] - now, "now": now, "waiting": not room["started"],
                "is_host": bool(room["host"]) and room["host"] == user_id,
                "players": [p for p in self.game.rooms.players(room_id) if p["user_id"] != user_id]}

    def finish(self, user_id: int, room_id: int, ms: int) -> dict[str, Any]:
        """Финиш: место среди людей и ботов, монеты (с дневным лимитом). Проверяем, что время честное."""
        now = time.time()
        room = self.conn.execute("SELECT * FROM race_rooms WHERE id = ?", (room_id,)).fetchone()
        me = self.conn.execute("SELECT * FROM race_players WHERE room_id = ? AND user_id = ?", (room_id, user_id)).fetchone()
        if room is None or me is None:
            raise RaceError("Заезд не найден.")
        if me["fin_ms"] is not None:
            raise RaceError("Финиш уже засчитан.")
        ms = int(ms)
        real_ms = (now - room["start_at"]) * 1000
        if ms < MIN_MS or abs(real_ms - ms) > 6000:      # быстрее физики или не сходится с часами сервера
            raise RaceError("Результат не засчитан.")
        humans = self.conn.execute("SELECT COUNT(*) FROM race_players WHERE room_id = ?", (room_id,)).fetchone()[0]
        ahead = self.conn.execute("SELECT COUNT(*) FROM race_players WHERE room_id = ? AND fin_ms IS NOT NULL AND fin_ms < ?",
                             (room_id, ms)).fetchone()[0]
        ahead += sum(1 for i in range(max(0, MAX_CARS - humans)) if bot_finish_ms(room["seed"], i) < ms)
        place = ahead + 1
        w = self.game.garage.wallet(user_id, "")
        today = self.game.today()
        won = min(PRIZES.get(place, 0), max(0, w["day_left"]))
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            if not self.conn.execute("UPDATE race_players SET fin_ms = ?, place = ?, z = ?, upd = ? WHERE room_id = ? "
                                "AND user_id = ? AND fin_ms IS NULL", (ms, place, TRACK, now, room_id, user_id)).rowcount:
                raise RaceError("Финиш уже засчитан.")
            self.conn.execute(
                "UPDATE race_wallet SET coins = coins + ?, wins = wins + ?, races = races + 1, day = ?, "
                "day_coins = CASE WHEN day = ? THEN day_coins ELSE 0 END + ? WHERE user_id = ?",
                (won, 1 if place == 1 else 0, today, today, won, user_id))
            self.conn.execute("INSERT INTO race_results (user_id, room_id, place, ms, humans, points, at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (user_id, room_id, place, ms, humans, POINTS.get(place, 1), now))
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        w = self.game.garage.wallet(user_id, "")
        return {"place": place, "of": MAX_CARS, "ms": ms, "won": won, "coins": w["coins"], "wins": w["wins"],
                "day_left": max(0, w["day_left"])}

    # ── своя группа: код, свои игроки, старт по кнопке хозяина — у всех один отсчёт ──

    def _view(self, room: sqlite3.Row, user_id: int) -> dict[str, Any]:
        now = time.time()
        waiting = not room["started"]
        return {"room": room["id"], "seed": room["seed"], "now": now, "waiting": waiting,
                "start_in": GROUP_TTL if waiting else room["start_at"] - now, "code": room["code"] or "",
                "host": room["host"] or 0, "is_host": bool(room["host"]) and room["host"] == user_id,
                "players": self.players(room["id"])}

    def _room(self, room_id: int) -> sqlite3.Row:
        room = self.conn.execute("SELECT * FROM race_rooms WHERE id = ?", (room_id,)).fetchone()
        if room is None:
            raise RaceError("Группа закрыта. / Гурӯҳ баста шуд.")
        return room

    def group_create(self, user_id: int, name: str) -> dict[str, Any]:
        """Новая группа: игрок становится хозяином и получает код, по которому заходят его друзья."""
        w = self.game.garage.wallet(user_id, name)
        self.game.presence.seen(user_id, name, "race")
        now = time.time()
        self.conn.execute("DELETE FROM race_players WHERE room_id IN (SELECT id FROM race_rooms WHERE started = 0 AND host = ?)", (user_id,))
        self.conn.execute("DELETE FROM race_rooms WHERE started = 0 AND host = ?", (user_id,))       # прежняя незапущенная группа
        for _ in range(20):
            code = "".join(random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(5))
            if not self.conn.execute("SELECT 1 FROM race_rooms WHERE code = ?", (code,)).fetchone():
                break
        rid = self.conn.execute("INSERT INTO race_rooms (seed, start_at, created, solo, code, host, started) VALUES (?, ?, ?, 0, ?, ?, 0)",
                                (random.getrandbits(31), now + GROUP_TTL, now, code, user_id)).lastrowid
        self.conn.execute("INSERT INTO race_players (room_id, user_id, name, color, upd) VALUES (?, ?, ?, ?, ?)",
                          (rid, user_id, (name or "Игрок")[:16], w["color"], now))
        return self._view(self._room(rid), user_id)

    def group_join(self, user_id: int, name: str, code: str) -> dict[str, Any]:
        """Войти в группу друга по коду — пока хозяин не нажал «Старт» и есть место."""
        w = self.game.garage.wallet(user_id, name)
        self.game.presence.seen(user_id, name, "race")
        code = "".join(c for c in str(code).upper() if c.isalnum())[:8]
        room = self.conn.execute("SELECT * FROM race_rooms WHERE code = ? AND created > ? ORDER BY id DESC LIMIT 1",
                                 (code, time.time() - GROUP_TTL)).fetchone() if code else None
        if room is None:
            raise RaceError("Группа с таким кодом не найдена. / Гурӯҳ бо ин код ёфт нашуд.")
        inside = self.conn.execute("SELECT 1 FROM race_players WHERE room_id = ? AND user_id = ?", (room["id"], user_id)).fetchone()
        if not inside:
            if room["started"]:
                raise RaceError("Эта группа уже стартовала. / Ин гурӯҳ аллакай оғоз кард.")
            if self.conn.execute("SELECT COUNT(*) FROM race_players WHERE room_id = ?", (room["id"],)).fetchone()[0] >= MAX_CARS:
                raise RaceError("В группе нет мест. / Дар гурӯҳ ҷой нест.")
            self.conn.execute("INSERT INTO race_players (room_id, user_id, name, color, upd) VALUES (?, ?, ?, ?, ?)",
                              (room["id"], user_id, (name or "Игрок")[:16], w["color"], time.time()))
        return self._view(room, user_id)

    def group_start(self, user_id: int, room_id: int) -> dict[str, Any]:
        """Хозяин запускает заезд: у всех игроков группы один и тот же отсчёт."""
        room = self._room(room_id)
        if room["host"] != user_id:
            raise RaceError("Старт даёт хозяин группы. / Оғозро соҳиби гурӯҳ медиҳад.")
        if not room["started"]:
            self.conn.execute("UPDATE race_rooms SET started = 1, start_at = ? WHERE id = ? AND started = 0",
                              (time.time() + GROUP_WAIT, room_id))
        return self._view(self._room(room_id), user_id)

    def group_leave(self, user_id: int, room_id: int) -> dict[str, Any]:
        """Выйти из группы до старта; ушёл хозяин — хозяином становится следующий, пустая группа закрывается."""
        room = self.conn.execute("SELECT * FROM race_rooms WHERE id = ? AND started = 0", (room_id,)).fetchone()
        if room is not None:
            self.conn.execute("DELETE FROM race_players WHERE room_id = ? AND user_id = ?", (room_id, user_id))
            nxt = self.conn.execute("SELECT user_id FROM race_players WHERE room_id = ? ORDER BY upd LIMIT 1", (room_id,)).fetchone()
            if nxt is None:
                self.conn.execute("DELETE FROM race_rooms WHERE id = ?", (room_id,))
            elif room["host"] == user_id:
                self.conn.execute("UPDATE race_rooms SET host = ? WHERE id = ?", (nxt["user_id"], room_id))
        return {"ok": True}


class Rating(_Part):
    """Очки за места, рейтинг за день / неделю / всё время и личная статистика."""

    def since(self, period: str) -> float:
        if period == "day":
            return time.time() - (time.time() + self.tz * 3600) % 86400
        if period == "week":
            return time.time() - 7 * 86400
        return 0.0

    def top(self, limit: int = 20, period: str = "week") -> list[dict[str, Any]]:
        """Рейтинг: очки за места (1-е — 10, 2-е — 6, 3-е — 4, любой финиш — 1) за день, неделю или всё время."""
        return [dict(r) for r in self.conn.execute(
            "SELECT r.user_id, COALESCE(w.name, '') AS name, COALESCE(w.color, 'violet') AS color, SUM(r.points) AS points, "
            "COUNT(*) AS races, SUM(r.place = 1) AS wins, MIN(r.ms) AS best_ms FROM race_results r "
            "LEFT JOIN race_wallet w ON w.user_id = r.user_id WHERE r.at >= ? GROUP BY r.user_id "
            "ORDER BY points DESC, wins DESC, best_ms LIMIT ?", (self.game.rating.since(period), limit))]

    def stats(self, user_id: int) -> dict[str, Any]:
        """Моя статистика: заезды, победы, подиумы, лучшее время, очки и место в рейтинге недели и всех времён."""
        w = self.game.garage.wallet(user_id, "")
        r = self.conn.execute("SELECT COUNT(*) AS n, SUM(place = 1) AS wins, SUM(place <= 3) AS podium, MIN(ms) AS best, "
                         "AVG(place) AS avg_place, SUM(points) AS points, SUM(humans > 1) AS vs_people "
                         "FROM race_results WHERE user_id = ?", (user_id,)).fetchone()

        def rank(since: float) -> int:
            mine = self.conn.execute("SELECT COALESCE(SUM(points), 0) FROM race_results WHERE user_id = ? AND at >= ?",
                                (user_id, since)).fetchone()[0]
            if not mine:
                return 0
            return 1 + self.conn.execute("SELECT COUNT(*) FROM (SELECT SUM(points) AS p FROM race_results WHERE at >= ? "
                                    "GROUP BY user_id HAVING p > ?)", (since, mine)).fetchone()[0]
        week = self.conn.execute("SELECT COALESCE(SUM(points), 0) FROM race_results WHERE user_id = ? AND at >= ?",
                            (user_id, self.game.rating.since("week"))).fetchone()[0]
        races = max(w["races"], r["n"] or 0)
        return {"races": races, "wins": max(w["wins"], r["wins"] or 0), "podium": r["podium"] or 0,
                "best_ms": r["best"] or 0, "avg_place": round(r["avg_place"] or 0, 1), "points": r["points"] or 0,
                "week_points": week, "vs_people": r["vs_people"] or 0,
                "win_rate": round((r["wins"] or 0) * 100 / r["n"]) if r["n"] else 0,
                "rank_week": rank(self.game.rating.since("week")), "rank_all": rank(0.0)}


class RaceGame:
    """Вся гонка для одного соединения с базой: гараж, присутствие, заезды, рейтинг."""

    def __init__(self, conn: sqlite3.Connection, tz_offset: int = 5):
        init(conn)
        self.conn, self.tz = conn, tz_offset
        self.garage, self.presence, self.rooms, self.rating = Garage(self), Presence(self), Rooms(self), Rating(self)

    def today(self) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime(time.time() + self.tz * 3600))


# ── короткие обёртки: остальной код и тесты зовут гонку обычными функциями ──

def _today(tz_offset: int) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() + tz_offset * 3600))


def wallet(conn, user_id, name="", tz_offset=5):
    return RaceGame(conn, tz_offset).garage.wallet(user_id, name)


def profile(conn, user_id, name, tz_offset=5):
    return RaceGame(conn, tz_offset).garage.profile(user_id, name)


def shop(conn, user_id, color, tz_offset=5):
    return RaceGame(conn, tz_offset).garage.shop(user_id, color)


def upgrade(conn, user_id, key, tz_offset=5):
    return RaceGame(conn, tz_offset).garage.upgrade(user_id, key)


def seen(conn, user_id, name, place="app"):
    return RaceGame(conn).presence.seen(user_id, name, place)


def online(conn):
    return RaceGame(conn).presence.online()


def lobby(conn, user_id=0):
    return RaceGame(conn).presence.lobby(user_id)


def join(conn, user_id, name, tz_offset=5, solo=False):
    return RaceGame(conn, tz_offset).rooms.join(user_id, name, solo)


def tick(conn, user_id, room_id, z, x, v):
    return RaceGame(conn).rooms.tick(user_id, room_id, z, x, v)


def finish(conn, user_id, room_id, ms, tz_offset=5):
    return RaceGame(conn, tz_offset).rooms.finish(user_id, room_id, ms)


def top(conn, limit=20, period="week", tz_offset=5):
    return RaceGame(conn, tz_offset).rating.top(limit, period)


def stats(conn, user_id, tz_offset=5):
    return RaceGame(conn, tz_offset).rating.stats(user_id)

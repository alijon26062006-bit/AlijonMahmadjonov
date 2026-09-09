"""Сервер дуэли: WebSocket для матчей и раздача Mini App.

Все решения принимает сервер: он выдаёт примеры, сверяет ответы, двигает
канат и объявляет победителя. Клиент только рисует картинку и шлёт нажатия.
Состояние матчей живёт в памяти — матч короткий, переживать перезапуск ему
незачем; в базу попадает только итог.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import sqlite3
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from aiohttp import ClientSession, ClientTimeout, WSMsgType, web

from . import rating as rating_mod
from . import storage
from .auth import AuthError, WebAppUser, authenticate
from .config import DuelConfig
from . import games
from . import robot as robot_mod
from .game import (
    DURATIONS,
    STATE_FINISHED,
    STATE_RUNNING,
    WIN_STEPS,
    Match,
    Side,
)
from .i18n import normalize, t, ui_strings
from .matchmaking import HOST_GRACE_SEC, Queue, Room, Ticket, make_match
from .five_match import FiveMatch
from .sea_match import SHOT_RESULTS, SeaMatch
from .tasks import LEVELS

log = logging.getLogger("duel.server")

WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"
MAX_MESSAGE_BYTES = 4096
# Больше двадцати пяти нажатий в секунду — это уже не пальцы.
ANSWER_BURST = 25
# Даже если ничего не поменялось, состояние шлём раз в полсекунды: так клиент
# понимает, что связь жива.
HEARTBEAT_SEC = 0.5

# Одного и того же человека не зовём чаще, чем раз в минуту, и вообще не чаще
# чем раз в восемь секунд: приглашение приходит в чат, спамить им нельзя.
# Столько ждём живого соперника, прежде чем предложить робота: пятнадцать
# секунд в пустой очереди — это уже долго, дальше человек просто уходит.
WAIT_FOR_ROBOT = 15.0
CHALLENGE_COOLDOWN = 60.0
CHALLENGE_RATE = 8.0
PLAYERS_PAGE = 60

# Библиотека Telegram, без которой Mini App не знает, кто её открыл.
TG_SCRIPT_URL = "https://telegram.org/js/telegram-web-app.js"
TG_SCRIPT_NAME = "telegram-web-app.js"
TG_SCRIPT_MAX_AGE = 7 * 24 * 3600


@dataclass
class Conn:
    """Одно открытое соединение с игроком."""

    ws: web.WebSocketResponse
    user: WebAppUser
    lang: str = "ru"
    # Рейтинг и число матчей по каждой игре: у каната и моря они разные.
    scores: dict[str, tuple[int, int]] = field(default_factory=dict)
    last_state: str = ""
    last_state_at: float = 0.0
    answers: deque[float] = field(default_factory=lambda: deque(maxlen=ANSWER_BURST))

    @property
    def user_id(self) -> int:
        return self.user.id

    def rating(self, game: str) -> int:
        return self.scores.get(game, (1000, 0))[0]

    def played(self, game: str) -> int:
        return self.scores.get(game, (1000, 0))[1]

    async def send(self, payload: dict[str, object]) -> None:
        if self.ws.closed:
            return
        with contextlib.suppress(ConnectionResetError, RuntimeError):
            await self.ws.send_str(json.dumps(payload, ensure_ascii=False))

    def flooding(self, now: float) -> bool:
        self.answers.append(now)
        return len(self.answers) == ANSWER_BURST and now - self.answers[0] < 1.0


class Hub:
    """Держит очередь, матчи и соединения."""

    def __init__(
        self,
        config: DuelConfig,
        conn: sqlite3.Connection,
        notify: Callable[..., Awaitable[None]] | None = None,
        bot_username: str = "",
        main_app: bool = False,
    ) -> None:
        self.config = config
        self.db = conn
        self.notify = notify
        self.bot_username = bot_username
        # Настроено ли у бота главное мини-приложение. От этого зависит, какая
        # ссылка-приглашение открывает игру в одно касание.
        self.main_app = main_app
        self.queue = Queue()
        self.conns: dict[int, Conn] = {}
        self.matches: dict[int, Match] = {}
        self.match_of: dict[int, int] = {}
        self._ticker: asyncio.Task[None] | None = None
        self._online: dict[str, int] = {}
        self._online_at = 0.0
        self._called: dict[tuple[int, int], float] = {}
        self._called_at: dict[int, float] = {}
        self.robots: dict[int, robot_mod.Robot] = {}
        self._offered: set[int] = set()

    # ── служебное ───────────────────────────────────────────────────

    def open_group_room(
        self,
        user_id: int,
        name: str,
        chat_id: int,
        *,
        duration: int = -1,
        level: str = "auto",
        game: str = games.DEFAULT_GAME,
        now: float | None = None,
    ) -> "Room":
        """Открытый вызов в чате: дерётся тот, кто первым нажмёт кнопку."""

        game = games.normalize(game)
        row = storage.get_player(self.db, user_id)
        rating, played = storage.rating_of(self.db, user_id, game)
        ticket = Ticket(
            user_id=user_id,
            name=name,
            rating=rating,
            games=played,
            lang=row["lang"] if row else "ru",
            duration=duration if duration in DURATIONS else games.info(game).duration,
            level=level if level in LEVELS else "auto",
            joined_at=now if now is not None else time.monotonic(),
            game=game,
        )
        return self.queue.create_room(
            ticket, ticket.joined_at, chat_id=chat_id
        )

    def invite_link(self, code: str) -> str:
        """Ссылка-приглашение, самая короткая из доступных.

        С настроенным главным мини-приложением ?startapp= открывает игру одним
        касанием — даже у того, кто бота ещё ни разу не запускал. Без него
        Telegram просто откроет переписку, поэтому там нужен ?start=: бот
        ответит на него сообщением с кнопкой.
        """

        if not self.bot_username:
            return ""
        key = "startapp" if self.main_app else "start"
        return f"https://t.me/{self.bot_username}?{key}={code}"

    def match_for(self, user_id: int) -> Match | None:
        mid = self.match_of.get(user_id)
        return self.matches.get(mid) if mid else None

    def standing_of(self, user_id: int, game: str) -> dict[str, object]:
        row = storage.standing(self.db, user_id, game)
        if row is None:
            return {
                "rating": 1000, "title": rating_mod.title(1000), "games": 0,
                "wins": 0, "losses": 0, "draws": 0, "correct": 0,
                "best_streak": 0, "place": 0,
            }
        return {
            "rating": row["rating"],
            "title": rating_mod.title(row["rating"]),
            "games": row["games"],
            "wins": row["wins"],
            "losses": row["losses"],
            "draws": row["draws"],
            "correct": row["correct"],
            "best_streak": row["best_streak"],
            "place": storage.place_of(self.db, user_id, game),
        }

    def profile(self, conn: Conn) -> dict[str, object]:
        row = storage.get_player(self.db, conn.user_id)
        if row is None:
            return {}
        return {
            "id": row["id"],
            "name": row["name"],
            "photo_url": row["photo_url"],
            "standings": {g: self.standing_of(conn.user_id, g) for g in games.GAME_IDS},
        }

    def online_stats(self) -> dict[str, int]:
        """Сколько людей сейчас в игре. Видно прямо в меню."""

        return {
            "online": len(self.conns),
            "searching": len(self.queue),
            "playing": len(self.matches) * 2,
        }

    async def broadcast_online(self) -> None:
        payload = {"t": "online", **self.online_stats()}
        for conn in list(self.conns.values()):
            await conn.send(payload)

    def leaderboard(self, limit: int = 50, game: str = games.DEFAULT_GAME) -> list[dict[str, object]]:
        return [
            {
                "place": i,
                "id": r["id"],
                "name": r["name"],
                "rating": r["rating"],
                "games": r["games"],
                "wins": r["wins"],
            }
            for i, r in enumerate(storage.top(self.db, game, limit), start=1)
        ]

    def ticket_for(
        self,
        conn: Conn,
        duration: int,
        level: str,
        game: str = games.DEFAULT_GAME,
        *,
        now: float,
    ) -> Ticket:
        info = games.info(game)
        game = info.id
        return Ticket(
            user_id=conn.user_id,
            name=conn.user.name,
            rating=conn.rating(game),
            games=conn.played(game),
            lang=conn.lang,
            photo_url=conn.user.photo_url,
            duration=duration if duration in DURATIONS else info.duration,
            # Где примеров нет, сложность нечему настраивать — и очередь
            # незачем делить на четыре по признаку, который ни на что не влияет.
            level=(level if level in LEVELS else "auto") if info.math else "auto",
            joined_at=now,
            game=game,
        )

    @staticmethod
    def _wanted(data: dict) -> tuple[int, str, str]:
        """Что просит клиент: длительность, уровень, игра."""

        try:
            duration = int(data.get("duration", -1) if data.get("duration") is not None else -1)
        except (TypeError, ValueError):
            duration = -1
        return duration, str(data.get("level", "auto")), games.normalize(data.get("game"))

    # ── HTTP ────────────────────────────────────────────────────────

    async def index(self, _: web.Request) -> web.StreamResponse:
        return web.FileResponse(
            WEBAPP_DIR / "index.html",
            headers={"Cache-Control": "no-cache"},
        )

    async def health(self, _: web.Request) -> web.Response:
        return web.json_response(
            {
                "ok": True,
                "online": len(self.conns),
                "queue": len(self.queue),
                "matches": len(self.matches),
                **storage.totals(self.db),
            }
        )

    @property
    def tg_script_path(self) -> Path:
        return self.config.data_dir / TG_SCRIPT_NAME

    async def refresh_tg_script(self) -> bool:
        """Забирает свежую библиотеку Telegram к себе. True — получилось."""

        try:
            async with ClientSession(timeout=ClientTimeout(total=20)) as session:
                async with session.get(TG_SCRIPT_URL) as response:
                    response.raise_for_status()
                    body = await response.text()
        except Exception as exc:  # сеть, блокировка, что угодно
            log.warning("Не удалось получить %s: %s", TG_SCRIPT_URL, exc)
            return False

        # Заодно убеждаемся, что нам отдали именно её, а не страницу-заглушку.
        if "WebApp" not in body or len(body) < 2000:
            log.warning("По адресу %s пришло что-то не то", TG_SCRIPT_URL)
            return False

        self.config.data_dir.mkdir(parents=True, exist_ok=True)
        self.tg_script_path.write_text(body, encoding="utf-8")
        log.info("Библиотека Telegram обновлена (%s байт)", len(body))
        return True

    async def tg_script(self, _: web.Request) -> web.StreamResponse:
        """Отдаёт библиотеку Telegram со своего домена.

        У части операторов telegram.org с телефона не открывается — тогда в
        Mini App не появляется window.Telegram, и игра не может узнать, кто
        зашёл. Поэтому файл держим у себя и раздаём сами, а раз в неделю
        обновляем из первоисточника.
        """

        path = self.tg_script_path
        stale = not path.is_file() or (
            time.time() - path.stat().st_mtime > TG_SCRIPT_MAX_AGE
        )
        if stale:
            await self.refresh_tg_script()
        if not path.is_file():
            # Пусть страница попробует взять её напрямую у Telegram.
            raise web.HTTPBadGateway(text="// библиотека Telegram недоступна")
        return web.FileResponse(
            path,
            headers={
                "Content-Type": "application/javascript; charset=utf-8",
                "Cache-Control": "public, max-age=3600",
            },
        )

    async def api_top(self, request: web.Request) -> web.Response:
        try:
            limit = max(1, min(100, int(request.query.get("limit", 50))))
        except ValueError:
            limit = 50
        game = games.normalize(request.query.get("game"))
        return web.json_response({"top": self.leaderboard(limit, game), "game": game})

    # ── WebSocket ───────────────────────────────────────────────────

    async def websocket(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=30, max_msg_size=MAX_MESSAGE_BYTES)
        await ws.prepare(request)

        conn: Conn | None = None
        try:
            async for msg in ws:
                if msg.type is not WSMsgType.TEXT:
                    continue
                try:
                    data = json.loads(msg.data)
                except (json.JSONDecodeError, TypeError):
                    continue
                if not isinstance(data, dict):
                    continue

                kind = str(data.get("t", ""))
                if conn is None:
                    if kind != "hello":
                        await ws.send_str(json.dumps({"t": "error", "code": "no_hello"}))
                        break
                    conn = await self._hello(ws, data)
                    if conn is None:
                        break
                    continue
                await self._on_message(conn, kind, data)
        finally:
            if conn is not None:
                await self._on_close(conn)
        return ws

    async def _hello(self, ws: web.WebSocketResponse, data: dict) -> Conn | None:
        """Первое сообщение: проверяем подпись Telegram и заводим игрока."""

        try:
            user = authenticate(
                str(data.get("initData", "")),
                self.config.bot_token,
                dev_mode=self.config.dev_mode,
                dev_fallback=WebAppUser(
                    id=int(data.get("devId", 1)),
                    first_name=f"Игрок {data.get('devId', 1)}",
                ),
            )
        except (AuthError, ValueError) as exc:
            log.info("Отказ во входе: %s", exc)
            await ws.send_str(
                json.dumps({"t": "error", "code": "auth", "message": str(exc)})
            )
            return None

        row = storage.get_player(self.db, user.id)
        lang = normalize(row["lang"] if row else user.language_code)
        row = storage.touch_player(
            self.db,
            user.id,
            user.name,
            username=user.username,
            photo_url=user.photo_url,
            lang=lang,
        )

        conn = Conn(
            ws=ws,
            user=user,
            lang=lang,
            scores={g: storage.rating_of(self.db, user.id, g) for g in games.GAME_IDS},
        )

        # Открыли игру во второй раз — старое окно закрываем, иначе на один
        # матч будет два экрана и оба будут мешать друг другу.
        old = self.conns.get(user.id)
        if old is not None and old.ws is not ws:
            with contextlib.suppress(Exception):
                await old.send({"t": "error", "code": "replaced"})
                await old.ws.close()
        self.conns[user.id] = conn

        await conn.send(
            {
                "t": "ready",
                "profile": self.profile(conn),
                "strings": ui_strings(conn.lang),
                "lang": conn.lang,
                "durations": list(DURATIONS),
                "levels": list(LEVELS),
                "win_steps": WIN_STEPS,
                "games": list(games.GAME_IDS),
                "game_info": {
                    g: {"math": games.info(g).math, "duration": games.info(g).duration}
                    for g in games.GAME_IDS
                },
                "bot": self.bot_username,
                "start_param": user.start_param,
                **self.online_stats(),
            }
        )

        # Друг принял вызов, пока нас не было, — начинаем бой немедленно.
        if await self._resume_accepted_room(conn, time.monotonic()):
            return conn

        # Вернулся в идущий матч — сразу возвращаем на поле, а не в меню.
        match = self.match_for(user.id)
        if match is not None and match.state != STATE_FINISHED:
            now = time.monotonic()
            match.reconnect(user.id, now)
            await self._send_found(conn, match, now)
            side = match.side(user.id)
            if side is not None and side.task is not None:
                await conn.send({"t": "task", **side.task.public()})
            await conn.send({"t": "state", **match.snapshot(user.id, now)})
        return conn

    async def _on_message(self, conn: Conn, kind: str, data: dict) -> None:
        now = time.monotonic()

        if kind == "ping":
            await conn.send({"t": "pong", "ts": data.get("ts")})

        elif kind == "find":
            if self.match_for(conn.user_id) is not None:
                return
            ticket = self.ticket_for(conn, *self._wanted(data), now=now)
            self.queue.add(ticket)
            self._offered.discard(conn.user_id)
            await conn.send(
                {
                    "t": "queued",
                    "waiting": self.queue.waiting_like(
                        ticket.duration, ticket.level, ticket.game
                    ),
                    "duration": ticket.duration,
                    "level": ticket.level,
                    "game": ticket.game,
                }
            )

        elif kind == "cancel":
            self.queue.remove(conn.user_id)
            self._offered.discard(conn.user_id)
            await conn.send({"t": "idle"})

        elif kind == "room":
            ticket = self.ticket_for(conn, *self._wanted(data), now=now)
            room = self.queue.create_room(ticket, now)
            await conn.send(
                {
                    "t": "room",
                    "code": room.code,
                    "link": self.invite_link(room.code),
                    "group": False,
                    "game": ticket.game,
                }
            )

        elif kind == "play_bot":
            await self._start_robot_match(conn, now, *self._wanted(data))

        elif kind == "players":
            await self._send_players(
                conn, int(data.get("offset", 0) or 0), games.normalize(data.get("game"))
            )

        # ── морской бой ──
        elif kind == "place":
            await self._place(conn, data, now)

        elif kind == "sea_random":
            match = self.match_for(conn.user_id)
            if isinstance(match, SeaMatch):
                await conn.send({"t": "sea_layout", "layout": match.random_layout()})

        elif kind == "fire":
            await self._fire(conn, data, now)

        # ── пять в ряд ──
        elif kind == "move":
            await self._move(conn, data, now)

        elif kind == "challenge":
            await self._challenge(conn, data, now)

        elif kind == "peek":
            # Гость пришёл по ссылке: сначала показываем, кто зовёт, и только
            # по нажатию кнопки заводим матч — иначе бой начинается врасплох.
            room = self.queue.find_room(str(data.get("code", "")))
            if room is None:
                await conn.send({"t": "room_error"})
                return
            if room.host.user_id == conn.user_id:
                # Свой же вызов: показываем ожидание, а не приглашение.
                # Если вызов брошен в чат, делиться кодом уже незачем.
                await conn.send(
                    {
                        "t": "room",
                        "code": room.code,
                        "link": self.invite_link(room.code),
                        "group": bool(room.chat_id),
                        "game": room.host.game,
                    }
                )
                return
            await conn.send(
                {
                    "t": "invite",
                    "code": room.code,
                    "game": room.host.game,
                    "duration": room.host.duration,
                    "level": room.host.level,
                    "host": {
                        "name": room.host.name,
                        "rating": room.host.rating,
                        "title": rating_mod.title(room.host.rating),
                        "photo": room.host.photo_url,
                    },
                }
            )

        elif kind == "join":
            await self._join_room(conn, data, now)

        elif kind == "answer":
            await self._answer(conn, data, now)

        elif kind == "lang":
            lang = normalize(str(data.get("lang", "")))
            conn.lang = lang
            storage.set_lang(self.db, conn.user_id, lang)
            await conn.send({"t": "strings", "strings": ui_strings(lang), "lang": lang})

        elif kind == "leave":
            self.queue.remove(conn.user_id)
            match = self.match_for(conn.user_id)
            if match is not None and match.state != STATE_FINISHED:
                other = match.opponent(conn.user_id)
                match.finish(now, "left", winner_id=other.user_id if other else None)
                await self._settle(match, now)
            else:
                await conn.send({"t": "idle"})

    async def _join_room(self, conn: Conn, data: dict, now: float) -> None:
        """Гость входит по коду или по ссылке."""

        room = self.queue.find_room(str(data.get("code", "")))
        wrong_room = (
            room is None
            or room.host.user_id == conn.user_id
            or (room.target and room.target != conn.user_id)
        )
        if wrong_room:
            await conn.send({"t": "room_error"})
            return

        host = self.conns.get(room.host.user_id)
        if host is None or self.match_for(room.host.user_id) is not None:
            # Хозяин вышел из игры — например, пошёл отправлять ссылку.
            # Приглашение не рвём: зовём его обратно и держим гостя.
            room.accepted_by = conn.user_id
            room.accepted_at = now
            self.queue.drop_ticket(conn.user_id)
            await self._call_host_back(room, conn)
            await conn.send({"t": "waiting_host", "name": room.host.name})
            return

        ticket = self.ticket_for(
            conn, room.host.duration, room.host.level, room.host.game, now=now
        )
        chat_id = room.chat_id
        pair = self.queue.join_room(room.code, ticket)
        if pair is None:
            await conn.send({"t": "room_error"})
            return
        await self._start_match(pair[0], pair[1], now, private=True, group_chat=chat_id)

    async def _call_host_back(self, room, guest: Conn) -> None:
        if self.notify is None:
            return
        row = storage.get_player(self.db, room.host.user_id)
        lang = row["lang"] if row else "ru"
        with contextlib.suppress(Exception):
            await self.notify(
                room.host.user_id,
                t("bot.accepted", lang, name=guest.user.name),
                button=t("bot.accepted.go", lang),
                url=self.config.webapp_url,
            )

    async def _resume_accepted_room(self, conn: Conn, now: float) -> bool:
        """Хозяин вернулся, а друг уже согласился — начинаем матч сразу."""

        for room in self.queue.rooms_of(conn.user_id):
            if not room.accepted_by:
                continue
            guest = self.conns.get(room.accepted_by)
            if guest is None or self.match_for(room.accepted_by) is not None:
                room.accepted_by = 0
                continue
            self.queue.rooms.pop(room.code, None)
            guest_ticket = self.ticket_for(
                guest, room.host.duration, room.host.level, room.host.game, now=now
            )
            await self._start_match(
                room.host, guest_ticket, now, private=True, group_chat=room.chat_id
            )
            return True
        return False

    async def _start_robot_match(
        self,
        conn: Conn,
        now: float,
        duration: int,
        level: str,
        game: str = games.DEFAULT_GAME,
    ) -> None:
        """Тренировка с роботом. В рейтинг не идёт и в историю не пишется."""

        if self.match_for(conn.user_id) is not None:
            return
        self.queue.remove(conn.user_id)
        self._offered.discard(conn.user_id)

        ticket = self.ticket_for(conn, duration, level, game, now=now)
        rating = conn.rating(ticket.game)
        opponent = games.robot_side(ticket.game, t("ui.robot", conn.lang), rating)
        match = games.make_match(
            ticket.game,
            ticket.to_side(),
            opponent,
            duration=ticket.duration,
            level=ticket.level,
            private=True,
        )
        match.begin(now)
        self.matches[match.id] = match
        self.match_of[conn.user_id] = match.id
        speed = robot_mod.speed_for(rating)
        self.robots[match.id] = games.make_robot(ticket.game, speed)
        log.info("Матч #%s (%s): %s против робота (%s)",
                 match.id, ticket.game, conn.user.name, speed)
        await self._send_found(conn, match, now)

    # ── морской бой ─────────────────────────────────────────────────

    async def _place(self, conn: Conn, data: dict, now: float) -> None:
        """Игрок расставил корабли. Проверяет сервер, клиенту не верим."""

        match = self.match_for(conn.user_id)
        if not isinstance(match, SeaMatch):
            return
        layout = data.get("layout")
        error = match.place(conn.user_id, layout if isinstance(layout, list) else [])
        await conn.send({"t": "placed", "ok": not error, "error": error})
        if not error:
            match.poll(now)
            await self._broadcast(match, now, force=True)

    async def _fire(self, conn: Conn, data: dict, now: float) -> None:
        match = self.match_for(conn.user_id)
        if not isinstance(match, SeaMatch):
            return
        try:
            row, col = int(data.get("row")), int(data.get("col"))
        except (TypeError, ValueError):
            return
        shot = match.fire(conn.user_id, row, col, now)
        if shot.get("result") not in SHOT_RESULTS:
            # Не твой ход или клетка уже открыта — об этом знает только стрелявший.
            await conn.send({"t": "shot", **self._json_shot(shot)})
        await self._dispatch_shots(match)

        if match.state == STATE_FINISHED:
            await self._settle(match, now)
        else:
            await self._broadcast(match, now, force=True)

    # ── пять в ряд ──────────────────────────────────────────────────

    async def _move(self, conn: Conn, data: dict, now: float) -> None:
        """Игрок поставил свой знак. Проверяет сервер, клиенту не верим."""

        match = self.match_for(conn.user_id)
        if not isinstance(match, FiveMatch):
            return
        try:
            row, col = int(data.get("row")), int(data.get("col"))
        except (TypeError, ValueError):
            return
        result = match.play(conn.user_id, row, col, now)
        if result.get("result") != "ok":
            # Занято или не твой ход — об этом знает только сходивший.
            await conn.send({"t": "move_error", "reason": result.get("result")})
            return

        # Сначала показываем поле обоим, и только потом итог: победную линию
        # надо успеть увидеть, а не сразу уехать на экран результата.
        await self._broadcast(match, now, force=True)
        if match.state == STATE_FINISHED:
            await self._settle(match, now)

    async def _dispatch_shots(self, match: Match) -> None:
        """Рассказывает о выстрелах обоим: стрелявшему — «выстрел», второму —
        «в тебя попали». Одинаково для людей и робота."""

        if not isinstance(match, SeaMatch):
            return
        for shooter_id, shot in match.take_shots():
            payload = self._json_shot(shot)
            shooter = self.conns.get(shooter_id)
            if shooter is not None:
                await shooter.send({"t": "shot", **payload})
            other = match.opponent(shooter_id)
            victim = self.conns.get(other.user_id) if other else None
            if victim is not None:
                await victim.send({"t": "incoming", **payload})

    @staticmethod
    def _json_shot(shot: dict) -> dict:
        """Кортежи клеток — в списки: JSON кортежей не знает."""

        out = dict(shot)
        if isinstance(out.get("cell"), tuple):
            out["cell"] = list(out["cell"])
        for key in ("ship", "halo"):
            if key in out:
                out[key] = [list(c) for c in out[key]]
        return out

    async def _send_players(
        self, conn: Conn, offset: int, game: str = games.DEFAULT_GAME
    ) -> None:
        """Все игроки: кто был в сети недавно — сверху, забытые — внизу."""

        offset = max(0, min(5000, offset))
        rows = storage.by_last_seen(
            self.db, game=game, exclude=conn.user_id, limit=PLAYERS_PAGE, offset=offset
        )
        people = [
            {
                "id": row["id"],
                "name": row["name"],
                "rating": row["rating"],
                "games": row["games"],
                "wins": row["wins"],
                # Сколько секунд назад заходил; кто в сети сейчас — отдельно.
                "seen": storage.seconds_since(row["last_seen_at"]),
                "online": row["id"] in self.conns,
                "busy": self.match_for(row["id"]) is not None,
            }
            for row in rows
        ]
        # Кто сейчас в игре, тот всегда выше: с ним можно сыграть прямо сейчас.
        people.sort(key=lambda p: (not p["online"], p["seen"]))
        await conn.send(
            {
                "t": "players",
                "list": people,
                "offset": offset,
                "total": storage.count_players(self.db, exclude=conn.user_id),
            }
        )

    async def _challenge(self, conn: Conn, data: dict, now: float) -> None:
        """Личный вызов: приглашение уходит человеку в чат и в открытую игру."""

        try:
            target = int(data.get("to", 0))
        except (TypeError, ValueError):
            return
        if target == conn.user_id or self.match_for(conn.user_id) is not None:
            return

        row = storage.get_player(self.db, target)
        if row is None:
            await conn.send({"t": "challenge_error", "reason": "gone"})
            return

        if now - self._called_at.get(conn.user_id, 0.0) < CHALLENGE_RATE:
            await conn.send({"t": "challenge_error", "reason": "too_often"})
            return
        if now - self._called.get((conn.user_id, target), 0.0) < CHALLENGE_COOLDOWN:
            await conn.send({"t": "challenge_error", "reason": "already"})
            return
        self._called_at[conn.user_id] = now
        self._called[(conn.user_id, target)] = now

        ticket = self.ticket_for(conn, *self._wanted(data), now=now)
        room = self.queue.create_room(ticket, now, target=target)

        # Если человек уже в игре — зовём прямо на экран, как звонок.
        peer = self.conns.get(target)
        if peer is not None and self.match_for(target) is None:
            await peer.send(
                {
                    "t": "invite",
                    "code": room.code,
                    "game": ticket.game,
                    "duration": ticket.duration,
                    "level": ticket.level,
                    "host": {
                        "name": conn.user.name,
                        "rating": ticket.rating,
                        "title": rating_mod.title(ticket.rating),
                        "photo": conn.user.photo_url,
                    },
                }
            )

        # И в чат — чтобы нашёл, даже если игру закрыл.
        if self.notify is not None:
            lang = row["lang"] if row else "ru"
            with contextlib.suppress(Exception):
                # Кнопка — самый короткий путь, ссылка — запасной: её можно
                # переслать, и она открывается даже там, где кнопки не видно.
                link = self.invite_link(room.code)
                await self.notify(
                    target,
                    t("bot.challenge", lang, name=conn.user.name, link=link),
                    button=t("bot.challenge.go", lang),
                    url=f"{self.config.webapp_url}?tgWebAppStartParam={room.code}",
                )

        await conn.send(
            {
                "t": "challenge_sent",
                "code": room.code,
                "to": {"id": target, "name": row["name"], "online": peer is not None},
            }
        )

    async def _answer(self, conn: Conn, data: dict, now: float) -> None:
        match = self.match_for(conn.user_id)
        if match is None or match.state != STATE_RUNNING:
            return
        if conn.flooding(now):
            return
        try:
            task_id = int(data.get("id", 0))
            value = int(data.get("v"))
        except (TypeError, ValueError):
            return
        solve_ms = data.get("ms")
        result = match.submit(
            conn.user_id,
            task_id,
            value,
            now,
            solve_ms=int(solve_ms) if isinstance(solve_ms, (int, float)) else None,
        )

        if result.accepted:
            await conn.send(
                {
                    "t": "ans",
                    "correct": result.correct,
                    "step": result.step,
                    "freeze_ms": result.freeze_ms,
                }
            )
            if result.task is not None:
                await conn.send({"t": "task", **result.task.public()})
        elif result.note in {"frozen", "too_fast"}:
            await conn.send({"t": "ans", "correct": False, "freeze_ms": result.freeze_ms})

        if match.state == STATE_FINISHED:
            await self._settle(match, now)
        else:
            await self._broadcast(match, now, force=True)

    async def _on_close(self, conn: Conn) -> None:
        now = time.monotonic()
        self.queue.drop_ticket(conn.user_id)
        if self.conns.get(conn.user_id) is conn:
            del self.conns[conn.user_id]
        match = self.match_for(conn.user_id)
        if match is not None and match.state != STATE_FINISHED:
            # Не заканчиваем сразу: вкладка могла свернуться на пару секунд.
            match.disconnect(conn.user_id, now)
            other = match.opponent(conn.user_id)
            if other is not None:
                peer = self.conns.get(other.user_id)
                if peer is not None:
                    await peer.send({"t": "opp_offline"})

    # ── матчи ───────────────────────────────────────────────────────

    async def _start_match(
        self,
        one: Ticket,
        other: Ticket,
        now: float,
        *,
        private: bool = False,
        group_chat: int = 0,
    ) -> Match:
        match = make_match(one, other, now, private=private)
        match.group_chat = group_chat
        self.matches[match.id] = match
        self.match_of[one.user_id] = match.id
        self.match_of[other.user_id] = match.id
        log.info(
            "Матч #%s: %s (%s) против %s (%s), %s сек, уровень %s",
            match.id, one.name, one.rating, other.name, other.rating,
            match.duration, match.level,
        )
        for user_id in (one.user_id, other.user_id):
            conn = self.conns.get(user_id)
            if conn is not None:
                await self._send_found(conn, match, now)
        return match

    async def _send_found(self, conn: Conn, match: Match, now: float) -> None:
        opp = match.opponent(conn.user_id)
        if opp is None:
            return
        await conn.send(
            {
                "t": "found",
                "match": match.id,
                "game": match.game,
                "duration": match.duration,
                "level": match.level,
                "win_steps": WIN_STEPS,
                "starts_in_ms": max(0, int((match.starts_at - now) * 1000)),
                "opp": {
                    "name": opp.name,
                    "rating": opp.rating,
                    "title": rating_mod.title(opp.rating),
                    "photo": opp.photo_url,
                },
            }
        )

    async def _broadcast(self, match: Match, now: float, force: bool = False) -> None:
        for side in (match.a, match.b):
            conn = self.conns.get(side.user_id)
            if conn is None:
                continue
            payload = match.snapshot(side.user_id, now)
            packed = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            stale = now - conn.last_state_at >= HEARTBEAT_SEC
            if not force and not stale and packed == conn.last_state:
                continue
            conn.last_state = packed
            conn.last_state_at = now
            await conn.send({"t": "state", **payload})

    async def _settle(self, match: Match, now: float) -> None:
        """Считает рейтинг, пишет итог в базу и рассылает результат."""

        deltas = {match.a.user_id: 0, match.b.user_id: 0}
        ratings = {match.a.user_id: match.a.rating, match.b.user_id: match.b.rating}

        if match.rated:
            winner = match.winner_key()
            new_a, new_b = rating_mod.both(
                match.a.rating, match.b.rating, winner, match.a.games, match.b.games
            )
            outcomes = {
                "a": ("win", "loss"),
                "b": ("loss", "win"),
                "draw": ("draw", "draw"),
            }[winner]
            for side, new_rating, outcome in (
                (match.a, new_a, outcomes[0]),
                (match.b, new_b, outcomes[1]),
            ):
                storage.apply_result(
                    self.db,
                    side.user_id,
                    match.game,
                    new_rating=new_rating,
                    outcome=outcome,
                    correct=side.score,
                    wrong=side.wrong,
                    best_streak=side.best_streak,
                )
                deltas[side.user_id] = new_rating - side.rating
                ratings[side.user_id] = new_rating

            storage.save_match(
                self.db,
                game=match.game,
                duration=match.duration,
                level=match.level,
                private=match.private,
                player_a=match.a.user_id,
                player_b=match.b.user_id,
                score_a=match.a.score,
                score_b=match.b.score,
                rope=match.margin(),
                winner=match.winner_id,
                reason=match.reason,
                delta_a=deltas[match.a.user_id],
                delta_b=deltas[match.b.user_id],
            )

        for side in (match.a, match.b):
            result = match.result_for(side.user_id)
            result.update(
                {
                    "rating": ratings[side.user_id],
                    "delta": deltas[side.user_id],
                    "rated": match.rated,
                }
            )
            conn = self.conns.get(side.user_id)
            if conn is not None:
                played = conn.played(match.game) + (1 if match.rated else 0)
                conn.scores[match.game] = (ratings[side.user_id], played)
                result["place"] = storage.place_of(self.db, side.user_id, match.game)
                await conn.send({"t": "end", **result})
            if self.notify is not None and match.rated:
                await self._notify_result(side.user_id, result)

        if match.group_chat and match.rated:
            await self._report_to_chat(match, ratings, deltas)

        for user_id in (match.a.user_id, match.b.user_id):
            self.match_of.pop(user_id, None)
        self.matches.pop(match.id, None)
        self.robots.pop(match.id, None)

    async def _report_to_chat(
        self, match: Match, ratings: dict[int, int], deltas: dict[int, int]
    ) -> None:
        """Счёт уходит в тот чат, где бросили вызов: его видят все."""

        if self.notify is None:
            return
        lang = match.a.lang or "ru"
        if match.winner_id is None:
            head = t("bot.duel.draw", lang, one=match.a.name, two=match.b.name)
        else:
            winner = match.a if match.winner_id == match.a.user_id else match.b
            loser = match.b if winner is match.a else match.a
            head = t("bot.duel.won", lang, winner=winner.name, loser=loser.name)

        def line(side) -> str:
            delta = deltas[side.user_id]
            sign = f"+{delta}" if delta > 0 else str(delta)
            return f"{side.name} {ratings[side.user_id]} ({sign})"

        body = t(
            "bot.duel.score",
            lang,
            score=f"{match.a.score} : {match.b.score}",
            one=line(match.a),
            two=line(match.b),
        )
        with contextlib.suppress(Exception):
            await self.notify(match.group_chat, f"{head}\n{body}")

    async def _notify_result(self, user_id: int, result: dict[str, object]) -> None:
        """Короткая запись об итоге в чат — чтобы история матчей была под рукой."""

        row = storage.get_player(self.db, user_id)
        lang = row["lang"] if row else "ru"
        head = t(
            f"bot.result.{result['outcome']}", lang, opponent=result.get("opp_name", "")
        )
        delta = int(result.get("delta", 0))
        body = t(
            "bot.result.body",
            lang,
            score=result.get("score", 0),
            opp_score=result.get("opp_score", 0),
            rating=result.get("rating", 0),
            delta=f"+{delta}" if delta > 0 else str(delta),
        )
        with contextlib.suppress(Exception):
            await self.notify(user_id, f"{head}\n{body}")

    # ── такт ────────────────────────────────────────────────────────

    async def tick(self, now: float | None = None) -> None:
        """Один такт: подобрать пары, продвинуть матчи, разослать состояние."""

        now = time.monotonic() if now is None else now

        for one, other in self.queue.find_pairs(now):
            await self._start_match(one, other, now)
        for room in list(self.queue.rooms.values()):
            if not room.accepted_by or now - room.accepted_at < HOST_GRACE_SEC:
                continue
            guest = self.conns.get(room.accepted_by)
            self.queue.rooms.pop(room.code, None)
            if guest is not None:
                await guest.send({"t": "host_gone", "name": room.host.name})
        self.queue.sweep_rooms(now)

        # Никто не пришёл за полминуты — предлагаем сыграть с роботом.
        for ticket in list(self.queue.tickets.values()):
            if ticket.user_id in self._offered:
                continue
            if ticket.waited(now) < WAIT_FOR_ROBOT:
                continue
            waiting = self.conns.get(ticket.user_id)
            if waiting is None:
                continue
            self._offered.add(ticket.user_id)
            await waiting.send(
                {
                    "t": "offer_bot",
                    "online": len(self.conns),
                    "waited": int(ticket.waited(now)),
                }
            )

        # Счётчик людей в сети: шлём, только когда он и правда изменился.
        if now - self._online_at >= 2.0:
            self._online_at = now
            stats = self.online_stats()
            if stats != self._online:
                self._online = stats
                await self.broadcast_online()

        for match in list(self.matches.values()):
            was_running = match.state == STATE_RUNNING
            changed = match.poll(now)

            if changed and not was_running and match.state == STATE_RUNNING:
                for side in (match.a, match.b):
                    conn = self.conns.get(side.user_id)
                    if conn is not None and side.task is not None:
                        await conn.send({"t": "start"})
                        await conn.send({"t": "task", **side.task.public()})

            robot = self.robots.get(match.id)
            moved = bool(robot and robot.step(match, now))
            if moved:
                await self._dispatch_shots(match)

            if match.state == STATE_FINISHED:
                await self._settle(match, now)
            else:
                await self._broadcast(match, now, force=moved)

    async def run_ticker(self) -> None:
        interval = self.config.tick_interval
        while True:
            started = time.monotonic()
            try:
                await self.tick(started)
            except Exception:  # такт не должен ронять сервер целиком
                log.exception("Сбой в такте")
            await asyncio.sleep(max(0.0, interval - (time.monotonic() - started)))

    def start(self) -> None:
        if self._ticker is None:
            self._ticker = asyncio.create_task(self.run_ticker())
        # Библиотеку Telegram готовим заранее: первый игрок не должен её ждать.
        if not self.tg_script_path.is_file():
            asyncio.create_task(self.refresh_tg_script())

    async def stop(self) -> None:
        if self._ticker is not None:
            self._ticker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._ticker
            self._ticker = None
        for conn in list(self.conns.values()):
            with contextlib.suppress(Exception):
                await conn.ws.close()


HUB_KEY: web.AppKey[Hub] = web.AppKey("duel_hub", Hub)


def make_app(hub: Hub) -> web.Application:
    app = web.Application()
    app[HUB_KEY] = hub
    app.router.add_get("/", hub.index)
    app.router.add_get("/health", hub.health)
    app.router.add_get("/api/top", hub.api_top)
    app.router.add_get("/tg-webapp.js", hub.tg_script)
    app.router.add_get("/ws", hub.websocket)
    app.router.add_static("/static/", WEBAPP_DIR, name="static")

    async def on_start(_: web.Application) -> None:
        hub.start()

    async def on_stop(_: web.Application) -> None:
        await hub.stop()

    app.on_startup.append(on_start)
    app.on_cleanup.append(on_stop)
    return app

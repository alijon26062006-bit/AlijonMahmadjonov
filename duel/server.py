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
from .game import (
    DURATIONS,
    STATE_FINISHED,
    STATE_RUNNING,
    WIN_STEPS,
    Match,
)
from .i18n import normalize, t, ui_strings
from .matchmaking import Queue, Ticket, make_match
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
    rating: int = 1000
    games: int = 0
    last_state: str = ""
    last_state_at: float = 0.0
    answers: deque[float] = field(default_factory=lambda: deque(maxlen=ANSWER_BURST))

    @property
    def user_id(self) -> int:
        return self.user.id

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
    ) -> None:
        self.config = config
        self.db = conn
        self.notify = notify
        self.bot_username = bot_username
        self.queue = Queue()
        self.conns: dict[int, Conn] = {}
        self.matches: dict[int, Match] = {}
        self.match_of: dict[int, int] = {}
        self._ticker: asyncio.Task[None] | None = None
        self._online: dict[str, int] = {}
        self._online_at = 0.0
        self._called: dict[tuple[int, int], float] = {}
        self._called_at: dict[int, float] = {}

    # ── служебное ───────────────────────────────────────────────────

    def match_for(self, user_id: int) -> Match | None:
        mid = self.match_of.get(user_id)
        return self.matches.get(mid) if mid else None

    def profile(self, conn: Conn) -> dict[str, object]:
        row = storage.get_player(self.db, conn.user_id)
        if row is None:
            return {}
        return {
            "id": row["id"],
            "name": row["name"],
            "rating": row["rating"],
            "title": rating_mod.title(row["rating"]),
            "games": row["games"],
            "wins": row["wins"],
            "losses": row["losses"],
            "draws": row["draws"],
            "correct": row["correct"],
            "best_streak": row["best_streak"],
            "place": storage.place_of(self.db, conn.user_id),
            "photo_url": row["photo_url"],
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

    def leaderboard(self, limit: int = 50) -> list[dict[str, object]]:
        return [
            {
                "place": i,
                "id": r["id"],
                "name": r["name"],
                "rating": r["rating"],
                "games": r["games"],
                "wins": r["wins"],
            }
            for i, r in enumerate(storage.top(self.db, limit), start=1)
        ]

    def ticket_for(self, conn: Conn, duration: int, level: str, now: float) -> Ticket:
        return Ticket(
            user_id=conn.user_id,
            name=conn.user.name,
            rating=conn.rating,
            games=conn.games,
            lang=conn.lang,
            photo_url=conn.user.photo_url,
            duration=duration if duration in DURATIONS else 60,
            level=level if level in LEVELS else "auto",
            joined_at=now,
        )

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
        return web.json_response({"top": self.leaderboard(limit)})

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
            ws=ws, user=user, lang=lang, rating=row["rating"], games=row["games"]
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
                "bot": self.bot_username,
                "start_param": user.start_param,
                **self.online_stats(),
            }
        )

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
            ticket = self.ticket_for(
                conn, int(data.get("duration", 60) or 0), str(data.get("level", "auto")), now
            )
            self.queue.add(ticket)
            await conn.send(
                {
                    "t": "queued",
                    "waiting": self.queue.waiting_like(ticket.duration, ticket.level),
                    "duration": ticket.duration,
                    "level": ticket.level,
                }
            )

        elif kind == "cancel":
            self.queue.remove(conn.user_id)
            await conn.send({"t": "idle"})

        elif kind == "room":
            ticket = self.ticket_for(
                conn, int(data.get("duration", 60) or 0), str(data.get("level", "auto")), now
            )
            room = self.queue.create_room(ticket, now)
            link = (
                f"https://t.me/{self.bot_username}?startapp={room.code}"
                if self.bot_username
                else ""
            )
            await conn.send({"t": "room", "code": room.code, "link": link})

        elif kind == "players":
            await self._send_players(conn, int(data.get("offset", 0) or 0))

        elif kind == "challenge":
            await self._challenge(conn, data, now)

        elif kind == "peek":
            # Гость пришёл по ссылке: сначала показываем, кто зовёт, и только
            # по нажатию кнопки заводим матч — иначе бой начинается врасплох.
            room = self.queue.find_room(str(data.get("code", "")))
            if room is None or room.host.user_id == conn.user_id:
                await conn.send({"t": "room_error"})
                return
            await conn.send(
                {
                    "t": "invite",
                    "code": room.code,
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
            code = str(data.get("code", ""))
            ticket = self.ticket_for(
                conn, int(data.get("duration", 60) or 0), str(data.get("level", "auto")), now
            )
            pair = self.queue.join_room(code, ticket)
            if pair is None:
                await conn.send({"t": "room_error"})
                return
            await self._start_match(pair[0], pair[1], now, private=True)

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

    async def _send_players(self, conn: Conn, offset: int) -> None:
        """Все игроки: кто был в сети недавно — сверху, забытые — внизу."""

        offset = max(0, min(5000, offset))
        rows = storage.by_last_seen(
            self.db, exclude=conn.user_id, limit=PLAYERS_PAGE, offset=offset
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

        ticket = self.ticket_for(
            conn, int(data.get("duration", 60) or 0), str(data.get("level", "auto")), now
        )
        room = self.queue.create_room(ticket, now, target=target)

        # Если человек уже в игре — зовём прямо на экран, как звонок.
        peer = self.conns.get(target)
        if peer is not None and self.match_for(target) is None:
            await peer.send(
                {
                    "t": "invite",
                    "code": room.code,
                    "duration": ticket.duration,
                    "level": ticket.level,
                    "host": {
                        "name": conn.user.name,
                        "rating": conn.rating,
                        "title": rating_mod.title(conn.rating),
                        "photo": conn.user.photo_url,
                    },
                }
            )

        # И в чат — чтобы нашёл, даже если игру закрыл.
        if self.notify is not None:
            lang = row["lang"] if row else "ru"
            with contextlib.suppress(Exception):
                await self.notify(
                    target,
                    t("bot.challenge", lang, name=conn.user.name),
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
        self.queue.remove(conn.user_id)
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
        self, one: Ticket, other: Ticket, now: float, *, private: bool = False
    ) -> Match:
        match = make_match(one, other, now, private=private)
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
                duration=match.duration,
                level=match.level,
                private=match.private,
                player_a=match.a.user_id,
                player_b=match.b.user_id,
                score_a=match.a.score,
                score_b=match.b.score,
                rope=match.rope(),
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
                conn.rating = ratings[side.user_id]
                conn.games += 1 if match.rated else 0
                result["place"] = storage.place_of(self.db, side.user_id)
                await conn.send({"t": "end", **result})
            if self.notify is not None and match.rated:
                await self._notify_result(side.user_id, result)

        for user_id in (match.a.user_id, match.b.user_id):
            self.match_of.pop(user_id, None)
        self.matches.pop(match.id, None)

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
        self.queue.sweep_rooms(now)

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

            if match.state == STATE_FINISHED:
                await self._settle(match, now)
            else:
                await self._broadcast(match, now)

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

"""Матч в морской бой на примерах.

Устроен как канат: оба решают примеры одновременно и не ждут друг друга.
Только верный ответ даёт не рывок, а снаряд — и им стреляют по полю
соперника. Кто первым потопит чужой флот, тот и победил.

Перед боем — расстановка: каждый ставит корабли у себя. Кто не успел за
минуту, получает случайную расстановку, чтобы не держать соперника.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import game as rules
from . import sea
from .game import (
    DISCONNECT_GRACE,
    REASON_ABANDONED,
    REASON_LEFT,
    REASON_TIME,
    STATE_COUNTDOWN,
    STATE_FINISHED,
    STATE_RUNNING,
    AnswerResult,
    Match,
    Side,
)

STATE_PLACING = "placing"
REASON_FLEET = "fleet"        # чужой флот потоплен целиком

# Сколько даём на расстановку. Дольше — соперник заскучает.
PLACE_SEC = 60.0
# Бой не бесконечен: кто больше попал к этому времени, тот и победил.
BATTLE_CAP_SEC = 6 * 60
# Снаряды не копятся без конца: стреляй, а не запасайся.
MAX_SHELLS = 3
# Исходы настоящего выстрела — тех, о которых узнаёт и тот, в кого стреляли.
SHOT_RESULTS = frozenset({sea.MISS, sea.HIT, sea.SUNK})


@dataclass
class SeaSide(Side):
    """Сторона морского боя: всё, что у стороны каната, плюс флот и снаряды."""

    board: sea.Board | None = None
    placed: bool = False
    shells: int = 0
    # Что нащупал у соперника — считается по его полю, но храним и здесь.
    shots_fired: int = 0
    hits_made: int = 0
    sunk_made: int = 0
    last_shot: tuple[int, int] | None = None


@dataclass
class SeaMatch(Match):
    """Правила боя. Очерёдности ходов нет — стреляет тот, у кого есть снаряд."""

    game: str = field(default="sea", init=False)
    place_deadline: float = 0.0
    # Выстрелы, о которых ещё не рассказали игрокам: (кто стрелял, что вышло).
    # Сюда попадают и выстрелы робота — сервер разошлёт их так же, как людские.
    unsent: list[tuple[int, dict]] = field(default_factory=list)
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        self._rng = random.Random(self.seed)

    # ── расстановка ─────────────────────────────────────────────────

    def begin(self, now: float, countdown: float | None = None) -> None:
        """Матч найден: сначала расставляем корабли, отсчёт — потом."""

        self.created_at = now
        self.state = STATE_PLACING
        self.place_deadline = now + PLACE_SEC
        for side in (self.a, self.b):
            if isinstance(side, SeaSide) and side.is_bot and not side.placed:
                self.auto_place(side)

    def place(self, user_id: int, layout: list[dict]) -> str:
        """Принимает расстановку игрока. Возвращает пустую строку или причину отказа."""

        side = self.side(user_id)
        if self.state != STATE_PLACING or not isinstance(side, SeaSide):
            return "not_placing"
        try:
            side.board = sea.build_board(layout)
        except sea.PlacementError as exc:
            return str(exc)
        side.placed = True
        return ""

    def auto_place(self, side: SeaSide) -> None:
        side.board = sea.build_board(sea.random_layout(self._rng))
        side.placed = True

    def random_layout(self) -> list[dict]:
        """Случайная расстановка по просьбе игрока — для кнопки «Случайно»."""

        return sea.random_layout(self._rng)

    @property
    def both_placed(self) -> bool:
        return all(isinstance(s, SeaSide) and s.placed for s in (self.a, self.b))

    # ── ход времени ─────────────────────────────────────────────────

    def activate(self, now: float) -> None:
        self.state = STATE_RUNNING
        self.starts_at = now
        self.deadline = now + (self.duration if self.duration > 0 else BATTLE_CAP_SEC)
        for side in (self.a, self.b):
            self._issue(side, now)

    def poll(self, now: float) -> bool:
        if self.state == STATE_FINISHED:
            return False

        # Ушедших ждём и во время расстановки: она длится до минуты,
        # и за это время человек вполне может пропасть насовсем.
        gone = [s for s in (self.a, self.b) if not s.connected and s.left_at is not None]
        if len(gone) == 2:
            self.finish(now, REASON_ABANDONED)
            return True
        for side in gone:
            if now - side.left_at >= DISCONNECT_GRACE:
                other = self.a if side is self.b else self.b
                self.finish(now, REASON_LEFT, winner_id=other.user_id)
                return True

        if self.state == STATE_PLACING:
            if now >= self.place_deadline:
                for side in (self.a, self.b):
                    if isinstance(side, SeaSide) and not side.placed:
                        self.auto_place(side)
            if self.both_placed:
                self.state = STATE_COUNTDOWN
                # Берём из модуля, а не копию: тесты укорачивают отсчёт.
                self.starts_at = now + rules.COUNTDOWN_SEC
                return True
            return False

        if self.state == STATE_COUNTDOWN:
            if now >= self.starts_at:
                self.activate(now)
                return True
            return False

        if now >= self.deadline:
            self.finish(now, REASON_TIME)
            return True
        return False

    # ── ответы и выстрелы ───────────────────────────────────────────

    def _reward(self, side: Side, step: int, now: float) -> AnswerResult:
        """Верный ответ — снаряд. Серия — два, но выше потолка не копится."""

        assert isinstance(side, SeaSide)
        side.shells = min(MAX_SHELLS, side.shells + step)
        task = self._issue(side, now)
        return AnswerResult(
            accepted=True, correct=True, step=step, task=task, shells=side.shells
        )

    def fire(self, user_id: int, row: int, col: int, now: float) -> dict[str, object]:
        """Выстрел по полю соперника. Стоит один снаряд."""

        side = self.side(user_id)
        opp = self.opponent(user_id)
        if (
            self.state != STATE_RUNNING
            or not isinstance(side, SeaSide)
            or not isinstance(opp, SeaSide)
            or opp.board is None
        ):
            return {"result": "not_running"}
        if side.shells <= 0:
            return {"result": "no_shells", "shells": 0}

        shot = opp.board.fire(row, col)
        if shot["result"] == sea.REPEAT:
            # Уже стреляли сюда — снаряд не тратим, человек просто промахнулся пальцем.
            shot["shells"] = side.shells
            return shot

        side.shells -= 1
        side.shots_fired += 1
        side.last_shot = (row, col)
        if shot["result"] in (sea.HIT, sea.SUNK):
            side.hits_made += 1
        if shot["result"] == sea.SUNK:
            side.sunk_made += 1
        shot["shells"] = side.shells
        self.unsent.append((user_id, shot))

        if opp.board.defeated:
            self.finish(now, REASON_FLEET, winner_id=user_id)
        return shot

    def take_shots(self) -> list[tuple[int, dict]]:
        """Забирает ещё не разосланные выстрелы."""

        shots, self.unsent = self.unsent, []
        return shots

    # ── итог ────────────────────────────────────────────────────────

    def finish(self, now: float, reason: str, winner_id: int | None = None) -> None:
        if self.state == STATE_FINISHED:
            return
        if winner_id is None and reason not in (REASON_ABANDONED,):
            # Время вышло: побеждает тот, кто больше попал; поровну — кто
            # больше решил; и то поровну — ничья.
            a, b = self.a, self.b
            if isinstance(a, SeaSide) and isinstance(b, SeaSide):
                if a.hits_made != b.hits_made:
                    winner_id = (a if a.hits_made > b.hits_made else b).user_id
                elif a.score != b.score:
                    winner_id = (a if a.score > b.score else b).user_id
        self.state = STATE_FINISHED
        self.finished_at = now
        self.reason = reason
        self.winner_id = winner_id

    @property
    def rated(self) -> bool:
        if self.has_bot or self.state != STATE_FINISHED:
            return False
        if self.reason == REASON_ABANDONED:
            return False
        if self.reason in (REASON_LEFT,):
            # Ушёл до расстановки — не матч, а недоразумение.
            return self.both_placed
        return True

    def margin(self) -> int:
        a, b = self.a, self.b
        if isinstance(a, SeaSide) and isinstance(b, SeaSide):
            return a.hits_made - b.hits_made
        return 0

    # ── что видит клиент ────────────────────────────────────────────

    def _enemy_view(self, me: SeaSide, opp: SeaSide) -> dict[str, object]:
        """Чужое поле глазами стреляющего: только то, что уже нащупано."""

        if opp.board is None:
            return {"hits": [], "misses": [], "sunk": [], "alive": len(sea.FLEET)}
        board = opp.board
        hits = sorted(spot for ship in board.ships for spot in ship.hits)
        return {
            "hits": hits,
            "misses": sorted(spot for spot in board.shots if board.ship_at(spot) is None),
            "sunk": [sorted(ship.cells) for ship in board.ships if ship.sunk],
            "alive": board.alive,
            "last": list(me.last_shot) if me.last_shot else None,
        }

    def snapshot(self, user_id: int, now: float) -> dict[str, object]:
        me = self.side(user_id)
        opp = self.opponent(user_id)
        if not isinstance(me, SeaSide) or not isinstance(opp, SeaSide):
            return {}
        return {
            "game": self.game,
            "state": self.state,
            "left_ms": self.left_ms(now) if self.state == STATE_RUNNING else None,
            "place_left_ms": max(0, int((self.place_deadline - now) * 1000))
            if self.state == STATE_PLACING
            else 0,
            "starts_in_ms": max(0, int((self.starts_at - now) * 1000))
            if self.state == STATE_COUNTDOWN
            else 0,
            "me": {
                "score": me.score,
                "streak": me.streak,
                "wrong": me.wrong,
                "freeze_ms": me.freeze_ms(now),
                "shells": me.shells,
                "placed": me.placed,
                "board": me.board.own_view() if me.board else None,
                "hits": me.hits_made,
                "sunk": me.sunk_made,
            },
            "opp": {
                "score": opp.score,
                "streak": opp.streak,
                "connected": opp.connected,
                "placed": opp.placed,
                "hits": opp.hits_made,
                "sunk": opp.sunk_made,
                "last": list(opp.last_shot) if opp.last_shot else None,
            },
            "enemy": self._enemy_view(me, opp),
        }

    def result_for(self, user_id: int) -> dict[str, object]:
        me = self.side(user_id)
        opp = self.opponent(user_id)
        if not isinstance(me, SeaSide) or not isinstance(opp, SeaSide):
            return {}
        if self.winner_id is None:
            outcome = "draw"
        elif self.winner_id == user_id:
            outcome = "win"
        else:
            outcome = "loss"
        return {
            "game": self.game,
            "outcome": outcome,
            "reason": self.reason,
            "score": me.score,
            "opp_score": opp.score,
            "hits": me.hits_made,
            "opp_hits": opp.hits_made,
            "sunk": me.sunk_made,
            "opp_sunk": opp.sunk_made,
            "shots": me.shots_fired,
            "wrong": me.wrong,
            "best_streak": me.best_streak,
            "accuracy": me.accuracy,
            "avg_ms": me.avg_ms,
            "fastest_ms": me.fastest_ms,
            "opp_name": opp.name,
            "duration": self.duration,
            "fleet": me.board.own_view() if me.board else None,
            "enemy_fleet": [sorted(s.cells) for s in opp.board.ships] if opp.board else [],
        }

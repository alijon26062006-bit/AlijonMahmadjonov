"""Морской бой — по очереди, как на бумаге.

Сначала расстановка: каждый ставит корабли у себя. Кто не успел за минуту,
получает случайную расстановку, чтобы не держать соперника.

Потом бьют по очереди. Попал — стреляешь ещё раз, промахнулся — ход
переходит к сопернику. Кто первым потопит чужой флот, тот и выиграл.
Примеров здесь нет: это чистый морской бой, математика живёт в канате.
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
    Match,
    Side,
)

STATE_PLACING = "placing"
REASON_FLEET = "fleet"        # чужой флот потоплен целиком
REASON_IDLE = "idle"          # игрок перестал ходить

# Сколько даём на расстановку. Дольше — соперник заскучает.
PLACE_SEC = 60.0
# Сколько думает над выстрелом один игрок. Не выстрелил — ход уходит.
TURN_SEC = 30.0
# Три пропуска подряд — человек просто ушёл, засчитываем поражение.
MAX_SKIPS = 3
# Бой не бесконечен: кто больше попал к этому времени, тот и победил.
BATTLE_CAP_SEC = 10 * 60
# Исходы настоящего выстрела — тех, о которых узнаёт и тот, в кого стреляли.
SHOT_RESULTS = frozenset({sea.MISS, sea.HIT, sea.SUNK})


def _ms(seconds: float) -> int:
    """Миллисекунды с точностью до полусекунды.

    Точное время слать незачем: часы клиент дальше отсчитывает сам, а от
    точности до миллисекунды состояние менялось бы каждый такт и летело
    бы по сети двадцать раз в секунду.
    """

    return max(0, int(seconds * 1000) // 500 * 500)


@dataclass
class SeaSide(Side):
    """Сторона морского боя: всё, что у стороны каната, плюс флот и выстрелы.

    Счёт тут — попадания, промахи — `wrong`, серия — попадания подряд.
    Поэтому рейтинг, точность и статистика считаются тем же кодом, что и
    в канате, без единой поправки на игру.
    """

    board: sea.Board | None = None
    placed: bool = False
    shots_fired: int = 0
    sunk_made: int = 0
    last_shot: tuple[int, int] | None = None
    # Сколько ходов подряд человек продумал до конца таймера.
    skips: int = 0

    @property
    def hits_made(self) -> int:
        return self.score

    @property
    def misses_made(self) -> int:
        return self.wrong


@dataclass
class SeaMatch(Match):
    """Правила боя: ходят по очереди, попал — ходишь снова."""

    game: str = field(default="sea", init=False)
    place_deadline: float = 0.0
    # Чей сейчас ход и до какого времени он длится.
    turn: int = 0
    turn_deadline: float = 0.0
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
        """Бой пошёл. Кто ходит первым — решает жребий, иначе первый ход
        достался бы тому, кто раньше нажал «Готов»."""

        self.state = STATE_RUNNING
        self.starts_at = now
        self.deadline = now + (self.duration if self.duration > 0 else BATTLE_CAP_SEC)
        self.turn = self._rng.choice([self.a.user_id, self.b.user_id])
        self.turn_deadline = now + TURN_SEC

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
        if now >= self.turn_deadline:
            self._skip(now)
            return True
        return False

    # ── ходы и выстрелы ─────────────────────────────────────────────

    def _pass_turn(self, now: float) -> None:
        other = self.opponent(self.turn)
        if other is not None:
            self.turn = other.user_id
        self.turn_deadline = now + TURN_SEC

    def _skip(self, now: float) -> None:
        """Время хода вышло. Ход уходит, а совсем неходящий проигрывает."""

        side = self.side(self.turn)
        if isinstance(side, SeaSide):
            side.skips += 1
            if side.skips >= MAX_SKIPS:
                other = self.opponent(self.turn)
                self.finish(
                    now, REASON_IDLE, winner_id=other.user_id if other else None
                )
                return
        self._pass_turn(now)

    def my_turn(self, user_id: int) -> bool:
        return self.state == STATE_RUNNING and self.turn == user_id

    def fire(self, user_id: int, row: int, col: int, now: float) -> dict[str, object]:
        """Выстрел по полю соперника. Попал — ход остаётся, мимо — уходит."""

        side = self.side(user_id)
        opp = self.opponent(user_id)
        if (
            self.state != STATE_RUNNING
            or not isinstance(side, SeaSide)
            or not isinstance(opp, SeaSide)
            or opp.board is None
        ):
            return {"result": "not_running"}
        if self.turn != user_id:
            return {"result": "not_your_turn"}

        shot = opp.board.fire(row, col)
        if shot["result"] == sea.REPEAT:
            # Палец попал в уже открытую клетку — это не выстрел, ход остаётся.
            return shot

        side.shots_fired += 1
        side.skips = 0
        side.last_shot = (row, col)
        if shot["result"] == sea.MISS:
            side.wrong += 1
            side.streak = 0
        else:
            side.score += 1
            side.streak += 1
            side.best_streak = max(side.best_streak, side.streak)
        if shot["result"] == sea.SUNK:
            side.sunk_made += 1
        self.unsent.append((user_id, shot))

        if opp.board.defeated:
            self.finish(now, REASON_FLEET, winner_id=user_id)
            return shot

        # Попал — стреляешь ещё, промахнулся — очередь соперника.
        if shot["result"] == sea.MISS:
            self._pass_turn(now)
        else:
            self.turn_deadline = now + TURN_SEC
        shot["again"] = self.turn == user_id
        return shot

    def take_shots(self) -> list[tuple[int, dict]]:
        """Забирает ещё не разосланные выстрелы."""

        shots, self.unsent = self.unsent, []
        return shots

    # ── итог ────────────────────────────────────────────────────────

    def finish(self, now: float, reason: str, winner_id: int | None = None) -> None:
        if self.state == STATE_FINISHED:
            return
        if winner_id is None and reason != REASON_ABANDONED:
            # Время вышло: побеждает тот, кто больше попал; поровну —
            # у кого больше потопленных; и то поровну — ничья.
            a, b = self.a, self.b
            if isinstance(a, SeaSide) and isinstance(b, SeaSide):
                if a.hits_made != b.hits_made:
                    winner_id = (a if a.hits_made > b.hits_made else b).user_id
                elif a.sunk_made != b.sunk_made:
                    winner_id = (a if a.sunk_made > b.sunk_made else b).user_id
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
        if self.reason in (REASON_LEFT, REASON_IDLE):
            # Ушёл до расстановки — не матч, а недоразумение.
            return self.both_placed
        a, b = self.a, self.b
        if isinstance(a, SeaSide) and isinstance(b, SeaSide):
            return (a.shots_fired + b.shots_fired) > 0
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
        running = self.state == STATE_RUNNING
        return {
            "game": self.game,
            "state": self.state,
            "left_ms": self.left_ms(now) if running else None,
            "place_left_ms": _ms(self.place_deadline - now)
            if self.state == STATE_PLACING
            else 0,
            "starts_in_ms": _ms(self.starts_at - now)
            if self.state == STATE_COUNTDOWN
            else 0,
            "my_turn": running and self.turn == user_id,
            "turn_ms": _ms(self.turn_deadline - now) if running else 0,
            "me": {
                "placed": me.placed,
                "board": me.board.own_view() if me.board else None,
                "hits": me.hits_made,
                "sunk": me.sunk_made,
                "shots": me.shots_fired,
                "streak": me.streak,
            },
            "opp": {
                "connected": opp.connected,
                "placed": opp.placed,
                "hits": opp.hits_made,
                "sunk": opp.sunk_made,
                "shots": opp.shots_fired,
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
            "score": me.hits_made,
            "opp_score": opp.hits_made,
            "hits": me.hits_made,
            "opp_hits": opp.hits_made,
            "sunk": me.sunk_made,
            "opp_sunk": opp.sunk_made,
            "shots": me.shots_fired,
            "opp_shots": opp.shots_fired,
            "best_streak": me.best_streak,
            "accuracy": me.accuracy,
            "opp_name": opp.name,
            "duration": self.duration,
            "fleet": me.board.own_view() if me.board else None,
            "enemy_fleet": [sorted(s.cells) for s in opp.board.ships] if opp.board else [],
            # Куда ты бил — вместе с последним выстрелом: состояние после него
            # уже не рассылается, а на экране итога оно и нужно.
            "enemy_view": self._enemy_view(me, opp),
        }

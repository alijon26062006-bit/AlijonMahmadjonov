"""Робот для крестиков-ноликов.

Смотрит каждую свободную клетку и считает две вещи: не выигрывает ли она
прямо сейчас и не выигрывает ли соперник, если её не занять. Остальное —
привычные приоритеты: центр, углы, стороны.

Слабый робот думает дольше и иногда ходит мимо лучшего, но чужую тройку
закрывает всегда: соперник, который её проглядел, выглядит сломанным, а не
слабым. Сильный не проигрывает никогда — на поле три на три это возможно.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import tic
from .game import STATE_RUNNING
from .robot import ROBOT_ID
from .tic_match import TicMatch, TicSide

# Сколько робот думает над ходом. Мгновенный ответ выглядит как автомат.
THINK = {
    "slow": (1.6, 3.0),
    "normal": (1.0, 2.0),
    "fast": (0.6, 1.3),
}
# Как часто робот ходит мимо лучшего — но не тогда, когда решается партия.
SLOPPY = {"slow": 0.4, "normal": 0.15, "fast": 0.0}

# Чего стоит клетка сама по себе: центр сильнее углов, углы сильнее сторон.
SPOT_VALUE = {(1, 1): 3, (0, 0): 2, (0, 2): 2, (2, 0): 2, (2, 2): 2}

Cell = tuple[int, int]


def wins_with(board: tic.Board, spot: Cell, mark: str) -> bool:
    """Выиграет ли этот знак, если его поставить сюда."""

    board[spot] = mark
    line = tic.winning_line(board, *spot)
    del board[spot]
    return bool(line)


@dataclass
class TicRobot:
    """Ходит за робота в крестиках-ноликах."""

    speed: str = "normal"
    seed: int | None = None
    # Когда поставит знак. Ноль — ещё не начал думать в этот ход.
    think_at: float = 0.0
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    @property
    def _pause(self) -> tuple[float, float]:
        return THINK.get(self.speed, THINK["normal"])

    def step(self, match: TicMatch, now: float) -> bool:
        """Один такт. True — робот только что сходил."""

        if (
            match.state != STATE_RUNNING
            or match.between_rounds
            or not match.my_turn(ROBOT_ID)
        ):
            self.think_at = 0.0
            return False
        if not self.think_at:
            self.think_at = now + self._rng.uniform(*self._pause)
            return False
        if now < self.think_at:
            return False

        spot = self.choose(match)
        self.think_at = 0.0
        if spot is None:
            return False
        return match.play(ROBOT_ID, spot[0], spot[1], now).get("result") == "ok"

    # ── куда ставить ────────────────────────────────────────────────

    def choose(self, match: TicMatch) -> Cell | None:
        me = match.side(ROBOT_ID)
        opp = match.opponent(ROBOT_ID)
        if not isinstance(me, TicSide) or not isinstance(opp, TicSide):
            return None
        board = match.board
        spots = tic.free_cells(board)
        if not spots:
            return None

        # Своя тройка кончает партию, чужую закрываем сразу следом.
        for mark in (me.mark, opp.mark):
            winning = [spot for spot in spots if wins_with(board, spot, mark)]
            if winning:
                return self._rng.choice(winning)

        if self._rng.random() < SLOPPY.get(self.speed, 0.0):
            return self._rng.choice(spots)

        best = max(SPOT_VALUE.get(spot, 1) for spot in spots)
        return self._rng.choice([s for s in spots if SPOT_VALUE.get(s, 1) == best])

"""Робот для «Пять в ряд».

Думает без перебора вглубь: смотрит каждую свободную клетку рядом с уже
поставленными знаками и считает, что она даёт ему и что отнимает у соперника.
Этого хватает, чтобы он выигрывал сам и не зевал чужую четвёрку.

Слабый робот думает дольше, смотрит только вплотную к знакам и иногда
ставит не лучший ход из нескольких хороших — но чужую пятёрку закрывает
всегда: соперник, который её проглядел, выглядит сломанным, а не слабым.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import five
from .five_match import FiveMatch, FiveSide
from .game import STATE_RUNNING
from .robot import ROBOT_ID

# Сколько робот думает над ходом. Мгновенный ответ выглядит как автомат.
THINK = {
    "slow": (1.8, 3.4),
    "normal": (1.2, 2.4),
    "fast": (0.7, 1.5),
}
# Насколько робот придирчив к ходу и как далеко от знаков смотрит.
SLOPPY = {"slow": 0.35, "normal": 0.12, "fast": 0.0}
REACH = {"slow": 1, "normal": 2, "fast": 2}

# Чего стоит линия своих знаков. Открытая с двух сторон вдвое опаснее.
VALUE = {1: 1, 2: 12, 3: 120, 4: 1500, 5: 200000}
# Защита чуть дешевле нападения: при равном счёте лучше строить своё.
DEFENCE = 0.9

Cell = tuple[int, int]


def line_value(board: five.Board, spot: Cell, mark: str) -> int:
    """Сколько стоит поставить этот знак в эту клетку.

    Считается по всем четырём направлениям: длина получившейся линии и
    сколько у неё открытых концов — запертая с обеих сторон четвёрка
    не стоит ничего.
    """

    row, col = spot
    total = 0
    for dr, dc in five.LINES:
        run = 1
        ends = 0
        for step in (1, -1):
            r, c = row + dr * step, col + dc * step
            while board.get((r, c)) == mark:
                run += 1
                r, c = r + dr * step, c + dc * step
            if five.free(board, r, c):
                ends += 1
        if run >= five.WIN:
            return VALUE[5]
        if ends == 0:
            continue
        total += VALUE[min(run, 4)] * (2 if ends == 2 else 1)
    return total


@dataclass
class FiveRobot:
    """Ходит за робота в «Пять в ряд»."""

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

    def step(self, match: FiveMatch, now: float) -> bool:
        """Один такт. True — робот только что сходил."""

        if match.state != STATE_RUNNING or not match.my_turn(ROBOT_ID):
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

    def choose(self, match: FiveMatch) -> Cell | None:
        me = match.side(ROBOT_ID)
        opp = match.opponent(ROBOT_ID)
        if not isinstance(me, FiveSide) or not isinstance(opp, FiveSide):
            return None
        board = match.board
        spots = five.neighbourhood(board, REACH.get(self.speed, 2))
        if not spots:
            return None

        best: list[Cell] = []
        best_value = -1
        for spot in spots:
            mine = line_value(board, spot, me.mark)
            theirs = line_value(board, spot, opp.mark)
            # Своя пятёрка важнее всего, чужую закрываем сразу следом.
            value = max(mine, theirs * DEFENCE) + min(mine, theirs) * 0.1
            if value > best_value:
                best_value, best = value, [spot]
            elif value == best_value:
                best.append(spot)

        # Ход, который прямо сейчас выигрывает или спасает, робот не портит.
        if best_value < VALUE[4]:
            sloppy = SLOPPY.get(self.speed, 0.0)
            if sloppy and self._rng.random() < sloppy:
                return self._rng.choice(spots)
        return self._rng.choice(best)

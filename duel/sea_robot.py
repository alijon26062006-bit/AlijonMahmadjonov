"""Робот для морского боя.

Ходит наравне с человеком: дождался своего хода, «прицелился» и выстрелил.
Пока ничего не нашёл — ищет по полю через клетку, попал — добивает вокруг,
понял направление — идёт вдоль корабля.

Слабый робот целится дольше и иногда бьёт наугад, даже когда корабль уже
ранен: у новичка должен быть шанс.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import sea
from .robot import ROBOT_ID
from .sea_match import STATE_RUNNING, SeaMatch, SeaSide

# Сколько робот «целится» перед выстрелом. Мгновенный ответ выглядит как автомат.
AIM = {
    "slow": (2.0, 3.6),
    "normal": (1.3, 2.5),
    "fast": (0.8, 1.6),
}
# Насколько робот следует своему плану добивания. Остальное — выстрел наугад.
SMART = {"slow": 0.6, "normal": 0.85, "fast": 1.0}

Cell = tuple[int, int]


@dataclass
class SeaRobot:
    """Ходит за робота в морском бою."""

    speed: str = "normal"
    seed: int | None = None
    # Когда выстрелит. Ноль — ещё не прицелился в этот ход.
    fire_at: float = 0.0
    # Клетки корабля, который сейчас добиваем, и куда стрелять дальше.
    wounded: list[Cell] = field(default_factory=list)
    targets: list[Cell] = field(default_factory=list)
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    @property
    def _aim(self) -> tuple[float, float]:
        return AIM.get(self.speed, AIM["normal"])

    @property
    def _smart(self) -> float:
        return SMART.get(self.speed, SMART["normal"])

    def step(self, match: SeaMatch, now: float) -> bool:
        """Один такт. True — робот только что выстрелил."""

        if match.state != STATE_RUNNING or not match.my_turn(ROBOT_ID):
            self.fire_at = 0.0
            return False

        human = match.opponent(ROBOT_ID)
        if not isinstance(human, SeaSide) or human.board is None:
            return False

        if not self.fire_at:
            self.fire_at = now + self._rng.uniform(*self._aim)
            return False
        if now < self.fire_at:
            return False

        target = self.choose(human.board)
        if target is None:
            return False
        shot = match.fire(ROBOT_ID, target[0], target[1], now)
        self.learn(shot, human.board)
        self.fire_at = 0.0
        return True

    # ── куда стрелять ───────────────────────────────────────────────

    def choose(self, board: sea.Board) -> Cell | None:
        known = board.shots
        if self._rng.random() < self._smart:
            while self.targets:
                spot = self.targets.pop(0)
                if spot not in known and sea.inside(*spot):
                    return spot

        free = [
            (r, c)
            for r in range(sea.SIZE)
            for c in range(sea.SIZE)
            if (r, c) not in known
        ]
        if not free:
            return None
        # Через клетку: любой корабль длиннее одной клетки заденет такую сетку,
        # и искать вслепую выходит вдвое быстрее.
        parity = [spot for spot in free if (spot[0] + spot[1]) % 2 == 0]
        return self._rng.choice(parity or free)

    def learn(self, shot: dict, board: sea.Board) -> None:
        """Запоминает, что показал выстрел, и решает, куда бить дальше."""

        result = shot.get("result")
        cell = shot.get("cell")
        if result == sea.SUNK:
            self.wounded.clear()
            self.targets.clear()
            return
        if result != sea.HIT or not isinstance(cell, tuple):
            return

        self.wounded.append(cell)
        row, col = cell
        if len(self.wounded) >= 2:
            # Направление ясно — продолжаем линию в обе стороны.
            rows = {r for r, _ in self.wounded}
            cols = {c for _, c in self.wounded}
            if len(rows) == 1:
                lo, hi = min(cols), max(cols)
                self.targets = [(row, lo - 1), (row, hi + 1)]
            else:
                lo, hi = min(rows), max(rows)
                self.targets = [(lo - 1, col), (hi + 1, col)]
        else:
            around = [(row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)]
            self._rng.shuffle(around)
            self.targets = around
        self.targets = [t for t in self.targets if sea.inside(*t) and t not in board.shots]

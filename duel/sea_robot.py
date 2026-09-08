"""Робот для морского боя.

Считает он так же, как робот в канате — тем же мозгом, с теми же паузами и
ошибками. А стреляет по-человечески: пока ничего не нашёл — ищет по полю,
попал — добивает вокруг, понял направление — идёт вдоль корабля.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import sea
from .robot import ROBOT_ID, Robot
from .sea_match import STATE_RUNNING, SeaMatch, SeaSide

# Между выстрелами робот «целится»: мгновенная очередь выглядит как автомат.
AIM = (0.5, 1.3)

Cell = tuple[int, int]


@dataclass
class SeaRobot:
    """Ходит за робота в морском бою: и примеры решает, и стреляет."""

    speed: str = "normal"
    seed: int | None = None
    brain: Robot = field(init=False)
    fire_at: float = 0.0
    # Клетки корабля, который сейчас добиваем, и куда стрелять дальше.
    wounded: list[Cell] = field(default_factory=list)
    targets: list[Cell] = field(default_factory=list)
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.brain = Robot(speed=self.speed, seed=self.seed)
        self._rng = random.Random(self.seed)

    def step(self, match: SeaMatch, now: float) -> bool:
        """Один такт: подумать над примером, при снаряде — выстрелить."""

        moved = self.brain.step(match, now)
        if match.state != STATE_RUNNING:
            return moved

        me = match.side(ROBOT_ID)
        human = match.opponent(ROBOT_ID)
        if not isinstance(me, SeaSide) or not isinstance(human, SeaSide):
            return moved
        if me.shells <= 0 or now < self.fire_at or human.board is None:
            return moved

        target = self.choose(human.board)
        if target is None:
            return moved
        shot = match.fire(ROBOT_ID, target[0], target[1], now)
        self.learn(shot, human.board)
        self.fire_at = now + self._rng.uniform(*AIM)
        return True

    # ── куда стрелять ───────────────────────────────────────────────

    def choose(self, board: sea.Board) -> Cell | None:
        known = board.shots
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

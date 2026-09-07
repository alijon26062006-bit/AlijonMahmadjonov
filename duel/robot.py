"""Соперник-робот. Играет, когда живых игроков рядом не нашлось.

Робот не должен быть безупречным: безупречный соперник — это не игра, а
стена. Поэтому он думает разное время, иногда ошибается и получает за это ту
же паузу, что и человек. Правила для него общие: он ходит через ту же
проверку ответов, что и все.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .game import Match

# Робот живёт под отрицательным номером: у настоящих людей в Telegram таких
# не бывает, поэтому он никогда не столкнётся с живым игроком в базе.
ROBOT_ID = -1

# Для каждой скорости: сколько секунд робот думает над примером в среднем и
# как часто ошибается.
SPEEDS = {
    "slow": (4.2, 0.15),
    "normal": (2.9, 0.09),
    "fast": (2.0, 0.05),
}

# Разброс времени: без него ответы идут как метроном и сразу видно машину.
SPREAD = (0.55, 1.7)
MIN_THINK = 0.9
MAX_THINK = 12.0
# После ошибки робот приходит в себя не мгновенно.
AFTER_MISS = 0.4


def speed_for(rating: int) -> str:
    """Соперник по силам: слабому — медленный робот, сильному — быстрый."""

    if rating < 1000:
        return "slow"
    if rating < 1250:
        return "normal"
    return "fast"


@dataclass
class Robot:
    """Ходит за сторону робота в обычном матче."""

    speed: str = "normal"
    seed: int | None = None
    next_at: float = 0.0
    _task_id: int = 0
    _rng: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    @property
    def _mean(self) -> float:
        return SPEEDS.get(self.speed, SPEEDS["normal"])[0]

    @property
    def _miss_rate(self) -> float:
        return SPEEDS.get(self.speed, SPEEDS["normal"])[1]

    def think(self, tier: int) -> float:
        """Сколько времени уйдёт на этот пример. Чем сложнее — тем дольше."""

        weight = 0.75 + 0.09 * max(1, tier)
        seconds = self._mean * weight * self._rng.uniform(*SPREAD)
        return max(MIN_THINK, min(MAX_THINK, seconds))

    def step(self, match: Match, now: float) -> bool:
        """Один такт жизни робота. True — он только что ответил."""

        side = match.side(ROBOT_ID)
        if side is None or side.task is None or match.state != "running":
            return False

        # Новый пример — прикидываем, сколько над ним думать.
        if side.task.id != self._task_id:
            self._task_id = side.task.id
            self.next_at = now + self.think(side.task.tier)
            return False

        if side.frozen(now):
            self.next_at = max(self.next_at, side.frozen_until + AFTER_MISS)
            return False

        if now < self.next_at:
            return False

        answer = side.task.answer
        if self._rng.random() < self._miss_rate:
            answer += self._rng.choice((1, 2, -1, -2, 10))
        match.submit(ROBOT_ID, side.task.id, answer, now)
        # Следующий ход запланируется сам, когда придёт новый пример.
        self.next_at = now + MIN_THINK
        return True

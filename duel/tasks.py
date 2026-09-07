"""Генератор примеров: сложение, вычитание, умножение, деление.

Примеры выдаёт сервер, ответ хранит у себя и клиенту не отправляет — иначе
ответ можно было бы подсмотреть в консоли браузера. Сложность растёт по ходу
матча: начинается с простого и к концу доходит до уровня, выбранного игроком.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

PLUS = "+"
MINUS = "−"
TIMES = "×"
DIVIDE = "÷"

LEVELS = ("easy", "normal", "hard", "auto")
MIN_TIER = 1
MAX_TIER = 10

# Стартовая ступень и потолок для каждого уровня. Между ними сложность
# поднимается на ступень каждые step_seconds секунд матча.
LEVEL_RAMP = {
    "easy": (1, 4, 30),
    "normal": (3, 7, 25),
    "hard": (6, 10, 20),
}

# Ступень по рейтингу — для режима «авто», когда игрок не выбирал уровень.
RATING_TIERS = ((900, 1), (1050, 2), (1150, 4), (1300, 5), (1450, 7), (1600, 8))


def tier_for(level: str, elapsed: float, rating: int = 1000) -> int:
    """Ступень сложности на данной секунде матча."""

    if level == "auto":
        base = MAX_TIER - 2
        for bound, tier in RATING_TIERS:
            if rating < bound:
                base = tier
                break
        top, step = MAX_TIER, 25
    else:
        base, top, step = LEVEL_RAMP.get(level, LEVEL_RAMP["normal"])

    grown = base + int(max(0.0, elapsed) // step)
    return max(MIN_TIER, min(top, grown))


@dataclass(frozen=True)
class Task:
    """Один пример. answer на клиент не уходит."""

    id: int
    text: str
    answer: int
    op: str
    tier: int

    def public(self) -> dict[str, object]:
        return {"id": self.id, "q": self.text, "tier": self.tier}


def _add(rng: random.Random, lo: int, hi: int) -> tuple[str, int, str]:
    a, b = rng.randint(lo, hi), rng.randint(lo, hi)
    return f"{a} {PLUS} {b}", a + b, PLUS


def _sub(rng: random.Random, lo: int, hi: int) -> tuple[str, int, str]:
    a, b = rng.randint(lo, hi), rng.randint(lo, hi)
    if b > a:
        a, b = b, a
    return f"{a} {MINUS} {b}", a - b, MINUS


def _mul(rng: random.Random, a_lo: int, a_hi: int, b_lo: int, b_hi: int) -> tuple[str, int, str]:
    a, b = rng.randint(a_lo, a_hi), rng.randint(b_lo, b_hi)
    return f"{a} {TIMES} {b}", a * b, TIMES


def _div(rng: random.Random, q_lo: int, q_hi: int, d_lo: int, d_hi: int) -> tuple[str, int, str]:
    # Делимое собираем из ответа и делителя, чтобы деление было нацело.
    answer = rng.randint(q_lo, q_hi)
    divisor = rng.randint(d_lo, d_hi)
    return f"{answer * divisor} {DIVIDE} {divisor}", answer, DIVIDE


# Для каждой ступени — набор примеров с весами. Вес показывает, как часто
# такой пример попадается: на младших ступенях больше сложения, на старших
# больше умножения и деления.
TIERS: dict[int, tuple[tuple[int, object], ...]] = {
    1: (
        (5, lambda r: _add(r, 1, 9)),
        (4, lambda r: _sub(r, 1, 9)),
        (1, lambda r: _mul(r, 1, 3, 1, 4)),
    ),
    2: (
        (4, lambda r: _add(r, 2, 19)),
        (4, lambda r: _sub(r, 2, 19)),
        (2, lambda r: _mul(r, 2, 4, 2, 5)),
    ),
    3: (
        (3, lambda r: _add(r, 5, 30)),
        (3, lambda r: _sub(r, 5, 30)),
        (3, lambda r: _mul(r, 2, 5, 2, 9)),
        (1, lambda r: _div(r, 2, 9, 2, 4)),
    ),
    4: (
        (2, lambda r: _add(r, 10, 60)),
        (2, lambda r: _sub(r, 10, 60)),
        (4, lambda r: _mul(r, 2, 9, 2, 10)),
        (2, lambda r: _div(r, 2, 10, 2, 9)),
    ),
    5: (
        (2, lambda r: _add(r, 15, 99)),
        (2, lambda r: _sub(r, 15, 99)),
        (4, lambda r: _mul(r, 3, 12, 3, 10)),
        (2, lambda r: _div(r, 3, 12, 3, 9)),
    ),
    6: (
        (2, lambda r: _add(r, 25, 199)),
        (2, lambda r: _sub(r, 25, 199)),
        (4, lambda r: _mul(r, 11, 20, 3, 9)),
        (2, lambda r: _div(r, 4, 20, 3, 9)),
    ),
    7: (
        (2, lambda r: _add(r, 50, 499)),
        (2, lambda r: _sub(r, 50, 499)),
        (4, lambda r: _mul(r, 12, 25, 4, 9)),
        (2, lambda r: _div(r, 6, 30, 4, 9)),
    ),
    8: (
        (2, lambda r: _add(r, 100, 899)),
        (2, lambda r: _sub(r, 100, 899)),
        (4, lambda r: _mul(r, 21, 49, 4, 9)),
        (2, lambda r: _div(r, 8, 45, 5, 9)),
    ),
    9: (
        (2, lambda r: _add(r, 150, 1500)),
        (2, lambda r: _sub(r, 150, 1500)),
        (3, lambda r: _mul(r, 11, 19, 11, 19)),
        (2, lambda r: _mul(r, 51, 99, 4, 9)),
        (2, lambda r: _div(r, 11, 60, 6, 12)),
    ),
    10: (
        (2, lambda r: _add(r, 500, 4999)),
        (2, lambda r: _sub(r, 500, 4999)),
        (4, lambda r: _mul(r, 12, 39, 11, 29)),
        (3, lambda r: _div(r, 12, 90, 11, 25)),
    ),
}


class TaskGenerator:
    """Выдаёт примеры подряд, не повторяя предыдущий."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._next_id = 1
        self._last_text = ""

    def next(self, tier: int) -> Task:
        tier = max(MIN_TIER, min(MAX_TIER, tier))
        recipes = TIERS[tier]
        total = sum(weight for weight, _ in recipes)

        # Дважды подряд один и тот же пример выглядит как зависший экран.
        for _ in range(12):
            roll = self._rng.randint(1, total)
            for weight, make in recipes:
                roll -= weight
                if roll <= 0:
                    text, answer, op = make(self._rng)
                    break
            if text != self._last_text:
                break

        self._last_text = text
        task = Task(id=self._next_id, text=text, answer=answer, op=op, tier=tier)
        self._next_id += 1
        return task

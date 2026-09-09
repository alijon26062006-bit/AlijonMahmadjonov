"""Ходы по очереди — общее для всех пошаговых игр.

Морской бой, пять в ряд и всё, что будет дальше, отличаются только тем, что
происходит в свой ход. А сама очередь у них одна: чей сейчас ход, сколько
осталось времени, что делать с тем, кто задумался навсегда.

Правило, которое стоит помнить: удачный ход может ход и не отдавать —
в морском бою попадание оставляет очередь за стрелявшим. Поэтому переход
хода здесь не автоматический, его вызывает сама игра.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .game import STATE_RUNNING, Match, Side

# Сколько думает над ходом один игрок. Не сходил — ход уходит.
TURN_SEC = 30.0
# Три пропуска подряд — человек просто ушёл, засчитываем поражение.
MAX_SKIPS = 3
REASON_IDLE = "idle"


def ms(seconds: float) -> int:
    """Миллисекунды с точностью до полусекунды.

    Точное время слать незачем: часы клиент дальше отсчитывает сам, а от
    точности до миллисекунды состояние менялось бы каждый такт и летело
    бы по сети двадцать раз в секунду.
    """

    return max(0, int(seconds * 1000) // 500 * 500)


@dataclass
class TurnSide(Side):
    """Сторона пошаговой игры: считаем ещё и продуманные до конца ходы."""

    skips: int = 0


@dataclass
class TurnMatch(Match):
    """Очередь хода: кто ходит, до какого времени и что если не сходил."""

    turn: int = 0
    turn_deadline: float = 0.0
    _rng: random.Random = field(init=False, repr=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        self._rng = random.Random(self.seed)

    def start_turns(self, now: float) -> None:
        """Кто ходит первым — решает жребий: иначе первый ход всегда
        доставался бы тому, кто раньше нажал «Готов»."""

        self.turn = self._rng.choice([self.a.user_id, self.b.user_id])
        self.turn_deadline = now + TURN_SEC

    def my_turn(self, user_id: int) -> bool:
        return self.state == STATE_RUNNING and self.turn == user_id

    def turn_ms(self, now: float) -> int:
        return ms(self.turn_deadline - now) if self.state == STATE_RUNNING else 0

    def hold_turn(self, now: float) -> None:
        """Ход остаётся за тем же игроком, но время отсчитывается заново."""

        self.turn_deadline = now + TURN_SEC

    def pass_turn(self, now: float) -> None:
        other = self.opponent(self.turn)
        if other is not None:
            self.turn = other.user_id
        self.turn_deadline = now + TURN_SEC

    def skip_turn(self, now: float) -> bool:
        """Время хода вышло. True — на этом матч и закончился."""

        side = self.side(self.turn)
        if isinstance(side, TurnSide):
            side.skips += 1
            if side.skips >= MAX_SKIPS:
                other = self.opponent(self.turn)
                self.finish(
                    now, REASON_IDLE, winner_id=other.user_id if other else None
                )
                return True
        self.pass_turn(now)
        return False

    def moved(self) -> None:
        """Игрок сходил — счётчик пропусков обнуляется."""

        side = self.side(self.turn)
        if isinstance(side, TurnSide):
            side.skips = 0

"""Матч «Пять в ряд»: ходят по очереди, пять своих подряд — победа.

Расставлять тут нечего и решать примеры не нужно, поэтому матч начинается
сразу с отсчёта. Кто ходит первым — решает жребий, ему достаются крестики.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import five
from .game import (
    DISCONNECT_GRACE,
    REASON_ABANDONED,
    REASON_LEFT,
    REASON_TIME,
    STATE_COUNTDOWN,
    STATE_FINISHED,
    STATE_RUNNING,
)
from .turns import MAX_SKIPS, REASON_IDLE, TURN_SEC, TurnMatch, TurnSide

REASON_LINE = "line"      # выстроил пять подряд
REASON_FULL = "full"      # поле кончилось, никто не выстроил

# Партия на девять на девять идёт минуты три. Потолок — на случай, если
# двое решили ходить в последнюю секунду каждый ход.
GAME_CAP_SEC = 15 * 60

__all__ = ["FiveMatch", "FiveSide", "REASON_LINE", "REASON_FULL",
           "TURN_SEC", "MAX_SKIPS", "REASON_IDLE"]


@dataclass
class FiveSide(TurnSide):
    """Сторона: свой знак и сколько ходов сделал."""

    mark: str = ""

    @property
    def moves(self) -> int:
        return self.score


@dataclass
class FiveMatch(TurnMatch):
    """Правила партии. Всё поле лежит здесь, у клиента только его копия."""

    game: str = field(default="five", init=False)
    board: five.Board = field(default_factory=dict)
    last: tuple[int, int] | None = None
    win_line: list[tuple[int, int]] = field(default_factory=list)

    # ── ход времени ─────────────────────────────────────────────────

    def activate(self, now: float) -> None:
        """Партия пошла. Примеров нет, поэтому раздавать нечего — только
        решить, кто первый, и раздать знаки: первому крестики."""

        self.state = STATE_RUNNING
        self.starts_at = now
        self.deadline = now + (self.duration if self.duration > 0 else GAME_CAP_SEC)
        self.start_turns(now)
        first = self.side(self.turn)
        second = self.opponent(self.turn)
        if isinstance(first, FiveSide) and isinstance(second, FiveSide):
            first.mark, second.mark = five.X, five.O

    def poll(self, now: float) -> bool:
        if self.state == STATE_FINISHED:
            return False

        gone = [s for s in (self.a, self.b) if not s.connected and s.left_at is not None]
        if len(gone) == 2:
            self.finish(now, REASON_ABANDONED)
            return True
        for side in gone:
            if now - side.left_at >= DISCONNECT_GRACE:
                other = self.a if side is self.b else self.b
                self.finish(now, REASON_LEFT, winner_id=other.user_id)
                return True

        if self.state == STATE_COUNTDOWN:
            if now >= self.starts_at:
                self.activate(now)
                return True
            return False

        if now >= self.deadline:
            self.finish(now, REASON_TIME)
            return True
        if now >= self.turn_deadline:
            self.skip_turn(now)
            return True
        return False

    # ── ходы ────────────────────────────────────────────────────────

    def play(self, user_id: int, row: int, col: int, now: float) -> dict[str, object]:
        """Поставить свой знак. Проверяет всё сервер, клиенту не верим."""

        side = self.side(user_id)
        if self.state != STATE_RUNNING or not isinstance(side, FiveSide):
            return {"result": "not_running"}
        if self.turn != user_id:
            return {"result": "not_your_turn"}
        if not five.free(self.board, row, col):
            return {"result": "busy"}

        self.board[(row, col)] = side.mark
        self.last = (row, col)
        side.score += 1
        self.moved()

        line = five.winning_line(self.board, row, col)
        if line:
            self.win_line = line
            self.finish(now, REASON_LINE, winner_id=user_id)
        elif five.full(self.board):
            self.finish(now, REASON_FULL)
        else:
            self.pass_turn(now)

        return {
            "result": "ok",
            "cell": [row, col],
            "mark": side.mark,
            "win": [list(spot) for spot in line],
        }

    # ── итог ────────────────────────────────────────────────────────

    def finish(self, now: float, reason: str, winner_id: int | None = None) -> None:
        if self.state == STATE_FINISHED:
            return
        if winner_id is None and reason in (REASON_TIME,):
            # Время вышло: побеждает тот, у кого линия длиннее; поровну — ничья.
            a, b = self.a, self.b
            if isinstance(a, FiveSide) and isinstance(b, FiveSide):
                mine, theirs = self.best_line(a), self.best_line(b)
                if mine != theirs:
                    winner_id = (a if mine > theirs else b).user_id
        self.state = STATE_FINISHED
        self.finished_at = now
        self.reason = reason
        self.winner_id = winner_id

    def best_line(self, side: FiveSide) -> int:
        return five.longest(self.board, side.mark) if side.mark else 0

    @property
    def rated(self) -> bool:
        if self.has_bot or self.state != STATE_FINISHED:
            return False
        if self.reason == REASON_ABANDONED:
            return False
        if self.reason in (REASON_LEFT, REASON_IDLE):
            # Ушёл, не сделав ни хода, — не партия, а недоразумение.
            return self.a.score + self.b.score > 0
        return True

    def margin(self) -> int:
        return self.a.score - self.b.score

    # ── что видит клиент ────────────────────────────────────────────

    def cells(self) -> list[list]:
        return [[row, col, mark] for (row, col), mark in sorted(self.board.items())]

    def snapshot(self, user_id: int, now: float) -> dict[str, object]:
        me = self.side(user_id)
        opp = self.opponent(user_id)
        if not isinstance(me, FiveSide) or not isinstance(opp, FiveSide):
            return {}
        running = self.state == STATE_RUNNING
        return {
            "game": self.game,
            "state": self.state,
            "left_ms": self.left_ms(now) if running else None,
            "starts_in_ms": max(0, int((self.starts_at - now) * 1000))
            if self.state == STATE_COUNTDOWN
            else 0,
            "my_turn": running and self.turn == user_id,
            "turn_ms": self.turn_ms(now),
            "mark": me.mark,
            "cells": self.cells(),
            "last": list(self.last) if self.last else None,
            "win": [list(spot) for spot in self.win_line],
            "me": {"moves": me.moves, "mark": me.mark},
            "opp": {"moves": opp.moves, "mark": opp.mark, "connected": opp.connected},
        }

    def result_for(self, user_id: int) -> dict[str, object]:
        me = self.side(user_id)
        opp = self.opponent(user_id)
        if not isinstance(me, FiveSide) or not isinstance(opp, FiveSide):
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
            "score": me.moves,
            "opp_score": opp.moves,
            "moves": me.moves,
            "opp_moves": opp.moves,
            "line": self.best_line(me),
            "opp_line": self.best_line(opp),
            "mark": me.mark,
            "cells": self.cells(),
            "win": [list(spot) for spot in self.win_line],
            "opp_name": opp.name,
            "duration": self.duration,
        }

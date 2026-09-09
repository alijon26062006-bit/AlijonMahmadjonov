"""Матч в крестики-нолики: три партии подряд, кто взял две — тот и выиграл.

Одна партия три на три почти всегда кончается ничьёй: поле маленькое,
проиграть в нём трудно. Поэтому матч идёт из трёх партий, и первый ход
каждый раз переходит к другому — иначе преимущество первого хода решало бы
всё. Кто взял две партии, тот и победил.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import tic
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

# Партий в матче и сколько нужно взять для победы.
ROUNDS = 3
TO_WIN = ROUNDS // 2 + 1
# Пауза между партиями: увидеть, чем кончилась предыдущая.
ROUND_PAUSE = 2.5

REASON_ROUNDS = "rounds"    # взял больше партий
REASON_FULL = "full"        # все партии вничью

# Матч не бесконечен: три партии по девять клеток укладываются в пару минут.
GAME_CAP_SEC = 10 * 60

__all__ = ["TicMatch", "TicSide", "ROUNDS", "TO_WIN", "ROUND_PAUSE",
           "REASON_ROUNDS", "REASON_FULL", "TURN_SEC", "MAX_SKIPS", "REASON_IDLE"]


@dataclass
class TicSide(TurnSide):
    """Сторона матча: знак в текущей партии и сколько партий взял.

    Счётом матча считаются взятые партии — так рейтинг, история и итог
    считаются тем же кодом, что и в остальных играх.
    """

    mark: str = ""
    moves: int = 0

    @property
    def rounds_won(self) -> int:
        return self.score


@dataclass
class TicMatch(TurnMatch):
    """Правила матча. Всё поле лежит здесь, у клиента только его копия."""

    game: str = field(default="tic", init=False)
    board: tic.Board = field(default_factory=dict)
    last: tuple[int, int] | None = None
    win_line: list[tuple[int, int]] = field(default_factory=list)
    # Какая партия идёт, кто в ней начинал и чем кончилась предыдущая.
    round_no: int = 1
    round_first: int = 0
    round_winner: int | None = None
    round_over_at: float = 0.0

    # ── ход времени ─────────────────────────────────────────────────

    def activate(self, now: float) -> None:
        """Матч пошёл. Кто начинает первую партию — решает жребий."""

        self.state = STATE_RUNNING
        self.starts_at = now
        self.deadline = now + (self.duration if self.duration > 0 else GAME_CAP_SEC)
        self.start_turns(now)
        self.start_round(now, self.turn)

    def start_round(self, now: float, first: int) -> None:
        """Новая партия: чистое поле, знаки заново, ходит названный."""

        self.board = {}
        self.last = None
        self.win_line = []
        self.round_winner = None
        self.round_over_at = 0.0
        self.turn = first
        self.round_first = first
        self.turn_deadline = now + TURN_SEC
        me, other = self.side(first), self.opponent(first)
        if isinstance(me, TicSide) and isinstance(other, TicSide):
            me.mark, other.mark = tic.X, tic.O

    @property
    def between_rounds(self) -> bool:
        return self.round_over_at > 0.0

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

        if self.between_rounds:
            if now >= self.round_over_at:
                # Первый ход переходит к другому: иначе он решал бы весь матч.
                self.round_no += 1
                other = self.opponent(self.round_first)
                self.start_round(now, other.user_id if other else self.round_first)
                return True
            return False

        if now >= self.turn_deadline:
            self.skip_turn(now)
            return True
        return False

    # ── ходы ────────────────────────────────────────────────────────

    def play(self, user_id: int, row: int, col: int, now: float) -> dict[str, object]:
        """Поставить свой знак. Проверяет всё сервер, клиенту не верим."""

        side = self.side(user_id)
        if self.state != STATE_RUNNING or not isinstance(side, TicSide):
            return {"result": "not_running"}
        if self.between_rounds:
            return {"result": "between_rounds"}
        if self.turn != user_id:
            return {"result": "not_your_turn"}
        if not tic.free(self.board, row, col):
            return {"result": "busy"}

        self.board[(row, col)] = side.mark
        self.last = (row, col)
        side.moves += 1
        self.moved()

        line = tic.winning_line(self.board, row, col)
        if line:
            self.win_line = line
            side.score += 1
            self.end_round(now, user_id)
        elif tic.full(self.board):
            self.end_round(now, None)
        else:
            self.pass_turn(now)

        return {
            "result": "ok",
            "cell": [row, col],
            "mark": side.mark,
            "win": [list(spot) for spot in line],
            "round_over": self.between_rounds or self.state == STATE_FINISHED,
        }

    def end_round(self, now: float, winner_id: int | None) -> None:
        """Партия кончилась: считаем, надо ли играть следующую."""

        self.round_winner = winner_id
        a, b = self.a, self.b
        if max(a.score, b.score) >= TO_WIN:
            self.finish(now, REASON_ROUNDS, winner_id=winner_id)
            return
        if self.round_no >= ROUNDS:
            if a.score != b.score:
                self.finish(now, REASON_ROUNDS,
                            winner_id=(a if a.score > b.score else b).user_id)
            else:
                self.finish(now, REASON_FULL)
            return
        # Ещё не всё: даём посмотреть на доигранное поле и начинаем следующую.
        self.round_over_at = now + ROUND_PAUSE
        self.turn_deadline = self.round_over_at + TURN_SEC

    # ── итог ────────────────────────────────────────────────────────

    def finish(self, now: float, reason: str, winner_id: int | None = None) -> None:
        if self.state == STATE_FINISHED:
            return
        if winner_id is None and reason == REASON_TIME:
            a, b = self.a, self.b
            if a.score != b.score:
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
        a, b = self.a, self.b
        if self.reason in (REASON_LEFT, REASON_IDLE):
            # Ушёл, не сделав ни хода, — не матч, а недоразумение.
            return isinstance(a, TicSide) and isinstance(b, TicSide) \
                and (a.moves + b.moves) > 0
        return True

    def margin(self) -> int:
        return self.a.score - self.b.score

    # ── что видит клиент ────────────────────────────────────────────

    def cells(self) -> list[list]:
        return [[row, col, mark] for (row, col), mark in sorted(self.board.items())]

    def round_end_for(self, user_id: int) -> str:
        """Чем кончилась партия глазами игрока: пусто — она ещё идёт."""

        if not self.between_rounds and self.state != STATE_FINISHED:
            return ""
        if self.round_winner is None:
            return "draw"
        return "win" if self.round_winner == user_id else "loss"

    def snapshot(self, user_id: int, now: float) -> dict[str, object]:
        me = self.side(user_id)
        opp = self.opponent(user_id)
        if not isinstance(me, TicSide) or not isinstance(opp, TicSide):
            return {}
        running = self.state == STATE_RUNNING
        return {
            "game": self.game,
            "state": self.state,
            "left_ms": self.left_ms(now) if running else None,
            "starts_in_ms": max(0, int((self.starts_at - now) * 1000))
            if self.state == STATE_COUNTDOWN
            else 0,
            "my_turn": running and not self.between_rounds and self.turn == user_id,
            "turn_ms": 0 if self.between_rounds else self.turn_ms(now),
            "mark": me.mark,
            "cells": self.cells(),
            "last": list(self.last) if self.last else None,
            "win": [list(spot) for spot in self.win_line],
            "round": self.round_no,
            "rounds": ROUNDS,
            "round_end": self.round_end_for(user_id),
            "pause_ms": max(0, int((self.round_over_at - now) * 1000))
            if self.between_rounds
            else 0,
            "me": {"score": me.rounds_won, "moves": me.moves, "mark": me.mark},
            "opp": {
                "score": opp.rounds_won,
                "moves": opp.moves,
                "mark": opp.mark,
                "connected": opp.connected,
            },
        }

    def result_for(self, user_id: int) -> dict[str, object]:
        me = self.side(user_id)
        opp = self.opponent(user_id)
        if not isinstance(me, TicSide) or not isinstance(opp, TicSide):
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
            "score": me.rounds_won,
            "opp_score": opp.rounds_won,
            "rounds": self.round_no,
            "moves": me.moves,
            "opp_moves": opp.moves,
            "mark": me.mark,
            "cells": self.cells(),
            "win": [list(spot) for spot in self.win_line],
            "opp_name": opp.name,
            "duration": self.duration,
        }

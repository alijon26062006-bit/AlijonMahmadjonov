"""Матч: канат, счёт, примеры, время.

Здесь нет ни сети, ни базы — только правила игры. Поэтому логику можно
проверить тестами, не поднимая сервер. Время всегда передаётся снаружи
(now), чтобы в тестах его можно было перематывать.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from .tasks import Task, TaskGenerator, tier_for

# Сколько шагов до края каната. Дотянул — досрочная победа.
WIN_STEPS = 10
# Пауза после ошибки: клавиатура не принимает ввод.
FREEZE_SEC = 1.5
# С какой серии подряд верных ответов рывок считается двойным.
STREAK_BONUS_AT = 3
BONUS_STEP = 2
# Отсчёт «3, 2, 1» перед стартом, чтобы оба успели посмотреть на экран.
COUNTDOWN_SEC = 3.0
# Сколько ждём вернувшегося игрока, прежде чем засчитать техническое поражение.
DISCONNECT_GRACE = 15.0
# Даже бесконечный матч когда-то обязан кончиться.
ENDLESS_CAP_SEC = 15 * 60
# Быстрее этого человек ответить не может — значит, отвечает не человек.
MIN_SOLVE_SEC = 0.15
SUSPICIOUS_LIMIT = 6
# Один и тот же пример держим не больше двух ошибок, иначе игрок застрянет.
WRONG_BEFORE_RESHUFFLE = 2

DURATIONS = (30, 60, 120, 300, 0)  # 0 — до победы, без таймера
STATE_COUNTDOWN = "countdown"
STATE_RUNNING = "running"
STATE_FINISHED = "finished"

# Почему матч кончился.
REASON_ROPE = "rope"          # канат дотянут до края
REASON_TIME = "time"          # вышло время
REASON_LEFT = "left"          # соперник ушёл и не вернулся
REASON_ABANDONED = "abandoned"  # ушли оба
REASON_CHEAT = "cheat"        # ответы быстрее человеческих

_match_ids = itertools.count(1)


@dataclass
class Side:
    """Одна сторона каната."""

    user_id: int
    name: str
    rating: int = 1000
    games: int = 0
    lang: str = "ru"
    photo_url: str = ""

    score: int = 0
    wrong: int = 0
    pull: int = 0
    streak: int = 0
    best_streak: int = 0

    task: Task | None = None
    task_at: float = 0.0
    task_wrongs: int = 0
    frozen_until: float = 0.0

    connected: bool = True
    left_at: float | None = None
    is_bot: bool = False

    solve_ms_total: int = 0
    fastest_ms: int = 0
    suspicious: int = 0

    def frozen(self, now: float) -> bool:
        return now < self.frozen_until

    def freeze_ms(self, now: float) -> int:
        return max(0, int((self.frozen_until - now) * 1000))

    @property
    def avg_ms(self) -> int:
        return int(self.solve_ms_total / self.score) if self.score else 0

    @property
    def accuracy(self) -> int:
        total = self.score + self.wrong
        return round(100 * self.score / total) if total else 0


@dataclass
class AnswerResult:
    """Что сервер отвечает на присланный ответ."""

    accepted: bool
    correct: bool = False
    step: int = 0
    task: Task | None = None
    freeze_ms: int = 0
    note: str = ""


@dataclass
class Match:
    """Матч двух игроков. Всё состояние — здесь."""

    a: Side
    b: Side
    duration: int = 60
    level: str = "auto"
    private: bool = False
    seed: int | None = None
    id: int = field(default_factory=lambda: next(_match_ids))

    state: str = STATE_COUNTDOWN
    created_at: float = 0.0
    starts_at: float = 0.0
    deadline: float = 0.0
    finished_at: float = 0.0
    winner_id: int | None = None
    reason: str = ""
    _gen: TaskGenerator = field(init=False)

    def __post_init__(self) -> None:
        self._gen = TaskGenerator(self.seed)

    # ── жизненный цикл ──────────────────────────────────────────────

    def begin(self, now: float, countdown: float | None = None) -> None:
        """Запускает отсчёт перед стартом."""

        self.created_at = now
        self.starts_at = now + (COUNTDOWN_SEC if countdown is None else countdown)
        self.state = STATE_COUNTDOWN

    def activate(self, now: float) -> None:
        """Матч пошёл: раздаём первые примеры и заводим таймер."""

        self.state = STATE_RUNNING
        self.starts_at = now
        cap = self.duration if self.duration > 0 else ENDLESS_CAP_SEC
        self.deadline = now + cap
        for side in (self.a, self.b):
            self._issue(side, now)

    def elapsed(self, now: float) -> float:
        if self.state == STATE_COUNTDOWN:
            return 0.0
        return max(0.0, now - self.starts_at)

    def left_ms(self, now: float) -> int | None:
        """Сколько миллисекунд осталось. None — матч без таймера."""

        if self.duration <= 0:
            return None
        return max(0, int((self.deadline - now) * 1000))

    def rope(self) -> int:
        """Положение каната. Больше нуля — тянет сторона A."""

        return self.a.pull - self.b.pull

    def side(self, user_id: int) -> Side | None:
        if self.a.user_id == user_id:
            return self.a
        if self.b.user_id == user_id:
            return self.b
        return None

    def opponent(self, user_id: int) -> Side | None:
        if self.a.user_id == user_id:
            return self.b
        if self.b.user_id == user_id:
            return self.a
        return None

    # ── примеры и ответы ────────────────────────────────────────────

    def _issue(self, side: Side, now: float) -> Task:
        rating = side.rating
        task = self._gen.next(tier_for(self.level, self.elapsed(now), rating))
        side.task = task
        side.task_at = now
        side.task_wrongs = 0
        return task

    def submit(
        self,
        user_id: int,
        task_id: int,
        value: int,
        now: float,
        solve_ms: int | None = None,
    ) -> AnswerResult:
        """Принимает ответ. Правильность решает только сервер."""

        if self.state != STATE_RUNNING:
            return AnswerResult(accepted=False, note="not_running")

        side = self.side(user_id)
        if side is None or side.task is None:
            return AnswerResult(accepted=False, note="not_playing")

        if side.frozen(now):
            return AnswerResult(accepted=False, freeze_ms=side.freeze_ms(now), note="frozen")

        # Ответ на уже сменившийся пример — эхо старого нажатия, молча гасим.
        if task_id != side.task.id:
            return AnswerResult(accepted=False, note="stale")

        # Сервер сам замеряет, сколько прошло с выдачи примера. Это время
        # включает дорогу по сети, то есть оно заведомо не меньше настоящего:
        # если и оно меньше человеческого, отвечает скрипт.
        server_ms = int((now - side.task_at) * 1000)
        if now - side.task_at < MIN_SOLVE_SEC:
            side.suspicious += 1
            if side.suspicious >= SUSPICIOUS_LIMIT:
                other = self.opponent(user_id)
                self.finish(now, REASON_CHEAT, winner_id=other.user_id if other else None)
                return AnswerResult(accepted=False, note="cheat")
            return AnswerResult(accepted=False, note="too_fast")

        if value == side.task.answer:
            side.score += 1
            side.streak += 1
            side.best_streak = max(side.best_streak, side.streak)
            measured = solve_ms if solve_ms and 0 < solve_ms <= server_ms else server_ms
            side.solve_ms_total += measured
            side.fastest_ms = measured if not side.fastest_ms else min(side.fastest_ms, measured)

            step = BONUS_STEP if side.streak >= STREAK_BONUS_AT else 1
            side.pull += step

            if abs(self.rope()) >= WIN_STEPS:
                self.finish(now, REASON_ROPE, winner_id=side.user_id)
                return AnswerResult(accepted=True, correct=True, step=step)

            task = self._issue(side, now)
            return AnswerResult(accepted=True, correct=True, step=step, task=task)

        side.wrong += 1
        side.streak = 0
        side.task_wrongs += 1
        side.frozen_until = now + FREEZE_SEC
        # Два промаха по одному примеру — меняем его, чтобы не было тупика.
        task = self._issue(side, now) if side.task_wrongs >= WRONG_BEFORE_RESHUFFLE else None
        return AnswerResult(
            accepted=True, correct=False, task=task, freeze_ms=int(FREEZE_SEC * 1000)
        )

    # ── связь ───────────────────────────────────────────────────────

    def disconnect(self, user_id: int, now: float) -> None:
        side = self.side(user_id)
        if side is not None:
            side.connected = False
            side.left_at = now

    def reconnect(self, user_id: int, now: float) -> None:
        side = self.side(user_id)
        if side is not None:
            side.connected = True
            side.left_at = None

    # ── ход времени ─────────────────────────────────────────────────

    def poll(self, now: float) -> bool:
        """Двигает матч во времени. True — состояние изменилось."""

        if self.state == STATE_FINISHED:
            return False

        if self.state == STATE_COUNTDOWN:
            if now >= self.starts_at:
                self.activate(now)
                return True
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

        if now >= self.deadline:
            self.finish(now, REASON_TIME)
            return True
        return False

    def finish(self, now: float, reason: str, winner_id: int | None = None) -> None:
        if self.state == STATE_FINISHED:
            return
        self.state = STATE_FINISHED
        self.finished_at = now
        self.reason = reason

        if winner_id is not None:
            self.winner_id = winner_id
        elif reason == REASON_ABANDONED:
            self.winner_id = None
        else:
            # Время вышло: побеждает тот, на чьей стороне канат. Канат ровно
            # посередине — смотрим, кто дал больше верных ответов.
            rope = self.rope()
            if rope > 0:
                self.winner_id = self.a.user_id
            elif rope < 0:
                self.winner_id = self.b.user_id
            elif self.a.score != self.b.score:
                self.winner_id = (self.a if self.a.score > self.b.score else self.b).user_id
            else:
                self.winner_id = None

    @property
    def has_bot(self) -> bool:
        return self.a.is_bot or self.b.is_bot

    @property
    def rated(self) -> bool:
        """Идёт ли матч в рейтинг. Тренировка с роботом и брошенный — нет."""

        if self.has_bot:
            return False
        if self.state != STATE_FINISHED or self.reason == REASON_ABANDONED:
            return False
        return (self.a.score + self.b.score) > 0 or self.reason in {REASON_LEFT, REASON_CHEAT}

    def winner_key(self) -> str:
        if self.winner_id is None:
            return "draw"
        return "a" if self.winner_id == self.a.user_id else "b"

    # ── что видит клиент ────────────────────────────────────────────

    def snapshot(self, user_id: int, now: float) -> dict[str, object]:
        """Состояние глазами конкретного игрока: канат всегда «мой вправо»."""

        me = self.side(user_id)
        opp = self.opponent(user_id)
        if me is None or opp is None:
            return {}
        rope = self.rope() if me is self.a else -self.rope()
        return {
            "state": self.state,
            "rope": rope,
            "win_steps": WIN_STEPS,
            "left_ms": self.left_ms(now),
            "starts_in_ms": max(0, int((self.starts_at - now) * 1000))
            if self.state == STATE_COUNTDOWN
            else 0,
            "me": {
                "score": me.score,
                "streak": me.streak,
                "wrong": me.wrong,
                "freeze_ms": me.freeze_ms(now),
            },
            "opp": {
                "score": opp.score,
                "streak": opp.streak,
                "connected": opp.connected,
            },
        }

    def result_for(self, user_id: int) -> dict[str, object]:
        """Итог матча глазами игрока — без рейтинга, его считает сервер."""

        me = self.side(user_id)
        opp = self.opponent(user_id)
        if me is None or opp is None:
            return {}
        if self.winner_id is None:
            outcome = "draw"
        elif self.winner_id == user_id:
            outcome = "win"
        else:
            outcome = "loss"
        return {
            "outcome": outcome,
            "reason": self.reason,
            "rope": self.rope() if me is self.a else -self.rope(),
            "score": me.score,
            "opp_score": opp.score,
            "wrong": me.wrong,
            "best_streak": me.best_streak,
            "accuracy": me.accuracy,
            "avg_ms": me.avg_ms,
            "fastest_ms": me.fastest_ms,
            "opp_name": opp.name,
            "duration": self.duration,
        }

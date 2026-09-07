"""Соперник-робот: играет по правилам, но не безупречно."""

import pytest

from duel import robot as robot_mod
from duel.game import FREEZE_SEC, STATE_FINISHED, WIN_STEPS, Match, Side
from duel.robot import ROBOT_ID, Robot, speed_for


def duel(speed="normal", seed=1, duration=0):
    """Матч человека против робота. Человек молчит, если его не заставить."""
    match = Match(
        a=Side(user_id=1, name="Человек"),
        b=Side(user_id=ROBOT_ID, name="Робот", is_bot=True),
        duration=duration,
        level="normal",
        seed=seed,
    )
    match.begin(0.0, countdown=0.0)
    match.activate(0.0)
    return match, Robot(speed=speed, seed=seed)


def run(match, robot, until, step=0.1):
    """Прокручивает матч по тактам, как это делает сервер."""
    now = 0.0
    while now < until and match.state != STATE_FINISHED:
        now += step
        match.poll(now)
        robot.step(match, now)
    return now


# ── как он думает ───────────────────────────────────────────────────────────


def test_thinking_takes_human_time():
    robot = Robot(speed="normal", seed=3)
    times = [robot.think(4) for _ in range(200)]
    assert all(robot_mod.MIN_THINK <= x <= robot_mod.MAX_THINK for x in times)
    assert 1.5 < sum(times) / len(times) < 6.0


def test_harder_examples_take_longer():
    robot = Robot(speed="normal", seed=4)
    easy = sum(robot.think(1) for _ in range(300))
    hard = sum(robot.think(9) for _ in range(300))
    assert hard > easy


def test_answers_are_not_metronome():
    """Ровные промежутки сразу выдают машину."""
    robot = Robot(speed="fast", seed=5)
    times = {round(robot.think(4), 2) for _ in range(50)}
    assert len(times) > 40


def test_opponent_is_matched_to_your_strength():
    assert speed_for(800) == "slow"
    assert speed_for(1100) == "normal"
    assert speed_for(1500) == "fast"


# ── как он играет ───────────────────────────────────────────────────────────


def test_robot_never_answers_instantly():
    """Мгновенный ответ сервер считает признаком скрипта — робот не должен
    попадать под собственную защиту от роботов."""
    match, robot = duel()
    assert not robot.step(match, 0.0)
    assert not robot.step(match, 0.05)
    assert match.b.score == 0


def test_robot_scores_over_time():
    match, robot = duel(duration=0)
    run(match, robot, until=40)
    assert match.b.score > 0


def test_robot_can_win_a_match_on_its_own():
    match, robot = duel(duration=0)
    run(match, robot, until=300)
    assert match.state == STATE_FINISHED
    assert match.winner_id == ROBOT_ID
    assert abs(match.rope()) >= WIN_STEPS


def test_robot_sometimes_misses():
    misses = 0
    for seed in range(12):
        match, robot = duel(speed="slow", seed=seed, duration=0)
        run(match, robot, until=200)
        misses += match.b.wrong
    assert misses > 0, "безошибочный соперник — это стена, а не игра"


def time_to_win(speed, seeds=10):
    """Среднее время, за которое робот дотягивает канат до края."""
    total = 0.0
    for seed in range(seeds):
        match, robot = duel(speed=speed, seed=seed, duration=0)
        total += run(match, robot, until=600)
    return total / seeds


def test_a_faster_robot_wins_sooner():
    """Считать набранные очки бессмысленно: быстрый побеждает раньше и просто
    не успевает ответить столько же раз."""
    assert time_to_win("fast") < time_to_win("normal") < time_to_win("slow")


def test_the_error_rate_is_what_we_asked_for():
    """Соперник должен ошибаться примерно настолько, насколько задумано."""
    for speed, expected in (("slow", 0.15), ("fast", 0.05)):
        correct = wrong = 0
        for seed in range(20):
            match, robot = duel(speed=speed, seed=seed, duration=0)
            run(match, robot, until=200)
            correct += match.b.score
            wrong += match.b.wrong
        share = wrong / (correct + wrong)
        assert abs(share - expected) < 0.06, f"{speed}: ошибается {share:.0%}"


def test_robot_serves_its_penalty_like_everyone():
    match, robot = duel()
    match.b.frozen_until = 5.0
    before = match.b.score
    run(match, robot, until=4.5)
    assert match.b.score == before
    run(match, robot, until=5.0 + FREEZE_SEC + 8)
    assert match.b.score > before


def test_human_can_outrun_the_robot():
    """Робот должен быть обыгрываемым: человек, отвечающий за секунду, ведёт."""
    match, robot = duel(speed="normal", seed=11, duration=0)
    now = 0.0
    while now < 20 and match.state != STATE_FINISHED:
        now += 1.0
        match.poll(now)
        robot.step(match, now)
        side = match.side(1)
        if side.task and not side.frozen(now):
            match.submit(1, side.task.id, side.task.answer, now)
    assert match.a.score > match.b.score


# ── тренировка не идёт в зачёт ──────────────────────────────────────────────


def test_a_match_with_the_robot_is_never_rated():
    match, robot = duel(duration=0)
    run(match, robot, until=300)
    assert match.has_bot
    assert not match.rated, "иначе рейтинг можно нарисовать себе роботом"


def test_a_match_between_people_is_still_rated():
    match = Match(a=Side(user_id=1, name="A"), b=Side(user_id=2, name="B"), duration=5)
    match.begin(0.0, countdown=0.0)
    match.activate(0.0)
    match.submit(1, match.a.task.id, match.a.task.answer, 1.0)
    match.poll(6.0)
    assert match.rated

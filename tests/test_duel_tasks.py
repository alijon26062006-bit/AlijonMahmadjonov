"""Генератор примеров: ответы верные, сложность растёт, повторов подряд нет."""

import operator

import pytest

from duel import tasks

OPS = {
    tasks.PLUS: operator.add,
    tasks.MINUS: operator.sub,
    tasks.TIMES: operator.mul,
    tasks.DIVIDE: operator.floordiv,
}


def solve(text):
    left, op, right = text.split(" ")
    return OPS[op](int(left), int(right))


@pytest.mark.parametrize("tier", range(tasks.MIN_TIER, tasks.MAX_TIER + 1))
def test_answers_are_correct_on_every_tier(tier):
    generator = tasks.TaskGenerator(seed=tier)
    for _ in range(300):
        task = generator.next(tier)
        assert solve(task.text) == task.answer, task.text


@pytest.mark.parametrize("tier", range(tasks.MIN_TIER, tasks.MAX_TIER + 1))
def test_answers_never_negative(tier):
    """Отрицательных ответов быть не должно — на клавиатуре нет минуса."""
    generator = tasks.TaskGenerator(seed=100 + tier)
    for _ in range(200):
        assert generator.next(tier).answer >= 0


def test_division_is_exact():
    generator = tasks.TaskGenerator(seed=5)
    seen = 0
    for _ in range(500):
        task = generator.next(8)
        if task.op == tasks.DIVIDE:
            seen += 1
            left, _, right = task.text.split(" ")
            assert int(left) % int(right) == 0
    assert seen > 0, "деление на восьмой ступени должно попадаться"


def test_no_two_identical_tasks_in_a_row():
    generator = tasks.TaskGenerator(seed=1)
    previous = ""
    for _ in range(400):
        task = generator.next(3)
        assert task.text != previous
        previous = task.text


def test_task_ids_grow():
    generator = tasks.TaskGenerator(seed=2)
    ids = [generator.next(4).id for _ in range(10)]
    assert ids == list(range(1, 11))


def test_public_view_hides_the_answer():
    task = tasks.TaskGenerator(seed=3).next(5)
    assert "answer" not in task.public()
    assert set(task.public()) == {"id", "q", "tier"}


def test_difficulty_grows_with_time():
    assert tasks.tier_for("easy", 0) < tasks.tier_for("easy", 120)
    assert tasks.tier_for("hard", 0) > tasks.tier_for("easy", 0)


def test_difficulty_has_a_ceiling():
    assert tasks.tier_for("easy", 10_000) == tasks.LEVEL_RAMP["easy"][1]
    assert tasks.tier_for("hard", 10_000) == tasks.MAX_TIER
    assert tasks.tier_for("auto", 10_000, 2000) == tasks.MAX_TIER


def test_auto_level_follows_rating():
    assert tasks.tier_for("auto", 0, 700) < tasks.tier_for("auto", 0, 1500)


def test_unknown_level_falls_back_to_normal():
    assert tasks.tier_for("чепуха", 0) == tasks.tier_for("normal", 0)

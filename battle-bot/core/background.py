"""Учёт фоновых задач.

Итоги раундов, напоминания и реклама живут в фоновых задачах. Если такая
задача тихо умрёт, снаружи это выглядит именно как «бот работает
нестабильно»: кнопки отвечают, а раунды не закрываются. Поэтому задачи
регистрируются здесь, и панель показывает, жива каждая или нет.
"""
from __future__ import annotations

import asyncio

_tasks: dict[str, asyncio.Task] = {}


def register(name: str, task: asyncio.Task) -> None:
    _tasks[name] = task


def run(coro, name: str) -> asyncio.Task:
    """Запустить разовую работу фоном и не потерять её.

    Ссылку на задачу держим: без неё сборщик мусора вправе выбросить задачу
    посреди работы. По окончании имя убирается, чтобы список задач не рос.
    """
    task = asyncio.ensure_future(coro)
    register(name, task)
    task.add_done_callback(lambda _: forget(name))
    return task


def forget(name: str | None = None) -> None:
    if name is None:
        _tasks.clear()
        return
    _tasks.pop(name, None)


def report() -> dict[str, bool]:
    """Имя задачи -> жива ли она."""
    if not _tasks:
        return {"фоновые задачи не запущены": False}
    return {name: not task.done() for name, task in _tasks.items()}


def failures() -> dict[str, BaseException]:
    """Задачи, которые упали, и с чем именно."""
    broken = {}
    for name, task in _tasks.items():
        if not task.done() or task.cancelled():
            continue
        error = task.exception()
        if error is not None:
            broken[name] = error
    return broken

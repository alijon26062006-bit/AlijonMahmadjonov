"""Отложенные уведомления: внутри быстрого ответа (webhook оплаты) сообщения в Telegram и push не шлём сразу —
копим и отправляем после ответа в отдельном потоке. Иначе каждый запрос к Telegram держал ответ банку по 10–40 с."""

from __future__ import annotations

import contextvars
import logging
import threading
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)
_jobs: contextvars.ContextVar[list | None] = contextvars.ContextVar("donatix_later", default=None)


def start() -> contextvars.Token:
    return _jobs.set([])


def defer(job: Callable[[Any], None]) -> bool:
    """Отложить отправку (job получит своё соединение с базой). False — откладывать некуда, шлите сразу."""
    jobs = _jobs.get()
    if jobs is None:
        return False
    jobs.append(job)
    return True


def finish(token: contextvars.Token, config: Any) -> None:
    """Снять режим и отправить накопленное в фоне."""
    jobs = _jobs.get() or []
    _jobs.reset(token)
    if jobs:
        threading.Thread(target=_run, args=(config, jobs), daemon=True).start()


def _run(config: Any, jobs: list) -> None:
    from . import db
    conn = db.connect(config.db_path)
    try:
        for job in jobs:
            try:
                job(conn)
            except Exception:  # noqa: BLE001 — одно неудачное уведомление не мешает остальным
                log.exception("отложенное уведомление")
    finally:
        conn.close()

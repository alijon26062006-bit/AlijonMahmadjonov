"""Фоновый обработчик анализов: берёт задачи из очереди в MySQL и сообщает результат в Telegram."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import socket
import time
from collections.abc import Awaitable
from datetime import timedelta
from typing import Protocol

from wbm.analysis.runner import AnalysisDeps, AnalysisFailed, RunLost, run_analysis
from wbm.bot import texts
from wbm.config import WorkerSettings
from wbm.db import repositories as repo
from wbm.db.base import utcnow
from wbm.report.pdf import build_pdf

logger = logging.getLogger(__name__)

INTERNAL_ERROR = "Внутренняя ошибка сервиса — мы уже разбираемся. Попробуйте позже."


class Notifier(Protocol):
    async def progress(self, chat_id: int, message_id: int | None, text: str) -> None: ...

    async def finished(
        self, chat_id: int, message_id: int | None, text: str, pdf: bytes, filename: str
    ) -> None: ...

    async def failed(self, chat_id: int, message_id: int | None, text: str) -> None: ...


def default_worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


class Worker:
    def __init__(
        self,
        deps: AnalysisDeps,
        settings: WorkerSettings,
        notifier: Notifier | None = None,
        worker_id: str | None = None,
    ) -> None:
        self._deps = deps
        self._settings = settings
        self._notifier = notifier
        self._id = worker_id or default_worker_id()

    async def run_forever(self, stop: asyncio.Event) -> None:
        tasks = [
            asyncio.create_task(self._slot(f"{self._id}-{n}", stop))
            for n in range(self._settings.concurrency)
        ]
        tasks.append(asyncio.create_task(self._maintenance(stop)))
        logger.info(
            "Воркер %s запущен, параллельно анализов: %d", self._id, self._settings.concurrency
        )
        await stop.wait()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _slot(self, slot_id: str, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                worked = await self.process_next(slot_id)
            except Exception:
                logger.exception("Сбой в цикле воркера %s", slot_id)
                worked = False
            if not worked:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=self._settings.poll_seconds)

    async def _maintenance(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                await self.requeue_stale()
            except Exception:
                logger.exception("Не удалось вернуть зависшие анализы в очередь")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=self._settings.stale_seconds / 2)

    async def requeue_stale(self) -> int:
        stale_before = self._deps.clock() - timedelta(seconds=self._settings.stale_seconds)
        async with self._deps.sessionmaker.begin() as session:
            moved = await repo.requeue_stale_runs(
                session, stale_before=stale_before, max_attempts=self._settings.max_attempts
            )
        if moved:
            logger.warning("Вернули в очередь зависших анализов: %d", moved)
        return moved

    async def process_next(self, slot_id: str) -> bool:
        """Берёт один анализ из очереди и выполняет. False — очередь пуста."""
        async with self._deps.sessionmaker.begin() as session:
            run = await repo.claim_next_run(session, slot_id)
            if run is None:
                return False
            run_id = run.id
            chat_id, message_id = run.notify_chat_id, run.notify_message_id
        async with self._deps.sessionmaker() as session:
            loaded = await repo.get_run_for_worker(session, run_id)
            shop_name = loaded.shop.name if loaded else "Магазин"

        last_edit = 0.0

        async def on_progress(percent: int, stage: str) -> None:
            nonlocal last_edit
            if self._notifier is None or chat_id is None:
                return
            if time.monotonic() - last_edit < 3:  # не чаще раза в 3 с — лимиты Telegram
                return
            last_edit = time.monotonic()
            await self._safe(
                self._notifier.progress(
                    chat_id, message_id, texts.progress_text(shop_name, percent, stage)
                )
            )

        heartbeat = asyncio.create_task(self._heartbeat(run_id, slot_id))
        try:
            await run_analysis(self._deps, run_id, slot_id, on_progress)
        except RunLost as exc:
            logger.warning("%s", exc)
            return True
        except AnalysisFailed as exc:
            await self._fail(run_id, slot_id, chat_id, message_id, shop_name, str(exc))
            return True
        except Exception:
            logger.exception("Анализ %d упал", run_id)
            await self._fail(run_id, slot_id, chat_id, message_id, shop_name, INTERNAL_ERROR)
            return True
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat

        await self._notify_done(run_id, chat_id, message_id, shop_name)
        return True

    async def _heartbeat(self, run_id: int, slot_id: str) -> None:
        while True:
            await asyncio.sleep(self._settings.heartbeat_seconds)
            try:
                async with self._deps.sessionmaker.begin() as session:
                    if not await repo.heartbeat(session, run_id, slot_id):
                        return
            except Exception:
                logger.exception("Не удалось отметить, что анализ %d жив", run_id)

    async def _fail(
        self,
        run_id: int,
        slot_id: str,
        chat_id: int | None,
        message_id: int | None,
        shop_name: str,
        reason: str,
    ) -> None:
        async with self._deps.sessionmaker.begin() as session:
            await repo.fail_run(session, run_id, slot_id, error=reason)
        if self._notifier is not None and chat_id is not None:
            await self._safe(
                self._notifier.failed(chat_id, message_id, texts.run_failed(shop_name, reason))
            )

    async def _notify_done(
        self, run_id: int, chat_id: int | None, message_id: int | None, shop_name: str
    ) -> None:
        if self._notifier is None or chat_id is None:
            return
        async with self._deps.sessionmaker() as session:
            run = await repo.load_run_details(session, run_id)
            if run is None:
                return
            text = texts.run_summary(run, shop_name)
            pdf = build_pdf(run, shop_name)
            moment = (run.finished_at or utcnow()).strftime("%Y-%m-%d")
        await self._safe(
            self._notifier.finished(
                chat_id, message_id, text, pdf, f"wb-analysis-{run_id}-{moment}.pdf"
            )
        )

    @staticmethod
    async def _safe(call: Awaitable[None]) -> None:
        """Сбой Telegram не должен ронять воркер: результат уже сохранён, его видно в /history."""
        try:
            await call
        except Exception:
            logger.exception("Не удалось отправить сообщение в Telegram")

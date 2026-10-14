"""Один анализ магазина целиком: данные WB → аномалии → проверки → текст → база."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from wbm.analysis.anomalies import apply_anomalies, detect_anomalies
from wbm.analysis.persist import check_records, dataset_records, summary
from wbm.checks import Thresholds, run_checks
from wbm.collectors import Collector, collect_all
from wbm.config import WBSettings
from wbm.db import repositories as repo
from wbm.db.base import utcnow
from wbm.domain.data import DataBundle
from wbm.report import ReportWriter, generate_report, render_markdown
from wbm.security.crypto import TokenCipher, TokenDecryptError
from wbm.wb_client import WBClient

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, str], Awaitable[None]]


class AnalysisFailed(Exception):
    """Анализ не выполнить; сообщение можно показать продавцу."""


class RunLost(Exception):
    """Анализ забрал другой воркер или он уже завершён — тихо прекращаем работу."""


@dataclass(slots=True)
class AnalysisDeps:
    sessionmaker: async_sessionmaker[AsyncSession]
    cipher: TokenCipher
    wb_settings: WBSettings
    report_writer: ReportWriter | None = None
    collectors: list[Collector] | None = None
    thresholds: Thresholds = field(default_factory=Thresholds)
    clock: Callable[[], datetime] = utcnow


async def run_analysis(
    deps: AnalysisDeps,
    run_id: int,
    worker_id: str,
    on_progress: ProgressCallback | None = None,
) -> None:
    async with deps.sessionmaker() as session:
        run = await repo.get_run_for_worker(session, run_id)
        if run is None:
            raise RunLost(f"Анализ {run_id} не найден")
        shop = run.shop
        shop_id, shop_name, period_days = shop.id, shop.name, run.period_days
        token_encrypted, sandbox = shop.token_encrypted, shop.sandbox
        categories = list(shop.token_categories)
        cost_prices = await repo.get_cost_prices(session, shop_id)

    async def progress(percent: int, stage: str) -> None:
        async with deps.sessionmaker.begin() as session:
            if not await repo.report_progress(
                session, run_id, worker_id, progress=percent, stage=stage
            ):
                raise RunLost(f"Анализ {run_id} больше не наш")
        if on_progress is not None:
            await on_progress(percent, stage)

    try:
        token = deps.cipher.decrypt(token_encrypted)
    except TokenDecryptError:
        raise AnalysisFailed(
            "Не удалось прочитать сохранённый токен. Пришлите токен WB заново."
        ) from None

    await progress(5, "Подключаемся к WB")
    data = DataBundle(now=deps.clock(), period_days=period_days, cost_prices=cost_prices)
    settings = deps.wb_settings.model_copy(update={"sandbox": sandbox})
    step = 0

    async def collector_progress(stage: str) -> None:
        nonlocal step
        step += 1
        await progress(min(10 + step * 5, 70), stage)

    async with WBClient(token, settings, log_name=f"магазин {shop_id}") as client:
        await collect_all(
            client,
            data,
            available=categories,
            history_days=period_days * 2,
            progress=collector_progress,
            collectors=deps.collectors,
        )

    await progress(75, "Проверяем данные и ищем проблемы")
    anomalies = detect_anomalies(data)
    apply_anomalies(data, anomalies)
    outcomes = run_checks(data, deps.thresholds)

    await progress(85, "Пишем понятный отчёт")
    report = await generate_report(
        outcomes, shop_name=shop_name, period_days=period_days, writer=deps.report_writer
    )
    run_summary = summary(outcomes)
    run_summary["report_source"] = report.source
    run_summary["anomalies"] = [a.message for a in anomalies]

    async with deps.sessionmaker.begin() as session:
        finished = await repo.finish_run(
            session,
            run_id,
            worker_id,
            datasets=dataset_records(data),
            checks=check_records(outcomes, report.texts),
            summary={"summary_text": report.summary, **run_summary},
            report_text=render_markdown(outcomes, report),
        )
    if not finished:
        raise RunLost(f"Анализ {run_id} завершил кто-то другой")
    logger.info(
        "Анализ %d магазина %d готов: проблем %s, текст: %s",
        run_id,
        shop_id,
        run_summary["problems"],
        report.source,
    )

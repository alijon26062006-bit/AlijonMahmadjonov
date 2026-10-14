"""Сборщики данных: ответ WB → данные магазина в нашем формате (wbm.domain.data).

Каждый сборщик добавляется ТОЛЬКО после сверки метода с документацией WB.
Пока сборщика нет, набор данных помечается «метод WB ещё не подключён»,
и проверки, которым он нужен, честно пишут «нет данных».
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime

from wbm.domain.data import DataBundle, DataResult, Dataset
from wbm.wb_client import Category, WBClient, WBError

logger = logging.getLogger(__name__)

CollectFn = Callable[[WBClient, datetime, int], Awaitable[DataResult[object]]]


@dataclass(frozen=True, slots=True)
class Collector:
    dataset: Dataset
    category: Category
    title: str
    collect: CollectFn
    """(клиент, момент анализа, сколько дней истории) → данные."""


COLLECTORS: list[Collector] = []
"""Подключённые сборщики — только сверенные с документацией (см. register_default_collectors)."""

NOT_CONNECTED = "метод WB ещё не подключён (ждём сверки с документацией)"

ProgressFn = Callable[[str], Awaitable[None]]


async def collect_all(
    client: WBClient,
    data: DataBundle,
    *,
    available: Iterable[str],
    history_days: int,
    progress: ProgressFn | None = None,
    collectors: list[Collector] | None = None,
) -> None:
    """Заполняет data. Ошибка одного набора не мешает остальным."""
    allowed = set(available)
    active = COLLECTORS if collectors is None else collectors
    connected = {c.dataset for c in active}
    for dataset in Dataset:
        if dataset in (Dataset.COST_PRICES, Dataset.PREVIOUS_STOCKS):
            continue
        if dataset not in connected:
            data.set_result(dataset, DataResult.skipped(NOT_CONNECTED))

    for collector in active:
        if collector.category.value not in allowed:
            data.set_result(
                collector.dataset,
                DataResult.skipped(f"в токене нет доступа к разделу «{collector.category.value}»"),
            )
            continue
        if progress is not None:
            await progress(f"Загружаем {collector.title}")
        try:
            result = await collector.collect(client, data.now, history_days)
        except WBError as exc:
            logger.warning("%s: не загрузились %s: %s", client.log_name, collector.dataset, exc)
            result = DataResult.error(str(exc))
        except Exception:
            logger.exception("%s: сбой сборщика %s", client.log_name, collector.dataset)
            result = DataResult.error("внутренняя ошибка при загрузке")
        data.set_result(collector.dataset, result)


def _register_default_collectors() -> None:
    from wbm.collectors.reports import collect_orders, collect_paid_storage

    COLLECTORS.extend(
        [
            Collector(Dataset.ORDERS, Category.STATISTICS, "заказы", collect_orders),
            Collector(
                Dataset.PAID_STORAGE,
                Category.ANALYTICS,
                "отчёт о платном хранении",
                collect_paid_storage,
            ),
        ]
    )


_register_default_collectors()

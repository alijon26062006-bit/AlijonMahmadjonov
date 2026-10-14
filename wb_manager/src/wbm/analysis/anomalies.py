"""Проверка данных на аномалии ДО выводов.

Ловим ситуации, когда данные выглядят как сбой WB API, а не как реальность:
например, обрыв заказов до нуля при обычной истории. Такой набор помечается
ANOMALY, а выводы проверок по нему идут с явной оговоркой в отчёте.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import date, timedelta

from wbm.domain.data import DataBundle, DataResult, Dataset
from wbm.domain.enums import DatasetStatus

MIN_DAILY_ORDERS_FOR_GAP = 5.0
"""С какого среднего числа заказов в день «ноль за день» уже подозрителен."""
MAX_GAP_DAYS = 2
"""Ноль заказов подряд столько дней и больше при обычном потоке — аномалия."""
MIN_ORDERS_FOR_EMPTY_CHECK = 20


@dataclass(frozen=True, slots=True)
class Anomaly:
    dataset: Dataset
    message: str


def detect_anomalies(data: DataBundle) -> list[Anomaly]:
    anomalies: list[Anomaly] = []
    if data.orders.status is DatasetStatus.OK:
        anomalies += _order_gaps(data)
    orders_in_period = _orders_in_period(data)
    if data.sales.status is DatasetStatus.EMPTY and orders_in_period >= MIN_ORDERS_FOR_EMPTY_CHECK:
        anomalies.append(
            Anomaly(
                Dataset.SALES,
                f"WB вернул пустой список продаж, хотя заказов за период {orders_in_period}",
            )
        )
    if (
        data.finance.status is DatasetStatus.EMPTY
        and orders_in_period >= MIN_ORDERS_FOR_EMPTY_CHECK
    ):
        anomalies.append(
            Anomaly(
                Dataset.FINANCE,
                f"Финансовый отчёт пустой, хотя заказов за период {orders_in_period} "
                "(возможно, WB ещё не сформировал отчёт)",
            )
        )
    if data.stocks.status is DatasetStatus.EMPTY and orders_in_period >= MIN_ORDERS_FOR_EMPTY_CHECK:
        anomalies.append(
            Anomaly(
                Dataset.STOCKS,
                f"WB вернул нулевые остатки по всем товарам, хотя заказов за период {orders_in_period}",
            )
        )
    return anomalies


def apply_anomalies(data: DataBundle, anomalies: list[Anomaly]) -> None:
    """Помечает наборы данных статусом ANOMALY с пояснением."""
    for anomaly in anomalies:
        current = data.result(anomaly.dataset)
        message = "; ".join(m for m in (current.message, anomaly.message) if m)
        marked: DataResult[object] = replace(current, status=DatasetStatus.ANOMALY, message=message)
        data.set_result(anomaly.dataset, marked)


def _orders_in_period(data: DataBundle) -> int:
    if not data.orders.usable:
        return 0
    start = data.now - timedelta(days=data.period_days)
    return sum(1 for o in data.orders.rows if o.created_at >= start)


def _order_gaps(data: DataBundle) -> list[Anomaly]:
    """Дни подряд без единого заказа посреди обычного потока — похоже на сбой выгрузки."""
    start_day = (data.now - timedelta(days=data.period_days)).date()
    end_day = data.now.date()
    per_day: Counter[date] = Counter(
        o.created_at.date() for o in data.orders.rows if start_day <= o.created_at.date() < end_day
    )
    days = [start_day + timedelta(days=i) for i in range((end_day - start_day).days)]
    if not days:
        return []
    average = sum(per_day.values()) / len(days)
    if average < MIN_DAILY_ORDERS_FOR_GAP:
        return []

    longest, current, gap_end = 0, 0, None
    for day in days:
        if per_day.get(day, 0) == 0:
            current += 1
            if current > longest:
                longest, gap_end = current, day
        else:
            current = 0
    if longest < MAX_GAP_DAYS or gap_end is None:
        return []
    gap_start = gap_end - timedelta(days=longest - 1)
    return [
        Anomaly(
            Dataset.ORDERS,
            f"Нет ни одного заказа {longest} дн. подряд ({gap_start:%d.%m}–{gap_end:%d.%m}) "
            f"при среднем {average:.0f} заказов в день — похоже на сбой выгрузки WB",
        )
    ]

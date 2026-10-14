"""Сборщики раздела «Отчёты»: заказы и платное хранение."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from wbm.domain.data import DataResult, Order, StorageCost
from wbm.wb_client import WBClient
from wbm.wb_client.api.reports import MOSCOW, ReportsAPI, parse_wb_datetime
from wbm.wb_client.errors import WBError

logger = logging.getLogger(__name__)

MAX_ORDER_PAGES = 20
"""До ~80 000 строк на страницу — 20 страниц с запасом на любой магазин за 60 дней."""

STORAGE_WINDOW_DAYS = 7
"""WB отдаёт платное хранение максимум за 8 дней одним отчётом — берём по 7."""
STORAGE_POLL_SECONDS = 5.0
STORAGE_MAX_POLLS = 36
"""Ждём готовности отчёта до ~3 минут."""


async def collect_orders(client: WBClient, now: datetime, days: int) -> DataResult[object]:
    api = ReportsAPI(client)
    since = now - timedelta(days=days)
    cursor: datetime | str = since
    orders: dict[str, Order] = {}
    for _ in range(MAX_ORDER_PAGES):
        page = await api.orders_page(cursor)
        if not page:
            break
        for row in page:
            created = parse_wb_datetime(row.date)
            if created < since:
                continue
            key = row.srid or f"{row.nm_id}:{row.date}:{len(orders)}"
            # Строка с тем же srid приходит снова при изменении (например, отмене) — берём свежую.
            orders[key] = Order(
                order_id=key,
                created_at=created,
                nm_id=row.nm_id,
                vendor_code=row.supplier_article,
                price=row.price_with_disc,
                is_cancelled=row.is_cancel,
            )
        last = page[-1].last_change_date
        if last == (cursor if isinstance(cursor, str) else None):
            break  # курсор не сдвинулся — защита от бесконечного цикла
        cursor = last
    else:
        logger.warning(
            "%s: заказов больше %d страниц, взяли первые", client.log_name, MAX_ORDER_PAGES
        )
    return DataResult.ok(orders.values())


def storage_windows(now: datetime, days: int) -> list[tuple[date, date]]:
    """Окна по 7 дней (по московским датам), покрывающие последние `days` дней."""
    end = now.astimezone(MOSCOW).date()
    start = end - timedelta(days=days - 1)
    windows = []
    while start <= end:
        window_end = min(start + timedelta(days=STORAGE_WINDOW_DAYS - 1), end)
        windows.append((start, window_end))
        start = window_end + timedelta(days=1)
    return windows


async def collect_paid_storage(client: WBClient, now: datetime, days: int) -> DataResult[object]:
    api = ReportsAPI(client)
    # Для проверок нужен только анализируемый период, а не двойная история.
    period = max(1, days // 2)
    costs: list[StorageCost] = []
    for date_from, date_to in storage_windows(now, period):
        task_id = await api.create_paid_storage(date_from, date_to)
        for _ in range(STORAGE_MAX_POLLS):
            status = await api.paid_storage_status(task_id)
            if status == "done":
                break
            await client.sleep(STORAGE_POLL_SECONDS)
        else:
            raise WBError(
                f"WB не подготовил отчёт о платном хранении за {date_from:%d.%m}–{date_to:%d.%m} "
                f"(последний статус: {status})"
            )
        for row in await api.download_paid_storage(task_id):
            day = datetime.fromisoformat(row.date).replace(tzinfo=MOSCOW)
            costs.append(
                StorageCost(
                    day=day, nm_id=row.nm_id, vendor_code=row.vendor_code, cost=row.warehouse_price
                )
            )
    return DataResult.ok(costs)

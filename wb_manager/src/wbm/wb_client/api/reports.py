"""Раздел «Отчёты»: заказы (Статистика) и платное хранение (Аналитика).

Поля моделей — из примеров ответов документации WB (docs/WB_API.md). Лишние поля
игнорируются, отсутствующие необязательные — по умолчанию.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

from pydantic import Field, TypeAdapter, ValidationError

from wbm.wb_client.api._base import WBModel, parse_model
from wbm.wb_client.client import WBClient
from wbm.wb_client.endpoints import (
    PAID_STORAGE_CREATE,
    PAID_STORAGE_DOWNLOAD,
    PAID_STORAGE_STATUS,
    STATS_ORDERS,
    Endpoint,
)
from wbm.wb_client.errors import WBInvalidResponseError

MOSCOW = timezone(timedelta(hours=3), "MSK")
"""Даты в отчётах WB — по Москве (UTC+3, без перехода на летнее время)."""


def to_moscow_param(moment: datetime) -> str:
    """datetime → параметр dateFrom в формате RFC3339 по московскому времени."""
    return moment.astimezone(MOSCOW).replace(tzinfo=None).isoformat(timespec="seconds")


def parse_wb_datetime(raw: str) -> datetime:
    """'2022-03-04T18:08:31' (по Москве) → aware UTC. Если пояс указан — учитываем его."""
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=MOSCOW)
    return value.astimezone(UTC)


class OrderRow(WBModel):
    date: str
    last_change_date: str = Field(alias="lastChangeDate")
    nm_id: int = Field(alias="nmId")
    supplier_article: str = Field(default="", alias="supplierArticle")
    srid: str = ""
    is_cancel: bool = Field(default=False, alias="isCancel")
    price_with_disc: Decimal = Field(default=Decimal(0), alias="priceWithDisc")
    finished_price: Decimal = Field(default=Decimal(0), alias="finishedPrice")
    warehouse_type: str = Field(default="", alias="warehouseType")
    subject: str = ""
    brand: str = ""


class TaskId(WBModel):
    task_id: str = Field(alias="taskId")


class _TaskEnvelope(WBModel):
    data: TaskId


class TaskStatus(WBModel):
    id: str = ""
    status: str


class _StatusEnvelope(WBModel):
    data: TaskStatus


class StorageRow(WBModel):
    date: str
    nm_id: int = Field(alias="nmId")
    vendor_code: str = Field(default="", alias="vendorCode")
    warehouse: str = ""
    warehouse_price: Decimal = Field(default=Decimal(0), alias="warehousePrice")


_ORDERS = TypeAdapter(list[OrderRow])
_STORAGE = TypeAdapter(list[StorageRow])


def _parse_list[T](adapter: TypeAdapter[list[T]], data: object, endpoint: Endpoint) -> list[T]:
    if data is None:
        return []
    try:
        return adapter.validate_python(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"])
        raise WBInvalidResponseError(
            f"{endpoint.name}: ответ WB не совпадает с ожидаемой схемой (поле «{location}»)"
        ) from None


class ReportsAPI:
    def __init__(self, client: WBClient) -> None:
        self._client = client

    async def orders_page(self, date_from: datetime | str) -> list[OrderRow]:
        """Одна страница заказов, изменённых после date_from (строка — как lastChangeDate из WB)."""
        value = date_from if isinstance(date_from, str) else to_moscow_param(date_from)
        data = await self._client.request(STATS_ORDERS, params={"dateFrom": value, "flag": 0})
        return _parse_list(_ORDERS, data, STATS_ORDERS)

    async def create_paid_storage(self, date_from: date, date_to: date) -> str:
        data = await self._client.request(
            PAID_STORAGE_CREATE,
            params={"dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat()},
        )
        return parse_model(_TaskEnvelope, data, PAID_STORAGE_CREATE).data.task_id

    async def paid_storage_status(self, task_id: str) -> str:
        data = await self._client.request(PAID_STORAGE_STATUS, path_params={"task_id": task_id})
        return parse_model(_StatusEnvelope, data, PAID_STORAGE_STATUS).data.status

    async def download_paid_storage(self, task_id: str) -> list[StorageRow]:
        data = await self._client.request(PAID_STORAGE_DOWNLOAD, path_params={"task_id": task_id})
        return _parse_list(_STORAGE, data, PAID_STORAGE_DOWNLOAD)

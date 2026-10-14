"""Сборщики «Отчётов» на ответах в формате примеров из документации WB."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest
import respx

from tests.conftest import ClientFactory
from tests.helpers import FakeClock
from wbm.collectors import COLLECTORS, collect_all
from wbm.collectors.reports import (
    STORAGE_MAX_POLLS,
    collect_orders,
    collect_paid_storage,
    storage_windows,
)
from wbm.domain.data import DataBundle, Dataset, Order, StorageCost
from wbm.domain.enums import DatasetStatus
from wbm.wb_client.api.reports import parse_wb_datetime, to_moscow_param
from wbm.wb_client.errors import WBError

NOW = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
ORDERS_URL = "https://statistics-api.wildberries.ru/api/v1/supplier/orders"
STORAGE = "https://seller-analytics-api.wildberries.ru/api/v1/paid_storage"


def order(
    srid: str, date_: str, changed: str, *, cancel: bool = False, nm: int = 1234567
) -> dict[str, object]:
    """Строка заказа в формате примера из документации."""
    return {
        "date": date_,
        "lastChangeDate": changed,
        "warehouseName": "Склад WB РФ",
        "warehouseType": "Склад продавца",
        "supplierArticle": "12345",
        "nmId": nm,
        "barcode": "123453559000",
        "subject": "Мультистайлеры",
        "brand": "Тест",
        "totalPrice": 1887,
        "discountPercent": 18,
        "spp": 26,
        "finishedPrice": 1145,
        "priceWithDisc": 1547,
        "isCancel": cancel,
        "cancelDate": "0001-01-01T00:00:00",
        "srid": srid,
    }


def test_moscow_time_conversion() -> None:
    assert to_moscow_param(datetime(2026, 9, 14, 12, 0, tzinfo=UTC)) == "2026-09-14T15:00:00"
    assert parse_wb_datetime("2026-10-10T18:00:00") == datetime(2026, 10, 10, 15, 0, tzinfo=UTC)
    assert parse_wb_datetime("2026-10-10T18:00:00.123").microsecond == 123000


async def test_orders_paginated_and_deduplicated(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(ORDERS_URL)
    route.side_effect = [
        httpx.Response(
            200,
            json=[
                order("a", "2026-10-10T18:00:00", "2026-10-10T18:05:00"),
                order("old", "2026-07-01T10:00:00", "2026-10-11T09:00:00"),  # старше периода
                order("b", "2026-10-11T10:00:00", "2026-10-11T10:00:00"),
            ],
        ),
        httpx.Response(
            200, json=[order("a", "2026-10-10T18:00:00", "2026-10-12T08:00:00", cancel=True)]
        ),
        httpx.Response(200, json=[]),
    ]

    result = await collect_orders(make_client(), NOW, 60)

    assert result.status is DatasetStatus.OK
    rows = {o.order_id: o for o in result.rows if isinstance(o, Order)}
    assert set(rows) == {"a", "b"}
    assert rows["a"].is_cancelled  # взята свежая версия строки
    assert rows["a"].created_at == datetime(2026, 10, 10, 15, 0, tzinfo=UTC)
    assert rows["a"].price == Decimal(1547)
    assert rows["a"].vendor_code == "12345"
    params = [dict(call.request.url.params) for call in route.calls]
    assert params[0] == {"dateFrom": "2026-08-15T15:00:00", "flag": "0"}
    assert params[1]["dateFrom"] == "2026-10-11T10:00:00"
    assert params[2]["dateFrom"] == "2026-10-12T08:00:00"


async def test_orders_empty(make_client: ClientFactory, respx_mock: respx.MockRouter) -> None:
    respx_mock.get(ORDERS_URL).respond(200, json=[])

    result = await collect_orders(make_client(), NOW, 60)

    assert result.status is DatasetStatus.EMPTY


async def test_orders_unexpected_format(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(ORDERS_URL).respond(200, json={"error": "что-то новое"})

    with pytest.raises(WBError, match="схемой"):
        await collect_orders(make_client(), NOW, 60)


def test_storage_windows_cover_period_in_chunks_of_seven_days() -> None:
    windows = storage_windows(NOW, 30)

    assert windows[0] == (date(2026, 9, 15), date(2026, 9, 21))
    assert windows[-1] == (date(2026, 10, 13), date(2026, 10, 14))
    assert all((end - start).days < 8 for start, end in windows)
    assert sum((end - start).days + 1 for start, end in windows) == 30


async def test_paid_storage_flow(
    make_client: ClientFactory, respx_mock: respx.MockRouter, clock: FakeClock
) -> None:
    create = respx_mock.get(STORAGE).respond(200, json={"data": {"taskId": "t1"}})
    status = respx_mock.get(f"{STORAGE}/tasks/t1/status")
    status.side_effect = [
        httpx.Response(200, json={"data": {"id": "t1", "status": "processing"}}),
        httpx.Response(200, json={"data": {"id": "t1", "status": "done"}}),
    ]
    respx_mock.get(f"{STORAGE}/tasks/t1/download").respond(
        200,
        json=[
            {
                "date": "2026-10-10",
                "warehouse": "Коледино",
                "vendorCode": "567383",
                "nmId": 1234567,
                "warehousePrice": 7.65,
                "volume": 12,
                "calcType": "короба: без габаритов",
            },
        ],
    )

    result = await collect_paid_storage(make_client(), NOW, 14)  # период 7 дней → одно окно

    assert create.calls[0].request.url.params["dateFrom"] == "2026-10-08"
    assert create.calls[0].request.url.params["dateTo"] == "2026-10-14"
    rows = [r for r in result.rows if isinstance(r, StorageCost)]
    assert rows[0].cost == Decimal("7.65")
    assert rows[0].vendor_code == "567383"
    assert 5.0 in clock.sleeps  # подождали между опросами статуса


async def test_paid_storage_no_data(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(STORAGE).respond(200, json={"data": {"taskId": "t1"}})
    respx_mock.get(f"{STORAGE}/tasks/t1/status").respond(200, json={"data": {"status": "done"}})
    respx_mock.get(f"{STORAGE}/tasks/t1/download").respond(204)

    result = await collect_paid_storage(make_client(), NOW, 14)

    assert result.status is DatasetStatus.EMPTY


async def test_paid_storage_never_ready(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(STORAGE).respond(200, json={"data": {"taskId": "t1"}})
    status = respx_mock.get(f"{STORAGE}/tasks/t1/status").respond(
        200, json={"data": {"status": "processing"}}
    )

    with pytest.raises(WBError, match="не подготовил"):
        await collect_paid_storage(make_client(), NOW, 14)
    assert status.call_count == STORAGE_MAX_POLLS


async def test_collect_all_with_real_collectors(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(ORDERS_URL).side_effect = [
        httpx.Response(200, json=[order("a", "2026-10-10T18:00:00", "2026-10-10T18:05:00")]),
        httpx.Response(200, json=[]),
    ]
    data = DataBundle(now=NOW)

    # Доступа к Аналитике нет — хранение помечается, заказы загружаются.
    await collect_all(make_client(), data, available=["statistics"], history_days=60)

    assert {c.dataset for c in COLLECTORS} == {Dataset.ORDERS, Dataset.PAID_STORAGE}
    assert data.orders.status is DatasetStatus.OK
    assert data.paid_storage.status is DatasetStatus.SKIPPED
    assert "нет доступа" in (data.paid_storage.message or "")
    assert data.feedbacks.status is DatasetStatus.SKIPPED
    assert "не подключён" in (data.feedbacks.message or "")

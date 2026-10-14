from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from tests.conftest import ClientFactory
from tests.helpers import personal_token, sandbox_token, scopes
from wbm.wb_client.categories import Category
from wbm.wb_client.token_check import CategoryStatus, check_token

NOW = datetime(2026, 10, 14, tzinfo=UTC)
OK = {"TS": "2026-10-14T10:00:00+03:00", "Status": "OK"}


def ping_url(host: str) -> str:
    return f"https://{host}.wildberries.ru/ping"


async def test_all_categories_available(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    for host in ("common-api", "content-api", "statistics-api", "feedbacks-api"):
        respx_mock.get(ping_url(host)).respond(200, json=OK)
    categories = [Category.COMMON, Category.CONTENT, Category.STATISTICS, Category.FEEDBACKS]

    result = await check_token(make_client(), categories, now=NOW)

    assert result.valid
    assert result.available == set(categories)
    assert result.warnings == ()


async def test_missing_category_is_reported(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(ping_url("content-api")).respond(200, json=OK)
    respx_mock.get(ping_url("seller-analytics-api")).respond(403)

    result = await check_token(make_client(), [Category.CONTENT, Category.ANALYTICS], now=NOW)

    assert result.valid
    assert result.available == {Category.CONTENT}
    denied = next(c for c in result.categories if c.category is Category.ANALYTICS)
    assert denied.status is CategoryStatus.DENIED
    assert "Аналитика" in denied.message


async def test_rejected_token(make_client: ClientFactory, respx_mock: respx.MockRouter) -> None:
    respx_mock.get(ping_url("content-api")).respond(401, json={"title": "unauthorized"})

    result = await check_token(make_client(), [Category.CONTENT], now=NOW)

    assert not result.valid
    assert result.categories[0].status is CategoryStatus.UNAUTHORIZED
    assert any("не принял токен" in w for w in result.warnings)


async def test_expired_token_is_not_sent_to_wb(make_client: ClientFactory) -> None:
    client = make_client(personal_token(exp=int((NOW - timedelta(days=1)).timestamp())))

    result = await check_token(client, [Category.CONTENT], now=NOW)

    assert not result.valid
    assert result.categories == ()
    assert "истёк" in result.warnings[0]


async def test_sandbox_categories(make_client: ClientFactory, respx_mock: respx.MockRouter) -> None:
    respx_mock.get("https://content-api-sandbox.wildberries.ru/ping").respond(200, json=OK)

    result = await check_token(
        make_client(sandbox_token(), sandbox=True), [Category.CONTENT, Category.ANALYTICS], now=NOW
    )

    statuses = {c.category: c.status for c in result.categories}
    assert statuses == {
        Category.CONTENT: CategoryStatus.OK,
        Category.ANALYTICS: CategoryStatus.SANDBOX_UNAVAILABLE,
    }
    assert any("тестовый токен" in w for w in result.warnings)


async def test_wb_unavailable_is_an_error_not_a_denial(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(ping_url("content-api")).respond(503)
    respx_mock.get(ping_url("statistics-api")).mock(side_effect=httpx.ConnectError("refused"))

    result = await check_token(
        make_client(max_retries=0), [Category.CONTENT, Category.STATISTICS], now=NOW
    )

    assert result.valid
    assert {c.status for c in result.categories} == {CategoryStatus.ERROR}


async def test_ping_status_not_ok(make_client: ClientFactory, respx_mock: respx.MockRouter) -> None:
    respx_mock.get(ping_url("content-api")).respond(200, json={"Status": "MAINTENANCE"})

    result = await check_token(make_client(), [Category.CONTENT], now=NOW)

    assert result.categories[0].status is CategoryStatus.ERROR


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        (personal_token(s=scopes(1)), "Только на чтение"),
        ("abc.def.ghi", "Не удалось прочитать права"),
        (personal_token(exp=int((NOW + timedelta(days=5)).timestamp())), "перестанет работать"),
    ],
)
async def test_warnings(
    make_client: ClientFactory, respx_mock: respx.MockRouter, token: str, expected: str
) -> None:
    respx_mock.get(ping_url("content-api")).respond(200, json=OK)

    result = await check_token(make_client(token), [Category.CONTENT], now=NOW)

    assert any(expected in w for w in result.warnings), result.warnings


async def test_scope_mismatch_is_logged(
    make_client: ClientFactory, respx_mock: respx.MockRouter, caplog: pytest.LogCaptureFixture
) -> None:
    # По расшифровке у токена только Контент, а WB подтвердил и Статистику.
    respx_mock.get(ping_url("statistics-api")).respond(200, json=OK)

    with caplog.at_level(logging.WARNING):
        await check_token(make_client(personal_token(s=scopes(1, 30))), [Category.STATISTICS])

    assert "не совпала" in caplog.text

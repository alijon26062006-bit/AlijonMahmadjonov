from __future__ import annotations

import asyncio
import dataclasses
import logging

import httpx
import pytest
import respx

from tests.conftest import ClientFactory
from tests.helpers import SELLER_ID, FakeClock, personal_token, sandbox_token
from wbm.wb_client.api.general import GeneralAPI
from wbm.wb_client.categories import Category
from wbm.wb_client.endpoints import PING, SELLER_INFO, SELLER_RATING, Endpoint
from wbm.wb_client.errors import (
    WBAccessDeniedError,
    WBBadRequestError,
    WBConfigError,
    WBError,
    WBForbiddenMethodError,
    WBHTTPError,
    WBInvalidResponseError,
    WBNetworkError,
    WBNotFoundError,
    WBPaymentRequiredError,
    WBRateLimitError,
    WBSandboxUnavailableError,
    WBServerError,
    WBUnauthorizedError,
)
from wbm.wb_client.ratelimit import RateLimit

SELLER_INFO_URL = "https://common-api.wildberries.ru/api/v1/seller-info"
RATING_URL = "https://feedbacks-api.wildberries.ru/api/common/v1/rating"
SELLER_BODY = {
    "name": "ИП Кружинин В. Р.",
    "sid": SELLER_ID,
    "tin": "1234567890",
    "tradeMark": "Flax Store",
}
PING_BODY = {"TS": "2024-08-16T11:19:05+03:00", "Status": "OK"}


# ── обычная работа ────────────────────────────────────────────────────────────


async def test_request_uses_prod_host_and_token_header(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    token = personal_token()
    route = respx_mock.get(SELLER_INFO_URL).respond(200, json=SELLER_BODY)

    info = await GeneralAPI(make_client(token)).seller_info()

    assert info.name == "ИП Кружинин В. Р."
    assert info.trade_mark == "Flax Store"
    request = route.calls.last.request
    assert request.headers["Authorization"] == token
    assert request.headers["User-Agent"].startswith("wbm/")


async def test_sandbox_uses_sandbox_host(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get("https://content-api-sandbox.wildberries.ru/ping").respond(
        200, json=PING_BODY
    )

    result = await GeneralAPI(make_client(sandbox_token(), sandbox=True)).ping(Category.CONTENT)

    assert result.status == "OK"
    assert route.called


async def test_category_without_sandbox(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    client = make_client(sandbox_token(), sandbox=True)

    with pytest.raises(WBSandboxUnavailableError, match="Тарифы"):
        await GeneralAPI(client).seller_info()


def test_test_token_is_rejected_in_prod(make_client: ClientFactory) -> None:
    with pytest.raises(WBConfigError, match="песочниц"):
        make_client(sandbox_token())


def test_prod_token_in_sandbox_only_warns(
    make_client: ClientFactory, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        make_client(personal_token(), sandbox=True)

    assert "токен не тестовый" in caplog.text


async def test_204_returns_none(make_client: ClientFactory, respx_mock: respx.MockRouter) -> None:
    respx_mock.get(SELLER_INFO_URL).respond(204)

    assert await make_client().request(SELLER_INFO) is None


# ── 429, 5xx, сеть ────────────────────────────────────────────────────────────


async def test_429_waits_for_retry_header(
    make_client: ClientFactory, respx_mock: respx.MockRouter, clock: FakeClock
) -> None:
    route = respx_mock.get(SELLER_INFO_URL)
    route.side_effect = [
        httpx.Response(429, headers={"X-Ratelimit-Retry": "2", "X-Ratelimit-Reset": "29"}),
        httpx.Response(200, json=SELLER_BODY),
    ]

    info = await GeneralAPI(make_client()).seller_info()

    assert info.sid == SELLER_ID
    assert route.call_count == 2
    assert clock.sleeps == [pytest.approx(2.0)]


async def test_429_without_header_uses_backoff(
    make_client: ClientFactory, respx_mock: respx.MockRouter, clock: FakeClock
) -> None:
    respx_mock.get(SELLER_INFO_URL).side_effect = [
        httpx.Response(429),
        httpx.Response(200, json=SELLER_BODY),
    ]

    await GeneralAPI(make_client()).seller_info()

    assert clock.sleeps == [pytest.approx(1.0)]


async def test_429_gives_up_after_retries(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(SELLER_INFO_URL).respond(429, headers={"X-Ratelimit-Retry": "1"})

    with pytest.raises(WBRateLimitError) as exc:
        await make_client(max_rate_limit_retries=2).request(SELLER_INFO)

    assert route.call_count == 3
    assert exc.value.retry_after == pytest.approx(1.0)


async def test_429_with_too_long_retry_fails_fast(
    make_client: ClientFactory, respx_mock: respx.MockRouter, clock: FakeClock
) -> None:
    route = respx_mock.get(SELLER_INFO_URL).respond(429, headers={"X-Ratelimit-Retry": "3600"})

    with pytest.raises(WBRateLimitError, match="ждать"):
        await make_client(max_wait=300).request(SELLER_INFO)

    assert route.call_count == 1
    assert clock.sleeps == []


async def test_5xx_retried_with_growing_pause(
    make_client: ClientFactory, respx_mock: respx.MockRouter, clock: FakeClock
) -> None:
    route = respx_mock.get(SELLER_INFO_URL)
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(502),
        httpx.Response(200, json=SELLER_BODY),
    ]

    await GeneralAPI(make_client(max_retries=3)).seller_info()

    assert route.call_count == 3
    assert clock.sleeps == [pytest.approx(1.0), pytest.approx(2.0)]


async def test_backoff_is_capped(
    make_client: ClientFactory, respx_mock: respx.MockRouter, clock: FakeClock
) -> None:
    respx_mock.get(SELLER_INFO_URL).respond(500)

    with pytest.raises(WBServerError):
        await make_client(max_retries=4, backoff_base=2, backoff_max=5).request(SELLER_INFO)

    assert clock.sleeps == [pytest.approx(2), pytest.approx(4), pytest.approx(5), pytest.approx(5)]


async def test_5xx_gives_up_after_retries(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(SELLER_INFO_URL).respond(
        500, json={"title": "internal error", "status": 500}
    )

    with pytest.raises(WBServerError) as exc:
        await make_client(max_retries=2).request(SELLER_INFO)

    assert route.call_count == 3
    assert exc.value.status == 500
    assert exc.value.title == "internal error"


async def test_timeout_is_retried(
    make_client: ClientFactory, respx_mock: respx.MockRouter, clock: FakeClock
) -> None:
    respx_mock.get(SELLER_INFO_URL).side_effect = [
        httpx.ConnectTimeout("timed out"),
        httpx.Response(200, json=SELLER_BODY),
    ]

    await GeneralAPI(make_client()).seller_info()

    assert clock.sleeps == [pytest.approx(1.0)]


async def test_network_error_gives_up(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(SELLER_INFO_URL)
    route.side_effect = httpx.ConnectError("connection refused")

    with pytest.raises(WBNetworkError, match="ConnectError"):
        await make_client(max_retries=2).request(SELLER_INFO)

    assert route.call_count == 3


# ── коды ошибок и формат ответа ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("status", "error_cls"),
    [
        (400, WBBadRequestError),
        (401, WBUnauthorizedError),
        (402, WBPaymentRequiredError),
        (403, WBAccessDeniedError),
        (404, WBNotFoundError),
        (409, WBBadRequestError),
        (413, WBBadRequestError),
        (422, WBBadRequestError),
        (418, WBHTTPError),
        (302, WBHTTPError),
    ],
)
async def test_error_statuses_are_not_retried(
    make_client: ClientFactory,
    respx_mock: respx.MockRouter,
    status: int,
    error_cls: type[WBHTTPError],
) -> None:
    route = respx_mock.get(SELLER_INFO_URL).respond(status)

    with pytest.raises(error_cls) as exc:
        await make_client().request(SELLER_INFO)

    assert route.call_count == 1
    assert exc.value.status == status
    assert exc.value.endpoint == SELLER_INFO.name


async def test_error_body_new_format(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(SELLER_INFO_URL).respond(
        401,
        json={
            "title": "unauthorized",
            "detail": "token is expired",
            "requestId": "c479c04d0b576a9b",
            "origin": "s2s-api-auth",
            "status": 401,
            "statusText": "Unauthorized",
            "timestamp": "2025-04-24T07:25:28Z",
        },
    )

    with pytest.raises(WBUnauthorizedError) as exc:
        await make_client().request(SELLER_INFO)

    assert exc.value.title == "unauthorized"
    assert exc.value.detail == "token is expired"
    assert exc.value.request_id == "c479c04d0b576a9b"
    assert "token is expired" in str(exc.value)


async def test_error_body_content_format(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get("https://content-api.wildberries.ru/ping").respond(
        403,
        json={"data": None, "error": True, "errorText": "Доступ запрещён", "additionalErrors": "s"},
    )

    with pytest.raises(WBAccessDeniedError) as exc:
        await make_client().request(PING[Category.CONTENT])

    assert exc.value.detail == "Доступ запрещён (s)"


async def test_long_error_text_is_truncated(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(SELLER_INFO_URL).respond(400, json={"detail": "x" * 5_000})

    with pytest.raises(WBBadRequestError) as exc:
        await make_client().request(SELLER_INFO)

    assert exc.value.detail is not None
    assert len(exc.value.detail) <= 301


@pytest.mark.parametrize("body", [b"<html>oops</html>", b"{broken json"])
async def test_non_json_success_body(
    make_client: ClientFactory, respx_mock: respx.MockRouter, body: bytes
) -> None:
    respx_mock.get(SELLER_INFO_URL).respond(200, content=body)

    with pytest.raises(WBInvalidResponseError, match="не JSON"):
        await make_client().request(SELLER_INFO)


@pytest.mark.parametrize("body", [{"sid": SELLER_ID}, [], None, "text"])
async def test_unexpected_schema(
    make_client: ClientFactory, respx_mock: respx.MockRouter, body: object
) -> None:
    respx_mock.get(SELLER_INFO_URL).respond(200, json=body)

    with pytest.raises(WBInvalidResponseError):
        await GeneralAPI(make_client()).seller_info()


async def test_extra_fields_are_ignored(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(SELLER_INFO_URL).respond(200, json={**SELLER_BODY, "newField": [1, 2]})

    info = await GeneralAPI(make_client()).seller_info()

    assert info.sid == SELLER_ID


# ── лимиты и очередь ──────────────────────────────────────────────────────────


async def test_queue_follows_documented_limit(
    make_client: ClientFactory, respx_mock: respx.MockRouter, clock: FakeClock
) -> None:
    # seller-info, персональный токен: 1 запрос в минуту, всплеск 10.
    respx_mock.get(SELLER_INFO_URL).respond(200, json=SELLER_BODY)
    client = make_client()

    for _ in range(12):
        await client.request(SELLER_INFO)

    assert clock.sleeps == [pytest.approx(60), pytest.approx(60)]


async def test_base_token_uses_its_own_limit(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    # seller-info, базовый токен: 1 запрос в сутки — второй сразу отклоняется, а не ждёт сутки.
    respx_mock.get(SELLER_INFO_URL).respond(200, json=SELLER_BODY)
    client = make_client(personal_token(acc=1))

    await client.request(SELLER_INFO)
    with pytest.raises(WBRateLimitError) as exc:
        await client.request(SELLER_INFO)

    assert exc.value.retry_after == pytest.approx(86_400)


async def test_remaining_header_tightens_queue(
    make_client: ClientFactory, respx_mock: respx.MockRouter, clock: FakeClock
) -> None:
    respx_mock.get(SELLER_INFO_URL).side_effect = [
        httpx.Response(400, headers={"X-Ratelimit-Remaining": "0"}),
        httpx.Response(200, json=SELLER_BODY),
    ]
    client = make_client()

    with pytest.raises(WBBadRequestError):
        await client.request(SELLER_INFO)
    await client.request(SELLER_INFO)

    assert clock.sleeps == [pytest.approx(60)]


async def test_concurrent_requests_wait_in_line(
    make_client: ClientFactory, respx_mock: respx.MockRouter, clock: FakeClock
) -> None:
    # рейтинг: 1 запрос в минуту, всплеск 1.
    respx_mock.get(RATING_URL).respond(200, json={"feedbackCount": 12355, "valuation": 4.55})
    api = GeneralAPI(make_client())

    results = await asyncio.gather(*(api.seller_rating() for _ in range(3)))

    assert [r.valuation for r in results] == [4.55, 4.55, 4.55]
    assert sorted(clock.sleeps) == [pytest.approx(60), pytest.approx(120)]


async def test_clients_of_one_seller_share_limits(
    make_client: ClientFactory, respx_mock: respx.MockRouter, clock: FakeClock
) -> None:
    respx_mock.get(RATING_URL).respond(200, json={"feedbackCount": 1, "valuation": 5})
    token = personal_token()

    await make_client(token).request(SELLER_RATING)
    await make_client(token).request(SELLER_RATING)

    assert clock.sleeps == [pytest.approx(60)]


async def test_ping_limits_are_per_host(
    make_client: ClientFactory, respx_mock: respx.MockRouter, clock: FakeClock
) -> None:
    # /ping: всплеск 99, затем 1 запрос в 10 с — отдельно для каждого хоста.
    respx_mock.get(url__regex=r"https://.*\.wildberries\.ru/ping").respond(200, json=PING_BODY)
    api = GeneralAPI(make_client())

    for _ in range(99):
        await api.ping(Category.CONTENT)
    await api.ping(Category.STATISTICS)
    assert clock.sleeps == []

    await api.ping(Category.CONTENT)
    assert clock.sleeps == [pytest.approx(10)]


# ── только чтение ─────────────────────────────────────────────────────────────


async def test_unregistered_endpoint_is_blocked(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    evil = Endpoint(
        name="content.delete_cards",
        category=Category.CONTENT,
        method="POST",
        path="/content/v2/cards/delete/trash",
        limits={None: RateLimit(period_s=60, limit=100, interval_s=0.6, burst=5)},
        read_only_post=True,
    )

    with pytest.raises(WBForbiddenMethodError):
        await make_client().request(evil)


async def test_copy_of_registered_endpoint_is_blocked(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    forged = dataclasses.replace(SELLER_INFO, path="/api/v1/other")

    with pytest.raises(WBForbiddenMethodError):
        await make_client().request(forged)


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("DELETE", SELLER_INFO_URL),
        ("PUT", SELLER_INFO_URL),
        ("PATCH", SELLER_INFO_URL),
        ("POST", SELLER_INFO_URL),
        ("GET", "https://common-api.wildberries.ru/api/v1/invite"),
        ("GET", "https://evil.example.com/api/v1/seller-info"),
        ("GET", "http://common-api.wildberries.ru/api/v1/seller-info"),
    ],
)
async def test_transport_guard_blocks_requests_outside_whitelist(
    make_client: ClientFactory, respx_mock: respx.MockRouter, method: str, url: str
) -> None:
    client = make_client()

    with pytest.raises(WBForbiddenMethodError):
        await client._http.request(method, url)


async def test_get_with_body_is_rejected(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    with pytest.raises(ValueError, match="тела"):
        await make_client().request(SELLER_INFO, json={"x": 1})


# ── токен не попадает в логи ──────────────────────────────────────────────────


async def test_token_never_appears_in_logs_or_errors(
    make_client: ClientFactory, respx_mock: respx.MockRouter, caplog: pytest.LogCaptureFixture
) -> None:
    token = personal_token()
    route = respx_mock.get(SELLER_INFO_URL)
    route.side_effect = [
        httpx.Response(429, headers={"X-Ratelimit-Retry": "1"}),
        httpx.Response(503),
        httpx.ConnectTimeout("timed out"),
        httpx.Response(200, json=SELLER_BODY),
        httpx.Response(401, json={"title": "unauthorized", "detail": "bad token"}),
    ]
    client = make_client(token, max_retries=3)
    errors: list[WBError] = []

    with caplog.at_level(logging.DEBUG):
        await client.request(SELLER_INFO)
        try:
            await client.request(SELLER_INFO)
        except WBError as exc:
            errors.append(exc)

    assert len(errors) == 1
    assert caplog.text
    assert token not in caplog.text
    assert token not in str(errors[0])
    assert token not in repr(client)
    assert client.token_info.fingerprint in caplog.text

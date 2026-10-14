from __future__ import annotations

import respx

from tests.conftest import ClientFactory
from wbm.wb_client.api.general import GeneralAPI
from wbm.wb_client.categories import Category


async def test_ping(make_client: ClientFactory, respx_mock: respx.MockRouter) -> None:
    respx_mock.get("https://finance-api.wildberries.ru/ping").respond(
        200, json={"TS": "2024-08-16T11:19:05+03:00", "Status": "OK"}
    )

    result = await GeneralAPI(make_client()).ping(Category.FINANCE)

    assert result.status == "OK"
    assert result.ts == "2024-08-16T11:19:05+03:00"


async def test_seller_rating(make_client: ClientFactory, respx_mock: respx.MockRouter) -> None:
    respx_mock.get("https://feedbacks-api.wildberries.ru/api/common/v1/rating").respond(
        200, json={"feedbackCount": 12355, "valuation": 4.55}
    )

    rating = await GeneralAPI(make_client()).seller_rating()

    assert rating.feedback_count == 12355
    assert rating.valuation == 4.55


async def test_seller_info_optional_fields(
    make_client: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get("https://common-api.wildberries.ru/api/v1/seller-info").respond(
        200, json={"name": "ООО Ромашка", "sid": "abc"}
    )

    info = await GeneralAPI(make_client()).seller_info()

    assert info.tin is None
    assert info.trade_mark is None

"""Раздел «Общее»: проверка подключения, информация и рейтинг продавца."""

from __future__ import annotations

from pydantic import Field

from wbm.wb_client.api._base import WBModel, parse_model
from wbm.wb_client.categories import Category
from wbm.wb_client.client import WBClient
from wbm.wb_client.endpoints import PING, SELLER_INFO, SELLER_RATING


class PingResult(WBModel):
    ts: str | None = Field(default=None, alias="TS")
    status: str = Field(alias="Status")


class SellerInfo(WBModel):
    name: str
    sid: str
    tin: str | None = None
    trade_mark: str | None = Field(default=None, alias="tradeMark")


class SellerRating(WBModel):
    feedback_count: int = Field(alias="feedbackCount")
    valuation: float


class GeneralAPI:
    def __init__(self, client: WBClient) -> None:
        self._client = client

    async def ping(self, category: Category) -> PingResult:
        """Проверяет токен и его доступ к категории. Лимит: 3 запроса за 30 с на хост."""
        endpoint = PING[category]
        return parse_model(PingResult, await self._client.request(endpoint), endpoint)

    async def seller_info(self) -> SellerInfo:
        """Название продавца и его ID. Для базового токена — 1 запрос в сутки: кэшируйте."""
        data = await self._client.request(SELLER_INFO)
        return parse_model(SellerInfo, data, SELLER_INFO)

    async def seller_rating(self) -> SellerRating:
        """Рейтинг продавца и число отзывов (нужна категория «Отзывы и вопросы»)."""
        data = await self._client.request(SELLER_RATING)
        return parse_model(SellerRating, data, SELLER_RATING)

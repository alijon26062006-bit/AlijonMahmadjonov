"""Категории WB API: хосты (боевой контур и песочница) и биты прав в токене.

Источник: dev.wildberries.ru, раздел «Общее» — метод /ping (список хостов)
и «Поля токенов» (битовая маска `s`).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Category(StrEnum):
    COMMON = "common"
    CONTENT = "content"
    ANALYTICS = "analytics"
    PRICES = "prices"
    MARKETPLACE = "marketplace"
    STATISTICS = "statistics"
    PROMOTION = "promotion"
    FEEDBACKS = "feedbacks"
    BUYER_CHAT = "buyer_chat"
    SUPPLIES = "supplies"
    RETURNS = "returns"
    DOCUMENTS = "documents"
    FINANCE = "finance"
    USERS = "users"


@dataclass(frozen=True, slots=True)
class CategoryInfo:
    title: str
    """Название категории, как при создании токена в личном кабинете WB."""
    prod_host: str
    sandbox_host: str | None
    """None — у категории нет песочницы."""
    scope_bit: int | None
    """Позиция бита в поле `s` токена. None — методы доступны с токеном любой категории."""


CATEGORIES: dict[Category, CategoryInfo] = {
    Category.COMMON: CategoryInfo(
        "Тарифы, новости, информация о продавце", "common-api.wildberries.ru", None, None
    ),
    Category.CONTENT: CategoryInfo(
        "Контент", "content-api.wildberries.ru", "content-api-sandbox.wildberries.ru", 1
    ),
    Category.ANALYTICS: CategoryInfo("Аналитика", "seller-analytics-api.wildberries.ru", None, 2),
    Category.PRICES: CategoryInfo(
        "Цены и скидки",
        "discounts-prices-api.wildberries.ru",
        "discounts-prices-api-sandbox.wildberries.ru",
        3,
    ),
    Category.MARKETPLACE: CategoryInfo(
        "Маркетплейс", "marketplace-api.wildberries.ru", "marketplace-api-sandbox.wildberries.ru", 4
    ),
    Category.STATISTICS: CategoryInfo(
        "Статистика", "statistics-api.wildberries.ru", "statistics-api-sandbox.wildberries.ru", 5
    ),
    Category.PROMOTION: CategoryInfo(
        "Продвижение", "advert-api.wildberries.ru", "advert-api-sandbox.wildberries.ru", 6
    ),
    Category.FEEDBACKS: CategoryInfo(
        "Отзывы и вопросы",
        "feedbacks-api.wildberries.ru",
        "feedbacks-api-sandbox.wildberries.ru",
        7,
    ),
    Category.BUYER_CHAT: CategoryInfo(
        "Чат с покупателями", "buyer-chat-api.wildberries.ru", None, 9
    ),
    Category.SUPPLIES: CategoryInfo("Поставки", "supplies-api.wildberries.ru", None, 10),
    Category.RETURNS: CategoryInfo("Возвраты покупателями", "returns-api.wildberries.ru", None, 11),
    Category.DOCUMENTS: CategoryInfo("Документы", "documents-api.wildberries.ru", None, 12),
    Category.FINANCE: CategoryInfo("Финансы", "finance-api.wildberries.ru", None, 13),
    Category.USERS: CategoryInfo("Пользователи", "user-management-api.wildberries.ru", None, 16),
}

READ_ONLY_BIT = 30
"""Бит «Токен только для чтения» в поле `s`."""


def host_for(category: Category, *, sandbox: bool) -> str | None:
    """Хост категории в нужном контуре. None — в песочнице этой категории нет."""
    info = CATEGORIES[category]
    return info.sandbox_host if sandbox else info.prod_host

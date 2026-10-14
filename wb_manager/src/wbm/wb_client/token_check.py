"""Проверка токена при подключении магазина.

Доступ к категориям подтверждаем ответом WB на /ping (а не только расшифровкой токена):
так проверка не зависит от трактовки битовой маски и сразу ловит неверный токен.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from wbm.wb_client.api.general import GeneralAPI
from wbm.wb_client.categories import CATEGORIES, Category
from wbm.wb_client.client import WBClient
from wbm.wb_client.errors import (
    WBAccessDeniedError,
    WBError,
    WBSandboxUnavailableError,
    WBUnauthorizedError,
)
from wbm.wb_client.token import TokenInfo, TokenKind

logger = logging.getLogger(__name__)

EXPIRY_WARNING_PERIOD = timedelta(days=14)


class CategoryStatus(StrEnum):
    OK = "ok"
    UNAUTHORIZED = "unauthorized"
    DENIED = "denied"
    SANDBOX_UNAVAILABLE = "sandbox_unavailable"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class CategoryCheck:
    category: Category
    status: CategoryStatus
    message: str


@dataclass(frozen=True, slots=True)
class TokenCheckResult:
    token: TokenInfo
    valid: bool
    """False — WB не принял токен (неверный, просрочен, удалён)."""
    categories: tuple[CategoryCheck, ...]
    warnings: tuple[str, ...]

    @property
    def available(self) -> frozenset[Category]:
        return frozenset(c.category for c in self.categories if c.status is CategoryStatus.OK)


async def check_token(
    client: WBClient, categories: Iterable[Category], *, now: datetime | None = None
) -> TokenCheckResult:
    """Пингует каждую нужную категорию и собирает понятные предупреждения."""
    now = now or datetime.now(UTC)
    info = client.token_info
    if info.is_expired(now):
        return TokenCheckResult(
            info, False, (), ("Срок действия токена истёк — создайте новый токен в кабинете WB",)
        )

    api = GeneralAPI(client)
    checks = tuple(
        await asyncio.gather(*(_check_category(api, c) for c in dict.fromkeys(categories)))
    )
    valid = all(c.status is not CategoryStatus.UNAUTHORIZED for c in checks)
    _log_scope_mismatch(client, checks)
    return TokenCheckResult(info, valid, checks, _warnings(info, valid, now))


async def _check_category(api: GeneralAPI, category: Category) -> CategoryCheck:
    title = CATEGORIES[category].title
    try:
        result = await api.ping(category)
    except WBUnauthorizedError:
        return CategoryCheck(
            category, CategoryStatus.UNAUTHORIZED, "WB не принял токен: неверный или просрочен"
        )
    except WBAccessDeniedError:
        return CategoryCheck(category, CategoryStatus.DENIED, f"В токене нет категории «{title}»")
    except WBSandboxUnavailableError:
        return CategoryCheck(
            category, CategoryStatus.SANDBOX_UNAVAILABLE, f"У категории «{title}» нет песочницы"
        )
    except WBError as exc:
        return CategoryCheck(
            category, CategoryStatus.ERROR, f"Не удалось проверить «{title}»: {exc}"
        )
    if result.status != "OK":
        return CategoryCheck(
            category, CategoryStatus.ERROR, f"WB вернул статус «{result.status}» для «{title}»"
        )
    return CategoryCheck(category, CategoryStatus.OK, f"Доступ к «{title}» есть")


def _warnings(info: TokenInfo, valid: bool, now: datetime) -> tuple[str, ...]:
    warnings: list[str] = []
    if not valid:
        warnings.append("WB не принял токен: он неверный, просрочен или удалён")
    if info.read_only is False:
        warnings.append(
            "Токен разрешает изменения. Для анализа создайте токен с доступом «Только на чтение»"
        )
    elif info.read_only is None:
        warnings.append(
            "Не удалось прочитать права токена — убедитесь, что он создан «Только на чтение»"
        )
    if info.kind is TokenKind.TEST:
        warnings.append("Это тестовый токен: данные из песочницы WB, а не вашего магазина")
    if info.expires_at is not None and info.expires_within(EXPIRY_WARNING_PERIOD, now):
        warnings.append(
            f"Токен перестанет работать {info.expires_at:%d.%m.%Y} — заранее создайте новый"
        )
    return tuple(warnings)


def _log_scope_mismatch(client: WBClient, checks: tuple[CategoryCheck, ...]) -> None:
    """Сравнивает расшифровку маски `s` с ответами WB — так сверяется трактовка битов."""
    declared = client.token_info.categories
    if declared is None:
        return
    for check in checks:
        if CATEGORIES[check.category].scope_bit is None:
            continue
        if check.status not in (CategoryStatus.OK, CategoryStatus.DENIED):
            continue
        if (check.category in declared) != (check.status is CategoryStatus.OK):
            logger.warning(
                "%s: расшифровка прав токена не совпала с ответом WB для категории %s "
                "(в маске: %s, WB: %s) — проверьте трактовку битов поля s",
                client.log_name,
                check.category.value,
                check.category in declared,
                check.status.value,
            )

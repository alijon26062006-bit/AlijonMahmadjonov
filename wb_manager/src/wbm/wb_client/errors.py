"""Ошибки клиента WB. Ни в одном сообщении нет токена."""

from __future__ import annotations


class WBError(Exception):
    """Базовая ошибка работы с WB API."""


class WBConfigError(WBError):
    """Неверная настройка: например, тестовый токен для боевого контура."""


class WBTokenFormatError(WBConfigError):
    """Строка не похожа на токен WB (пустая, с пробелами, недопустимые символы)."""


class WBForbiddenMethodError(WBError):
    """Попытка вызвать метод вне белого списка «только чтение». Запрос не отправлен."""


class WBSandboxUnavailableError(WBError):
    """У категории нет песочницы — в тестовом контуре этих данных нет."""


class WBNetworkError(WBError):
    """Таймаут или сбой соединения после всех повторов."""


class WBRateLimitError(WBError):
    """Лимит запросов WB: ответ 429 после всех повторов или слишком долгое ожидание очереди."""

    def __init__(self, message: str, *, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class WBInvalidResponseError(WBError):
    """Ответ WB не JSON или не совпадает с ожидаемой схемой."""


class WBHTTPError(WBError):
    """WB ответил кодом ошибки."""

    def __init__(
        self,
        message: str,
        *,
        status: int,
        endpoint: str,
        title: str | None = None,
        detail: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.endpoint = endpoint
        self.title = title
        self.detail = detail
        self.request_id = request_id


class WBBadRequestError(WBHTTPError):
    """400, 409, 413, 422 — WB не принял параметры запроса."""


class WBUnauthorizedError(WBHTTPError):
    """401 — токен неверный, просрочен или не передан."""


class WBPaymentRequiredError(WBHTTPError):
    """402 — у сервиса из каталога WB недостаточно средств на балансе."""


class WBAccessDeniedError(WBHTTPError):
    """403 — у токена нет нужной категории, метод недоступен для типа токена или заблокирован."""


class WBNotFoundError(WBHTTPError):
    """404 — неверный адрес метода."""


class WBServerError(WBHTTPError):
    """5xx после всех повторов — сервис WB недоступен."""

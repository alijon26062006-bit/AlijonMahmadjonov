"""Клиент WB API — единственная точка, через которую приложение ходит в Wildberries.

Что делает:
- подставляет токен в заголовок Authorization (как требует документация);
- пускает только методы из белого списка «только чтение» (endpoints.py), причём
  проверяет дважды: до сборки запроса и на уровне HTTP-транспорта;
- соблюдает лимиты WB: очередь по bucket'ам, подстройка под X-Ratelimit-Remaining;
- повторяет запрос при 429 (ждёт X-Ratelimit-Retry), 5xx и сбоях сети;
- пишет понятные логи без токена.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable, Mapping
from types import TracebackType
from typing import Self

import httpx
from pydantic import SecretStr

from wbm import __version__
from wbm.config import WBSettings
from wbm.wb_client.categories import CATEGORIES, host_for
from wbm.wb_client.endpoints import Endpoint, is_allowed_request, is_registered
from wbm.wb_client.errors import (
    WBAccessDeniedError,
    WBBadRequestError,
    WBConfigError,
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
from wbm.wb_client.ratelimit import (
    DEFAULT_REGISTRY,
    GCRALimiter,
    RateLimiterRegistry,
    RateLimitWaitTooLong,
)
from wbm.wb_client.token import TokenInfo, inspect_token, normalize_token

logger = logging.getLogger(__name__)

QueryValue = str | int | float | bool
Sleep = Callable[[float], Awaitable[None]]

_MAX_ERROR_TEXT = 300
_STATUS_ERRORS: dict[int, type[WBHTTPError]] = {
    400: WBBadRequestError,
    401: WBUnauthorizedError,
    402: WBPaymentRequiredError,
    403: WBAccessDeniedError,
    404: WBNotFoundError,
    409: WBBadRequestError,
    413: WBBadRequestError,
    422: WBBadRequestError,
}


class WBClient:
    """Клиент одного токена (одного магазина). Использовать как `async with WBClient(...)`."""

    def __init__(
        self,
        token: str,
        settings: WBSettings,
        *,
        limiters: RateLimiterRegistry | None = None,
        sleep: Sleep = asyncio.sleep,
        rng: random.Random | None = None,
        max_wait: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        log_name: str | None = None,
    ) -> None:
        normalized = normalize_token(token)
        self._token = SecretStr(normalized)
        self.token_info: TokenInfo = inspect_token(normalized)
        self.sandbox = settings.sandbox
        self.log_name = log_name or f"токен {self.token_info.fingerprint}"
        self._settings = settings
        self._limiters = limiters or DEFAULT_REGISTRY
        self._sleep = sleep
        self._rng = rng or random.Random()  # noqa: S311 — разброс пауз, не криптография
        self._max_wait = settings.max_wait if max_wait is None else max_wait
        # Лимиты WB считаются на аккаунт продавца: ключ — ID продавца из токена.
        self._account = self.token_info.seller_id or self.token_info.fingerprint
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)
        self._check_contour()
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.timeout_read, connect=settings.timeout_connect),
            follow_redirects=False,
            headers={"User-Agent": f"wbm/{__version__}"},
            event_hooks={"request": [self._guard_request]},
            transport=transport,
        )

    def __repr__(self) -> str:
        return f"WBClient({self.log_name}, sandbox={self.sandbox})"

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    async def sleep(self, seconds: float) -> None:
        """Пауза между опросами асинхронного отчёта (в тестах — управляемые часы)."""
        await self._sleep(seconds)

    async def request(
        self,
        endpoint: Endpoint,
        *,
        params: Mapping[str, QueryValue] | None = None,
        json: object | None = None,
        path_params: Mapping[str, str | int] | None = None,
    ) -> object:
        """Выполняет метод из белого списка и возвращает разобранный JSON (None для 204)."""
        self._ensure_allowed(endpoint)
        if json is not None and endpoint.method == "GET":
            raise ValueError(f"{endpoint.name}: у GET-запроса не бывает тела")
        host = host_for(endpoint.category, sandbox=self.sandbox)
        if host is None:
            title = CATEGORIES[endpoint.category].title
            raise WBSandboxUnavailableError(f"У категории «{title}» нет песочницы WB")
        url = f"https://{host}{endpoint.build_path(path_params)}"
        limiter = self._limiter_for(endpoint)

        errors_left = self._settings.max_retries
        rate_limits_left = self._settings.max_rate_limit_retries
        attempt = 0
        while True:
            attempt += 1
            await self._wait_turn(limiter, endpoint)
            started = time.monotonic()
            try:
                async with self._semaphore:
                    response = await self._http.request(
                        endpoint.method,
                        url,
                        params=dict(params) if params else None,
                        json=json,
                        headers={"Authorization": self._token.get_secret_value()},
                    )
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if errors_left == 0:
                    raise WBNetworkError(
                        f"{endpoint.name}: нет ответа от WB ({type(exc).__name__}), "
                        f"попыток: {attempt}"
                    ) from exc
                errors_left -= 1
                delay = self._backoff(attempt)
                logger.warning(
                    "%s: сбой сети при запросе %s (%s), повтор через %.1f с",
                    self.log_name,
                    endpoint.name,
                    type(exc).__name__,
                    delay,
                )
                await self._sleep(delay)
                continue

            elapsed_ms = (time.monotonic() - started) * 1000
            status = response.status_code
            self._sync_limiter(limiter, response)

            if status == 429:
                retry_after = _float_header(response, "X-Ratelimit-Retry")
                delay = retry_after if retry_after is not None else self._backoff(attempt)
                limiter.block(delay)
                if rate_limits_left == 0:
                    raise WBRateLimitError(
                        f"{endpoint.name}: WB ответил 429 «слишком много запросов», "
                        f"попыток: {attempt}",
                        retry_after=delay,
                    )
                rate_limits_left -= 1
                logger.warning(
                    "%s: WB ответил 429 на %s — ждём %.1f с и повторяем",
                    self.log_name,
                    endpoint.name,
                    delay,
                )
                continue  # следующая бронь в очереди сама дождётся конца паузы

            if status >= 500:
                if errors_left == 0:
                    raise self._http_error(WBServerError, endpoint, response)
                errors_left -= 1
                delay = self._backoff(attempt)
                logger.warning(
                    "%s: WB ответил %d на %s — повтор через %.1f с",
                    self.log_name,
                    status,
                    endpoint.name,
                    delay,
                )
                await self._sleep(delay)
                continue

            if status >= 300:
                raise self._http_error(_STATUS_ERRORS.get(status, WBHTTPError), endpoint, response)

            logger.info(
                "%s: WB %s %s → %d за %.0f мс",
                self.log_name,
                endpoint.method,
                endpoint.name,
                status,
                elapsed_ms,
            )
            return _parse_body(endpoint, response)

    # ── проверки ──────────────────────────────────────────────────────────────

    def _check_contour(self) -> None:
        if self.token_info.is_test and not self.sandbox:
            raise WBConfigError(
                "Тестовый токен работает только в песочнице WB: "
                "включите WB_SANDBOX=true или подключите боевой токен"
            )
        if self.sandbox and self.token_info.is_test is False:
            logger.warning(
                "%s: включена песочница, но токен не тестовый — WB может его не принять",
                self.log_name,
            )

    @staticmethod
    def _ensure_allowed(endpoint: Endpoint) -> None:
        if not is_registered(endpoint):
            raise WBForbiddenMethodError(f"Метод {endpoint.name} не входит в белый список")
        if endpoint.method != "GET" and not endpoint.read_only_post:
            raise WBForbiddenMethodError(f"{endpoint.name}: в v1 разрешено только чтение")

    async def _guard_request(self, request: httpx.Request) -> None:
        url = request.url
        if url.scheme != "https" or not is_allowed_request(
            request.method, url.host, url.path, sandbox=self.sandbox
        ):
            logger.error(
                "%s: заблокирован запрос вне белого списка: %s %s%s",
                self.log_name,
                request.method,
                url.host,
                url.path,
            )
            raise WBForbiddenMethodError(
                f"Запрос {request.method} {url.host}{url.path} не входит в белый список"
            )

    # ── лимиты и паузы ────────────────────────────────────────────────────────

    def _limiter_for(self, endpoint: Endpoint) -> GCRALimiter:
        kind = self.token_info.kind
        limit = endpoint.limit_for(kind, sandbox=self.sandbox)
        group = f"{endpoint.group}:{'sandbox' if self.sandbox else 'prod'}"
        return self._limiters.get(self._account, group, kind.name if kind else "unknown", limit)

    async def _wait_turn(self, limiter: GCRALimiter, endpoint: Endpoint) -> None:
        try:
            wait = limiter.reserve(self._max_wait)
        except RateLimitWaitTooLong as exc:
            raise WBRateLimitError(
                f"{endpoint.name}: по лимитам WB ждать {exc.wait:.0f} с — "
                f"дольше допустимых {self._max_wait:.0f} с",
                retry_after=exc.wait,
            ) from None
        if wait > 0:
            if wait >= 1:
                logger.info(
                    "%s: очередь WB — %s ждёт %.1f с из-за лимита",
                    self.log_name,
                    endpoint.name,
                    wait,
                )
            await self._sleep(wait)

    @staticmethod
    def _sync_limiter(limiter: GCRALimiter, response: httpx.Response) -> None:
        remaining = response.headers.get("X-Ratelimit-Remaining")
        if remaining is not None and remaining.strip().isdigit():
            limiter.sync_remaining(int(remaining))

    def _backoff(self, attempt: int) -> float:
        base = self._settings.backoff_base * 2 ** (attempt - 1)
        delay = base + self._rng.uniform(0, base * 0.1)
        return float(min(self._settings.backoff_max, delay))

    def _http_error(
        self, error_cls: type[WBHTTPError], endpoint: Endpoint, response: httpx.Response
    ) -> WBHTTPError:
        title, detail, request_id = _parse_error_body(response)
        message = " — ".join(
            part
            for part in (f"{endpoint.name}: WB ответил HTTP {response.status_code}", title, detail)
            if part
        )
        logger.warning(
            "%s: %s%s", self.log_name, message, f" (requestId {request_id})" if request_id else ""
        )
        return error_cls(
            message,
            status=response.status_code,
            endpoint=endpoint.name,
            title=title,
            detail=detail,
            request_id=request_id,
        )


def _parse_body(endpoint: Endpoint, response: httpx.Response) -> object:
    if response.status_code == 204 or not response.content:
        return None
    try:
        data: object = response.json()
    except ValueError:
        raise WBInvalidResponseError(
            f"{endpoint.name}: ответ WB не JSON (HTTP {response.status_code})"
        ) from None
    return data


def _parse_error_body(response: httpx.Response) -> tuple[str | None, str | None, str | None]:
    """Форматы ошибок WB: {title, detail, requestId, …} и {error, errorText, additionalErrors}."""
    try:
        data = response.json()
    except ValueError:
        return None, None, None
    if not isinstance(data, dict):
        return None, None, None
    title = _short_text(data.get("title"))
    detail = _short_text(data.get("detail")) or _short_text(data.get("errorText"))
    additional = _short_text(data.get("additionalErrors"))
    if additional:
        detail = f"{detail} ({additional})" if detail else additional
    return title, detail, _short_text(data.get("requestId"))


def _short_text(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    return text if len(text) <= _MAX_ERROR_TEXT else text[:_MAX_ERROR_TEXT] + "…"


def _float_header(response: httpx.Response, name: str) -> float | None:
    raw = response.headers.get(name)
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value >= 0 else None

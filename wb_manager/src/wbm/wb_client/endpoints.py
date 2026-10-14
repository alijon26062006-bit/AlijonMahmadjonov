"""Белый список методов WB. Клиент вызывает только то, что описано здесь.

Правила v1 (только чтение):
- разрешены GET-методы;
- POST — только если по документации метод лишь читает данные (read_only_post=True);
- PUT, PATCH, DELETE запрещены всегда.

Каждый метод добавляется сюда только после сверки с dev.wildberries.ru,
лимиты переписаны из документации метода (docs/WB_API.md).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import quote

from wbm.wb_client.categories import Category, host_for
from wbm.wb_client.ratelimit import RateLimit
from wbm.wb_client.token import TokenKind

HttpMethod = Literal["GET", "POST"]
_PATH_PARAM_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


@dataclass(frozen=True, slots=True)
class Endpoint:
    name: str
    category: Category
    method: HttpMethod
    path: str
    limits: Mapping[TokenKind | None, RateLimit]
    """Лимиты по типу токена; ключ None — для любого типа."""
    limit_group: str | None = None
    """Общий bucket для нескольких методов (например, «вся категория Контент»). None — свой."""
    sandbox_limits: Mapping[TokenKind | None, RateLimit] | None = None
    read_only_post: bool = False
    doc: str = ""
    _path_re: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # split с группой даёт: чётные элементы — текст пути, нечётные — имена параметров.
        pieces = _PATH_PARAM_RE.split(self.path)
        pattern = "".join(
            re.escape(piece) if index % 2 == 0 else "[^/]+" for index, piece in enumerate(pieces)
        )
        object.__setattr__(self, "_path_re", re.compile(f"^{pattern}$"))

    @property
    def group(self) -> str:
        return self.limit_group or self.name

    def limit_for(self, kind: TokenKind | None, *, sandbox: bool) -> RateLimit:
        """Лимит для типа токена. Если тип не описан — самый строгий из описанных."""
        table = self.sandbox_limits if sandbox and self.sandbox_limits else self.limits
        if kind is not None and kind in table:
            return table[kind]
        if None in table:
            return table[None]
        return max(table.values(), key=lambda limit: limit.interval_s)

    def build_path(self, path_params: Mapping[str, str | int] | None = None) -> str:
        names = _PATH_PARAM_RE.findall(self.path)
        params = dict(path_params or {})
        if set(names) != set(params):
            raise ValueError(
                f"{self.name}: нужны параметры пути {sorted(names)}, переданы {sorted(params)}"
            )
        return _PATH_PARAM_RE.sub(lambda m: quote(str(params[m.group(1)]), safe=""), self.path)

    def matches_path(self, path: str) -> bool:
        return bool(self._path_re.match(path))


# ── Общее ─────────────────────────────────────────────────────────────────────

# /ping: 3 запроса за 30 с, интервал 10 с, всплеск 99; лимит у каждого хоста свой.
_PING_LIMIT = RateLimit(period_s=30, limit=3, interval_s=10, burst=99)

PING: dict[Category, Endpoint] = {
    category: Endpoint(
        name=f"ping.{category.value}",
        category=category,
        method="GET",
        path="/ping",
        limits={None: _PING_LIMIT},
        doc="Общее → Проверка подключения к WB API",
    )
    for category in Category
}

SELLER_INFO = Endpoint(
    name="general.seller_info",
    category=Category.COMMON,
    method="GET",
    path="/api/v1/seller-info",
    limits={
        TokenKind.PERSONAL: RateLimit(period_s=60, limit=1, interval_s=60, burst=10),
        TokenKind.SERVICE: RateLimit(period_s=60, limit=1, interval_s=60, burst=10),
        TokenKind.BASE: RateLimit(period_s=86_400, limit=1, interval_s=86_400, burst=1),
    },
    doc="Общее → Информация о продавце → Получить информацию о продавце",
)

SELLER_RATING = Endpoint(
    name="general.seller_rating",
    category=Category.FEEDBACKS,
    method="GET",
    path="/api/common/v1/rating",
    limits={None: RateLimit(period_s=60, limit=1, interval_s=60, burst=1)},
    doc="Общее → Информация о продавце → Получить рейтинг продавца",
)


def _build_registry(*endpoints: Endpoint) -> dict[str, Endpoint]:
    registry: dict[str, Endpoint] = {}
    for endpoint in endpoints:
        if endpoint.name in registry:
            raise RuntimeError(f"Метод {endpoint.name} описан дважды")
        if endpoint.method != "GET" and not endpoint.read_only_post:
            raise RuntimeError(f"{endpoint.name}: в v1 разрешено только чтение")
        if not endpoint.path.startswith("/"):
            raise RuntimeError(f"{endpoint.name}: путь должен начинаться с /")
        registry[endpoint.name] = endpoint
    return registry


ENDPOINTS: dict[str, Endpoint] = _build_registry(*PING.values(), SELLER_INFO, SELLER_RATING)


def is_registered(endpoint: Endpoint) -> bool:
    return ENDPOINTS.get(endpoint.name) is endpoint


def is_allowed_request(method: str, host: str, path: str, *, sandbox: bool) -> bool:
    """Проверка уже собранного HTTP-запроса — вторая линия защиты на уровне транспорта."""
    for endpoint in ENDPOINTS.values():
        if (
            endpoint.method == method.upper()
            and host_for(endpoint.category, sandbox=sandbox) == host
            and endpoint.matches_path(path)
        ):
            return True
    return False

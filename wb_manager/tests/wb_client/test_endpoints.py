from __future__ import annotations

import pytest

from wbm.wb_client.categories import CATEGORIES, Category
from wbm.wb_client.endpoints import (
    ENDPOINTS,
    PING,
    SELLER_INFO,
    SELLER_RATING,
    Endpoint,
    _build_registry,
    is_allowed_request,
    is_registered,
)
from wbm.wb_client.ratelimit import RateLimit
from wbm.wb_client.token import TokenKind

ANY_LIMIT: dict[TokenKind | None, RateLimit] = {
    None: RateLimit(period_s=60, limit=1, interval_s=60, burst=1)
}


def test_whitelist_is_read_only() -> None:
    for endpoint in ENDPOINTS.values():
        assert endpoint.method in {"GET", "POST"}, endpoint.name
        if endpoint.method == "POST":
            assert endpoint.read_only_post, endpoint.name


def test_every_category_has_ping() -> None:
    assert set(PING) == set(Category)
    assert all(endpoint.path == "/ping" for endpoint in PING.values())
    assert all(is_registered(endpoint) for endpoint in PING.values())


def test_registry_rejects_write_method() -> None:
    write = Endpoint(
        name="x.write", category=Category.CONTENT, method="POST", path="/x", limits=ANY_LIMIT
    )

    with pytest.raises(RuntimeError, match="только чтение"):
        _build_registry(write)


def test_registry_rejects_duplicates_and_bad_paths() -> None:
    with pytest.raises(RuntimeError, match="дважды"):
        _build_registry(SELLER_INFO, SELLER_INFO)
    with pytest.raises(RuntimeError, match="/"):
        _build_registry(
            Endpoint(name="x", category=Category.CONTENT, method="GET", path="x", limits=ANY_LIMIT)
        )


@pytest.mark.parametrize(
    ("method", "host", "path", "sandbox", "allowed"),
    [
        ("GET", "common-api.wildberries.ru", "/api/v1/seller-info", False, True),
        ("get", "common-api.wildberries.ru", "/api/v1/seller-info", False, True),
        ("DELETE", "common-api.wildberries.ru", "/api/v1/seller-info", False, False),
        ("GET", "common-api.wildberries.ru", "/api/v1/seller-info/x", False, False),
        ("GET", "feedbacks-api.wildberries.ru", "/api/v1/seller-info", False, False),
        ("GET", "content-api-sandbox.wildberries.ru", "/ping", True, True),
        ("GET", "content-api.wildberries.ru", "/ping", True, False),
        ("GET", "content-api-sandbox.wildberries.ru", "/ping", False, False),
        ("GET", "finance-api.wildberries.ru", "/ping", False, True),
    ],
)
def test_is_allowed_request(
    method: str, host: str, path: str, sandbox: bool, allowed: bool
) -> None:
    assert is_allowed_request(method, host, path, sandbox=sandbox) is allowed


def test_path_params_are_quoted_and_checked() -> None:
    endpoint = Endpoint(
        name="x", category=Category.CONTENT, method="GET", path="/a/{id}/b", limits=ANY_LIMIT
    )

    assert endpoint.build_path({"id": "1/2 3"}) == "/a/1%2F2%203/b"
    assert endpoint.matches_path("/a/42/b")
    assert not endpoint.matches_path("/a/42/c")
    assert not endpoint.matches_path("/a/b")
    with pytest.raises(ValueError, match="параметры пути"):
        endpoint.build_path({})


def test_limit_for_token_kind() -> None:
    personal = SELLER_INFO.limit_for(TokenKind.PERSONAL, sandbox=False)
    base = SELLER_INFO.limit_for(TokenKind.BASE, sandbox=False)

    assert (personal.interval_s, personal.burst) == (60, 10)
    assert (base.interval_s, base.burst) == (86_400, 1)
    # Для типа, которого нет в документации метода, — самый строгий лимит.
    assert SELLER_INFO.limit_for(TokenKind.TEST, sandbox=False) == base
    assert SELLER_INFO.limit_for(None, sandbox=False) == base
    assert SELLER_RATING.limit_for(TokenKind.SERVICE, sandbox=False).interval_s == 60


def test_sandbox_limits_override() -> None:
    sandbox_limit = RateLimit(period_s=1, limit=1, interval_s=1, burst=1)
    endpoint = Endpoint(
        name="x",
        category=Category.CONTENT,
        method="GET",
        path="/x",
        limits={None: RateLimit(period_s=60, limit=100, interval_s=0.6, burst=5)},
        sandbox_limits={None: sandbox_limit},
    )

    assert endpoint.limit_for(TokenKind.TEST, sandbox=True) == sandbox_limit
    assert endpoint.limit_for(TokenKind.TEST, sandbox=False).burst == 5


def test_categories_hosts_are_wildberries() -> None:
    for info in CATEGORIES.values():
        assert info.prod_host.endswith(".wildberries.ru")
        if info.sandbox_host is not None:
            assert info.sandbox_host.endswith("-sandbox.wildberries.ru")

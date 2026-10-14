"""Единственная точка доступа к Wildberries API (v1 — только чтение)."""

from wbm.wb_client.categories import CATEGORIES, Category
from wbm.wb_client.client import WBClient
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
    WBTokenFormatError,
    WBUnauthorizedError,
)
from wbm.wb_client.token import TokenInfo, TokenKind, inspect_token, normalize_token

__all__ = [
    "CATEGORIES",
    "Category",
    "TokenInfo",
    "TokenKind",
    "WBAccessDeniedError",
    "WBBadRequestError",
    "WBClient",
    "WBConfigError",
    "WBError",
    "WBForbiddenMethodError",
    "WBHTTPError",
    "WBInvalidResponseError",
    "WBNetworkError",
    "WBNotFoundError",
    "WBPaymentRequiredError",
    "WBRateLimitError",
    "WBSandboxUnavailableError",
    "WBServerError",
    "WBTokenFormatError",
    "WBUnauthorizedError",
    "inspect_token",
    "normalize_token",
]

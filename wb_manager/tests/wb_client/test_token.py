from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tests.helpers import SELLER_ID, make_jwt, personal_token, scopes
from wbm.wb_client.categories import Category
from wbm.wb_client.errors import WBTokenFormatError
from wbm.wb_client.token import TokenKind, inspect_token, normalize_token, token_fingerprint


def test_personal_token_is_decoded() -> None:
    info = inspect_token(personal_token())

    assert info.decoded
    assert info.kind is TokenKind.PERSONAL
    assert info.is_test is False
    assert info.categories == frozenset({Category.CONTENT, Category.STATISTICS, Category.FEEDBACKS})
    assert info.read_only is True
    assert info.seller_id == SELLER_ID
    assert info.expires_at == datetime(2100, 1, 1, tzinfo=UTC)


def test_test_token_detected_by_acc_and_t() -> None:
    info = inspect_token(make_jwt({"acc": 2, "t": True, "s": scopes(1)}))

    assert info.kind is TokenKind.TEST
    assert info.is_test is True


def test_read_only_bit_absent() -> None:
    info = inspect_token(personal_token(s=scopes(1, 2)))

    assert info.read_only is False
    assert info.categories == frozenset({Category.CONTENT, Category.ANALYTICS})


@pytest.mark.parametrize(
    "token",
    [
        "просто-строка".encode().hex(),
        "aaa.bbb",
        "aaa.!!!.ccc",
        "eyJhbGciOiJFUzI1NiJ9.bm90LWpzb24.sig",  # payload «not-json»
        make_jwt({"acc": 3}).replace(".", "..", 1),
    ],
)
def test_undecodable_token_is_not_an_error(token: str) -> None:
    info = inspect_token(token)

    assert not info.decoded
    assert info.kind is None
    assert info.categories is None
    assert info.read_only is None
    assert info.fingerprint == token_fingerprint(token)


def test_wrong_field_types_are_ignored() -> None:
    info = inspect_token(make_jwt({"acc": "3", "s": True, "t": "yes", "sid": 5, "exp": "soon"}))

    assert info.decoded
    assert info.kind is None
    assert info.categories is None
    assert info.read_only is None
    assert info.is_test is None
    assert info.seller_id is None
    assert info.expires_at is None


def test_unknown_token_kind() -> None:
    assert inspect_token(make_jwt({"acc": 99})).kind is None


def test_expiry_helpers() -> None:
    now = datetime(2026, 10, 14, tzinfo=UTC)
    info = inspect_token(personal_token(exp=int((now + timedelta(days=3)).timestamp())))

    assert not info.is_expired(now)
    assert info.expires_within(timedelta(days=14), now)
    assert info.is_expired(now + timedelta(days=4))


def test_normalize_strips_spaces_and_bearer() -> None:
    token = personal_token()

    assert normalize_token(f"  {token}\n") == token
    assert normalize_token(f"Bearer {token}") == token


@pytest.mark.parametrize("raw", ["", "   ", "abc def", "abc\ndef", "токен"])
def test_normalize_rejects_bad_input(raw: str) -> None:
    with pytest.raises(WBTokenFormatError):
        normalize_token(raw)


def test_token_info_does_not_hold_token() -> None:
    token = personal_token()
    info = inspect_token(token)

    assert token not in repr(info)
    assert len(info.fingerprint) == 12
    assert info.fingerprint not in token

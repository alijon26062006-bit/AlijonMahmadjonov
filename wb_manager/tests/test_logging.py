from __future__ import annotations

import io
import logging
from collections.abc import Iterator

import pytest

from tests.helpers import personal_token
from wbm.logging_setup import REDACTED, SecretRedactingFilter, configure_logging


@pytest.fixture
def capture() -> Iterator[tuple[logging.Logger, io.StringIO, SecretRedactingFilter]]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    redactor = SecretRedactingFilter(["my-anthropic-key-123"])
    handler.addFilter(redactor)
    logger = logging.getLogger("tests.redaction")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    yield logger, stream, redactor
    logger.removeHandler(handler)


def test_jwt_is_redacted(
    capture: tuple[logging.Logger, io.StringIO, SecretRedactingFilter],
) -> None:
    logger, stream, _ = capture
    token = personal_token()

    logger.info("токен %s сохранён", token)

    assert token not in stream.getvalue()
    assert REDACTED in stream.getvalue()


@pytest.mark.parametrize(
    "message",
    [
        "Authorization: Bearer abcdef123456",
        "password=hunter2-very-secret",
        'api_key: "sk-ant-XYZ123456"',
        "Ключ: my-anthropic-key-123",
    ],
)
def test_key_values_and_registered_secrets(
    capture: tuple[logging.Logger, io.StringIO, SecretRedactingFilter], message: str
) -> None:
    logger, stream, _ = capture

    logger.warning(message)

    output = stream.getvalue()
    for secret in (
        "abcdef123456",
        "hunter2-very-secret",
        "sk-ant-XYZ123456",
        "my-anthropic-key-123",
    ):
        assert secret not in output


def test_exception_text_is_redacted(
    capture: tuple[logging.Logger, io.StringIO, SecretRedactingFilter],
) -> None:
    logger, stream, _ = capture
    token = personal_token()

    try:
        raise RuntimeError(f"сбой с токеном {token}")
    except RuntimeError:
        logger.exception("ошибка")

    assert "RuntimeError" in stream.getvalue()
    assert token not in stream.getvalue()


def test_broken_format_args_do_not_crash(
    capture: tuple[logging.Logger, io.StringIO, SecretRedactingFilter],
) -> None:
    logger, stream, _ = capture

    logger.info("два аргумента %s %s", "один")

    assert "два аргумента" in stream.getvalue()


def test_ordinary_words_are_kept(
    capture: tuple[logging.Logger, io.StringIO, SecretRedactingFilter],
) -> None:
    logger, stream, _ = capture

    logger.info("token_check: проверка токена завершена, категорий: 3")

    assert "token_check: проверка токена завершена, категорий: 3" in stream.getvalue()


def test_configure_logging_installs_filter() -> None:
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    try:
        redactor = configure_logging("debug", secrets=["super-secret-value"])

        assert len(root.handlers) == 1
        assert redactor in root.handlers[0].filters
        assert root.level == logging.DEBUG
        assert logging.getLogger("httpx").level == logging.WARNING
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)

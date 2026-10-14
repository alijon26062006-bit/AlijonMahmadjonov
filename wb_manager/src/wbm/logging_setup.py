"""Настройка логов. Фильтр вычищает токены, ключи и пароли из любых сообщений.

Клиент WB сам никогда не пишет токен в лог — фильтр это вторая линия защиты
на случай, если секрет попадёт в сообщение или текст исключения из чужого кода.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable

REDACTED = "***"

# Токены WB — это JWT (RFC 7519): три части base64url через точку, первая начинается с eyJ.
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*")
# Пары «ключ: значение» / «ключ=значение» для типичных секретов.
_KEY_VALUE_RE = re.compile(
    r"(?i)\b(authorization|token|api[_-]?key|password|passwd|secret|fernet[_-]?key)\b"
    r"(\s*[:=]\s*)(\"?)(?:bearer\s+)?([^\s\"',;]+)"
)
_MIN_SECRET_LEN = 8
_exception_formatter = logging.Formatter()


class SecretRedactingFilter(logging.Filter):
    """Заменяет секреты в сообщении, тексте исключения и стеке на «***»."""

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        super().__init__()
        self._secrets: set[str] = set()
        for secret in secrets:
            self.add_secret(secret)

    def add_secret(self, value: str) -> None:
        """Явно запомнить секрет (например, ключ Anthropic), чтобы вырезать его везде."""
        if len(value) >= _MIN_SECRET_LEN:
            self._secrets.add(value)

    def redact(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, REDACTED)
        text = _JWT_RE.sub(REDACTED, text)
        return _KEY_VALUE_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}{REDACTED}", text)

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # неверные аргументы форматирования не должны ронять приложение
            message = str(record.msg)
        record.msg = self.redact(message)
        record.args = None
        if record.exc_info:
            record.exc_text = self.redact(_exception_formatter.formatException(record.exc_info))
        if record.stack_info:
            record.stack_info = self.redact(record.stack_info)
        return True


def configure_logging(level: str = "INFO", secrets: Iterable[str] = ()) -> SecretRedactingFilter:
    """Один обработчик в stderr с фильтром секретов. Возвращает фильтр, чтобы добавлять секреты."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    redactor = SecretRedactingFilter(secrets)
    handler.addFilter(redactor)

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # httpx на уровне INFO пишет каждый URL — у нас есть свои, более понятные строки.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    return redactor

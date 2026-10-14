"""Разбор токена WB без проверки подписи — только для подсказок и настройки лимитов.

По документации токен — JWT (RFC 7519). Поля payload:
- `acc` — тип токена: 1 базовый, 2 тестовый, 3 персональный, 4 сервисный;
- `t` — true у тестового токена;
- `s` — битовая маска категорий и признака «только чтение»;
- `sid` — ID продавца, `id` — ID токена, `exp` — срок действия (unix-время).

Решения о безопасности на расшифровке не строятся: доступ к категориям
подтверждаем запросом /ping, а запрет записи обеспечивает белый список методов.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import IntEnum

from wbm.wb_client.categories import CATEGORIES, READ_ONLY_BIT, Category
from wbm.wb_client.errors import WBTokenFormatError


class TokenKind(IntEnum):
    BASE = 1
    TEST = 2
    PERSONAL = 3
    SERVICE = 4


@dataclass(frozen=True, slots=True)
class TokenInfo:
    """Что удалось узнать о токене. Сам токен здесь не хранится."""

    fingerprint: str
    """Короткий отпечаток (sha256) — им можно подписывать строки логов."""
    decoded: bool
    kind: TokenKind | None = None
    is_test: bool | None = None
    categories: frozenset[Category] | None = None
    read_only: bool | None = None
    seller_id: str | None = None
    token_id: str | None = None
    expires_at: datetime | None = None

    def is_expired(self, now: datetime) -> bool:
        return self.expires_at is not None and self.expires_at <= now

    def expires_within(self, period: timedelta, now: datetime) -> bool:
        return self.expires_at is not None and self.expires_at <= now + period


def normalize_token(raw: str) -> str:
    """Убирает пробелы по краям и необязательный префикс «Bearer », проверяет символы."""
    token = raw.strip()
    if token[:7].lower() == "bearer ":
        token = token[7:].strip()
    if not token:
        raise WBTokenFormatError("Токен пустой")
    if not token.isascii() or not token.isprintable() or any(ch.isspace() for ch in token):
        raise WBTokenFormatError("В токене есть пробелы или недопустимые символы")
    return token


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:12]


def inspect_token(token: str) -> TokenInfo:
    """Расшифровывает payload. Если формат неизвестен — decoded=False, остальное None."""
    fingerprint = token_fingerprint(token)
    payload = _decode_payload(token)
    if payload is None:
        return TokenInfo(fingerprint=fingerprint, decoded=False)

    kind = _token_kind(_int_field(payload, "acc"))
    t_field = payload.get("t")
    is_test: bool | None
    if isinstance(t_field, bool):
        is_test = t_field or kind is TokenKind.TEST
    elif kind is not None:
        is_test = kind is TokenKind.TEST
    else:
        is_test = None

    scopes = _int_field(payload, "s")
    categories: frozenset[Category] | None = None
    read_only: bool | None = None
    if scopes is not None:
        categories = frozenset(
            category
            for category, info in CATEGORIES.items()
            if info.scope_bit is not None and _bit(scopes, info.scope_bit)
        )
        read_only = _bit(scopes, READ_ONLY_BIT)

    exp = _int_field(payload, "exp")
    expires_at = datetime.fromtimestamp(exp, tz=UTC) if exp is not None and exp > 0 else None

    return TokenInfo(
        fingerprint=fingerprint,
        decoded=True,
        kind=kind,
        is_test=is_test,
        categories=categories,
        read_only=read_only,
        seller_id=_str_field(payload, "sid"),
        token_id=_str_field(payload, "id"),
        expires_at=expires_at,
    )


def _token_kind(value: int | None) -> TokenKind | None:
    if value is None:
        return None
    try:
        return TokenKind(value)
    except ValueError:
        return None


def _bit(mask: int, position: int) -> bool:
    # Позиция N в таблице документации трактуется как значение 2**N (бит 0 — младший).
    # Трактовку нужно сверить на реальном токене — см. docs/WB_API.md.
    return bool((mask >> position) & 1)


def _decode_payload(token: str) -> dict[str, object] | None:
    parts = token.split(".")
    if len(parts) != 3 or not parts[1]:
        return None
    segment = parts[1]
    try:
        raw = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
        data = json.loads(raw)
    except (binascii.Error, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return {str(key): value for key, value in data.items()}


def _int_field(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    # bool — подкласс int, поэтому сравниваем тип строго.
    return value if type(value) is int else None


def _str_field(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    return value if isinstance(value, str) and value else None

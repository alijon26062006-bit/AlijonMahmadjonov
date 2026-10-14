"""Claude не придумывает цифры: каждое число в его тексте должно быть во входных данных.

Допускаются форматы «1 500», «1500,5», «34.7 %» и округления до целого или
до одного знака (34,7 → 35). Всё остальное — выдуманное число, такой текст
отбрасывается и заменяется шаблонным.
"""

from __future__ import annotations

import json
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_NUMBER_RE = re.compile(r"(?<![\w.,])\d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?")


def _to_decimal(raw: str) -> Decimal | None:
    cleaned = re.sub(r"[   ]", "", raw).replace(",", ".")
    try:
        return Decimal(cleaned).normalize()
    except InvalidOperation:
        return None


def numbers_in(text: str) -> set[Decimal]:
    found = set()
    for match in _NUMBER_RE.finditer(text):
        value = _to_decimal(match.group())
        if value is not None:
            found.add(value)
    return found


def allowed_numbers(source: object) -> set[Decimal]:
    """Все числа из входных данных и их допустимые округления."""
    text = json.dumps(source, ensure_ascii=False, default=str)
    base = numbers_in(text)
    allowed = set(base)
    for value in base:
        for places in (Decimal(1), Decimal("0.1")):
            allowed.add(value.quantize(places, rounding=ROUND_HALF_UP).normalize())
        allowed.add(abs(value))
    return allowed


def unknown_numbers(text: str, allowed: set[Decimal]) -> list[str]:
    return sorted(format(n, "f") for n in numbers_in(text) - allowed)

"""Перенос балансов со старого бота.

Список выгружают по-разному: «123456789 100», «123456789 - 100.50»,
«id: 123456789, balance: 100», таблицей с заголовками. Разбирать каждый
формат отдельно бессмысленно — берём из строки два числа: первое длинное
это ID, последнее это сумма.

Деньги чужие, поэтому разбор ничего не применяет сам: он только читает
и показывает, что понял. Применяет — владелец, отдельным нажатием.
"""
from __future__ import annotations

import re

#: ID пользователя Telegram: минимум пять цифр. Меньше — не бывает.
ID_RE = re.compile(r"\b(\d{5,15})\b")
#: Сумма: с копейками или без, разделитель точка или запятая.
MONEY_RE = re.compile(r"(\d+(?:[.,]\d{1,2})?)")


def to_diram(text: str) -> int | None:
    """Сумму в сомони — в дирамы. None — не разобрали."""
    cleaned = text.replace(",", ".").strip()
    try:
        value = round(float(cleaned) * 100)
    except ValueError:
        return None
    return value if value >= 0 else None


def parse_balances(raw: str) -> tuple[list[tuple[int, int]], list[str]]:
    """Разобрать список. Возвращает (пары «ID → дирамы», непонятые строки).

    Повтор одного ID не удваивает баланс: остаётся последняя строка —
    так же, как если бы выгрузку сделали заново.
    """
    found: dict[int, int] = {}
    skipped: list[str] = []

    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue

        ids = ID_RE.findall(line)
        if not ids:
            skipped.append(line)
            continue

        user_id = int(ids[0])
        # Сумма — это то, что стоит после ID: иначе в строке вида
        # «5 123456789 100» первым числом оказался бы номер по порядку.
        tail = line[line.index(ids[0]) + len(ids[0]):]
        numbers = MONEY_RE.findall(tail)
        if not numbers:
            skipped.append(line)
            continue

        amount = to_diram(numbers[-1])
        if amount is None:
            skipped.append(line)
            continue
        found[user_id] = amount

    return list(found.items()), skipped


def preview(pairs: list[tuple[int, int]], limit: int = 5) -> list[tuple[int, int]]:
    """Первые записи — чтобы владелец глазами сверил, что понято верно."""
    return pairs[:limit]

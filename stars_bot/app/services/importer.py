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
#: Юзернейм, если он есть в строке.
NAME_RE = re.compile(r"@([A-Za-z0-9_]{4,32})")
#: Хвост таблицы выгрузки: баланс, потрачено, число заказов.
#: Без этого из строки «… 70.00  0.00  0» взялось бы последнее число —
#: количество заказов, и все балансы обнулились бы.
TABLE_TAIL = re.compile(
    r"(\d+(?:[.,]\d{1,2}))\s+(\d+(?:[.,]\d{1,2}))\s+(\d+)\s*$"
)


def to_diram(text: str) -> int | None:
    """Сумму в сомони — в дирамы. None — не разобрали."""
    cleaned = text.replace(",", ".").strip()
    try:
        value = round(float(cleaned) * 100)
    except ValueError:
        return None
    return value if value >= 0 else None


def parse_balances(raw: str) -> tuple[list[dict], list[str]]:
    """Разобрать список. Возвращает (записи, непонятые строки).

    Запись — это {"id", "amount", "username"}. В «непонятые» попадают
    только строки, где ID есть, а сумму разобрать не вышло: шапка и
    разделители отбрасываются молча.

    Повтор одного ID не удваивает баланс: остаётся последняя строка —
    так же, как если бы выгрузку сделали заново.
    """
    found: dict[int, dict] = {}
    skipped: list[str] = []

    for line in (raw or "").splitlines():
        line = line.rstrip()
        if not line.strip():
            continue

        ids = ID_RE.findall(line)
        if not ids:
            # Шапка, разделители, итоги — в выгрузке их всегда полно.
            # Показывать их владельцу как «не понял» значит пугать зря:
            # в них и нет ничего, что нужно переносить.
            continue

        user_id = int(ids[0])
        # Сумма — это то, что стоит после ID: иначе в строке вида
        # «5 123456789 100» первым числом оказался бы номер по порядку.
        tail = line[line.index(ids[0]) + len(ids[0]):]

        # Выгрузка таблицей: в конце строки баланс, потрачено и число
        # заказов. Берём первое из трёх — остальное не баланс.
        table = TABLE_TAIL.search(tail)
        if table:
            amount = to_diram(table.group(1))
        else:
            numbers = MONEY_RE.findall(tail)
            amount = to_diram(numbers[-1]) if numbers else None

        if amount is None:
            skipped.append(line.strip())
            continue

        name = NAME_RE.search(tail)
        found[user_id] = {
            "id": user_id,
            "amount": amount,
            "username": name.group(1) if name else "",
        }

    return list(found.values()), skipped


def with_money(rows: list[dict]) -> list[dict]:
    """Только те, у кого на счету есть деньги."""
    return [row for row in rows if row["amount"] > 0]


def preview(rows: list[dict], limit: int = 5) -> list[dict]:
    """Первые записи — чтобы владелец глазами сверил, что понято верно.

    Показываем сначала тех, у кого деньги: нули занимают весь экран,
    а проверять надо именно суммы.
    """
    rich = sorted(with_money(rows), key=lambda row: -row["amount"])
    return (rich or rows)[:limit]

"""Призы за места в финале.

Приз — это текст, а не только число. «1000» бот покажет как <b>1000⭐</b>,
а «Telegram Premium на 3 месяца» — как есть. Так призом может быть что
угодно: звёзды, деньги, подписка, реклама в канале.

Разделитель — перевод строки: каждый приз с новой строки. Запятая остаётся
разделителем только когда все части — числа: иначе запятая внутри самого
приза («Premium, 3 месяца») разорвала бы его надвое. Старая запись вида
«1000,500,250» читается по этому же правилу, поэтому ничего не ломается.
"""
from __future__ import annotations

from html import escape

from services.validation import InputError

MAX_PRIZES = 10
MAX_LENGTH = 120
STARS = "⭐"


def is_stars(value: str) -> bool:
    """Приз задан числом — значит это звёзды."""
    return value.strip().isdigit()


def label(value: str) -> str:
    """Как приз выглядит в сообщении. Готов к вставке в HTML."""
    text = str(value).strip()
    return f"{text}{STARS}" if is_stars(text) else escape(text)


def parse(raw: str) -> list[str]:
    """Прочитать список призов. Пустой ввод — пустой список."""
    text = (raw or "").strip()
    if not text:
        return []

    if "\n" in text:
        parts = [part.strip() for part in text.splitlines()]
    else:
        parts = [part.strip() for part in text.replace(";", ",").split(",")]
        # запятая внутри текстового приза — не разделитель
        if not all(is_stars(part) for part in parts if part):
            parts = [text]

    return [part for part in parts if part][:MAX_PRIZES]


def dump(values) -> str:
    """Как список хранится в базе."""
    return "\n".join(str(value).strip() for value in values if str(value).strip())


def check(raw: str) -> list[str]:
    """То же, что parse, но с понятными отказами — для ввода из панели."""
    values = parse(raw)
    if not values:
        raise InputError(
            "Пустое значение. Напишите призы — каждый с новой строки, "
            "например:\n<code>1000\n500\n250</code>"
        )

    too_long = next((v for v in values if len(v) > MAX_LENGTH), None)
    if too_long is not None:
        raise InputError(
            f"Приз слишком длинный ({len(too_long)} символов). "
            f"Максимум — {MAX_LENGTH}. Опишите короче."
        )

    if len(parse(raw)) == MAX_PRIZES and len(_all_parts(raw)) > MAX_PRIZES:
        raise InputError(f"Слишком много призов. Максимум — {MAX_PRIZES}.")
    return values


def _all_parts(raw: str) -> list[str]:
    text = (raw or "").strip()
    parts = text.splitlines() if "\n" in text else [text]
    return [part for part in (p.strip() for p in parts) if part]


def line(place: int, value: str, medal: str) -> str:
    """Одна строка списка призов: медаль, место и сам приз."""
    return f"{medal} <b>{label(value)}</b>"

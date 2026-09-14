"""Пардохт: коди тасдиқ ва ҳаволаи «Душанбе Сити» бо як пахш."""

from __future__ import annotations

import re
import secrets
from urllib.parse import quote

_DIGITS = re.compile(r"\D+")


def make_code() -> str:
    """Коди чоррақамаи тасдиқ, ки харидор дар шарҳи ҳавола менависад."""
    return f"{secrets.randbelow(9000) + 1000}"


def card_digits(card: str) -> str:
    return _DIGITS.sub("", card or "")


def format_card(card: str) -> str:
    """«8888123412341234» → «8888 1234 1234 1234»"""
    digits = card_digits(card)
    if len(digits) < 12:
        return card
    return " ".join(digits[i : i + 4] for i in range(0, len(digits), 4))


def amount_text(diram: int) -> str:
    """1250 → «12.50» — барои ҷойнишини {amount} дар ҳавола."""
    return f"{diram // 100}.{diram % 100:02d}"


def build_pay_link(template: str, *, card: str, amount: int, comment: str) -> str | None:
    """Ҳаволаро аз шаблон месозад.

    Ҷойнишинҳои дастрас:
      {card}       — рақами корт бе фосила
      {amount}     — маблағ бо нуқта, намуна 150.00
      {amount_int} — маблағ ҳамчун адади бутун дар сомонӣ
      {diram}      — маблағ дар дирам
      {comment}    — коди тасдиқ (барои URL омода)

    Агар шаблон холӣ ё нодуруст бошад — None бармегардад.
    """
    template = (template or "").strip()
    if not template:
        return None
    values = {
        "card": card_digits(card),
        "amount": amount_text(amount),
        "amount_int": str(amount // 100),
        "diram": str(amount),
        "comment": quote(str(comment), safe=""),
    }
    try:
        return template.format(**values)
    except (KeyError, IndexError, ValueError):
        return None

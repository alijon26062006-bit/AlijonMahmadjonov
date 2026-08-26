"""Ссылка на оплату в приложении «Душанбе Сити».

Формат: https://pay.dc.tj/?a=СЧЁТ&c=КОММЕНТАРИЙ&f1=УСЛУГА&s=СУММА

Ссылка открывает приложение с уже подставленными счётом и суммой —
покупателю остаётся подтвердить перевод. Это убирает главный источник
ошибок при пополнении: переписывание номера карты и суммы вручную.

В комментарий кладётся код заявки: по нему владелец находит платёж в
выписке, даже если покупатель прислал чек не сразу.
"""
from __future__ import annotations

import random
from urllib.parse import quote

BASE_URL = "https://pay.dc.tj/"


def make_reference(prefix: str = "TOP") -> str:
    """Короткий код платежа: его видно и в комментарии, и в заявке."""
    return f"{prefix}{random.randint(1000, 9999)}"


def amount_text(diram: int) -> str:
    """Сумма для ссылки: 5000 -> '50', 5050 -> '50.50'.

    Целые суммы пишем без копеек — так их проще сверять глазами.
    """
    whole, frac = divmod(max(diram, 0), 100)
    return str(whole) if frac == 0 else f"{whole}.{frac:02d}"


def build_link(account: str, amount_diram: int, comment: str, service: str = "133") -> str:
    """Собрать ссылку на оплату."""
    account = "".join(ch for ch in account if ch.isdigit())
    params = [
        f"a={quote(account)}",
        f"c={quote(comment, safe='')}",
        f"f1={quote(str(service))}",
        f"s={quote(amount_text(amount_diram))}",
    ]
    return BASE_URL + "?" + "&".join(params)


def build_comment(prefix: str, reference: str) -> str:
    """Комментарий к платежу: подпись владельца плюс код заявки."""
    prefix = (prefix or "").strip()
    return f"{prefix} {reference}".strip()


def is_ready(account: str) -> bool:
    """Хватает ли данных, чтобы собрать ссылку."""
    digits = "".join(ch for ch in (account or "") if ch.isdigit())
    return len(digits) >= 10

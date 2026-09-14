"""Ранги тугмаҳо.

Telegram барои ҳар тугма майдони ``style``-ро медиҳад:

* ``success`` — сабз: тасдиқ ва пул ба ҳисоб (пардохт, пур кардан, иҷро шуд)
* ``danger``  — сурх: бекор кардан, рад кардан, маҳдуд кардан
* ``primary`` — кабуд: бахшҳои асосии дӯкон
* ``link``    — ҳавола: тугмаҳое, ки сайти берунаро мекушоянд

Ҳама дар як ҷо аст, то ранги тамоми бот аз ҳамин файл идора шавад.
"""

from __future__ import annotations

import os

from aiogram.enums import ButtonStyle

SUCCESS = ButtonStyle.SUCCESS
DANGER = ButtonStyle.DANGER
PRIMARY = ButtonStyle.PRIMARY
LINK = ButtonStyle.LINK

#: Агар мизоҷони кӯҳна рангро дастгирӣ накунанд — SHOP_BUTTON_COLORS=0
_ENABLED = os.getenv("SHOP_BUTTON_COLORS", "1").strip().lower() not in (
    "0", "no", "false", "off",
)


def enabled() -> bool:
    return _ENABLED


def set_enabled(value: bool) -> None:
    """Барои тестҳо ва танзими дастӣ."""
    global _ENABLED
    _ENABLED = value


def pick(style: str | None) -> str | None:
    """Рангро бармегардонад ё None, агар рангкунӣ хомӯш бошад."""
    return style if (_ENABLED and style) else None

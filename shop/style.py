"""Ранги тугмаҳо.

Telegram барои ҳар тугма майдони ``style``-ро медиҳад:

* ``success`` — сабз: тасдиқ ва пул ба ҳисоб (пардохт, пур кардан, иҷро шуд)
* ``danger``  — сурх: бекор кардан, рад кардан, маҳдуд кардан
* ``primary`` — кабуд: бахшҳои асосии дӯкон
* ``link``    — ТАНҲО барои RichMessage; дар клавиатураи inline Telegram
  онро қабул намекунад (иҷозат: ``danger``, ``success``, ``primary``)

Ҳама дар як ҷо аст, то ранги тамоми бот аз ҳамин файл идора шавад.
"""

from __future__ import annotations

import os

from aiogram.enums import ButtonStyle

SUCCESS = ButtonStyle.SUCCESS
DANGER = ButtonStyle.DANGER
PRIMARY = ButtonStyle.PRIMARY
LINK = ButtonStyle.LINK  # барои клавиатураи inline истифода нашавад!

#: Танҳо инҳоро Telegram дар тугмаҳои клавиатура қабул мекунад.
KEYBOARD_STYLES = frozenset({SUCCESS, DANGER, PRIMARY})

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
    """Рангро бармегардонад ё None, агар рангкунӣ хомӯш бошад.

    Рангҳои берун аз рӯйхати иҷозатдодашуда партофта мешаванд — вагарна
    Telegram тамоми паёмро рад мекунад.
    """
    if not _ENABLED or not style:
        return None
    return style if style in KEYBOARD_STYLES else None


def strip(markup) -> bool:
    """Ҳамаи рангҳоро аз клавиатура мебардорад. True — агар чизе тағйир ёбад."""
    changed = False
    for attr in ("inline_keyboard", "keyboard"):
        rows = getattr(markup, attr, None) or []
        for row in rows:
            for button in row:
                if getattr(button, "style", None) is not None:
                    button.style = None
                    changed = True
    return changed

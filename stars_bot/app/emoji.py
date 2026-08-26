"""Все эмодзи бота в одном месте — каждое меняется из админ-панели.

Тексты и клавиатуры не пишут значки напрямую, а вставляют токен вида
[[stars]]. Подстановка происходит при обращении, поэтому смена значка в
панели видна сразу, без перезапуска.
"""
from __future__ import annotations

import re

# Группа -> {ключ: (значок по умолчанию,понятное название)}
GROUPS: dict[str, dict[str, tuple[str, str]]] = {
    "Товары": {
        "stars": ("⭐️", "Звёзды"),
        "premium": ("👑", "Telegram Premium"),
        "gift": ("🎁", "Подарок"),
    },
    "Деньги": {
        "money": ("💰", "Баланс"),
        "deposit": ("💳", "Пополнение"),
        "price": ("🏷", "Цена"),
        "refund": ("↩️", "Возврат"),
        "receipt": ("🧾", "Чек, заказ"),
    },
    "Разделы": {
        "profile": ("👤", "Профиль"),
        "history": ("📜", "История"),
        "promo": ("🎟", "Промокод"),
        "referral": ("👥", "Рефералы"),
        "support": ("💬", "Поддержка"),
        "info": ("ℹ️", "Информация"),
        "reviews": ("👍", "Отзывы"),
        "top": ("🏆", "Топ клиентов"),
        "calc": ("🖩", "Калькулятор"),
    },
    "Состояния": {
        "ok": ("✅", "Успех"),
        "fail": ("❌", "Ошибка"),
        "warn": ("⚠️", "Предупреждение"),
        "wait": ("⏳", "Ожидание"),
        "search": ("🔍", "Проверка"),
        "party": ("🎉", "Праздник"),
        "block": ("🚫", "Запрет"),
    },
    "Навигация": {
        "back": ("‹", "Назад"),
        "cancel": ("✖️", "Отмена"),
        "confirm": ("✅", "Подтвердить"),
        "edit": ("✏️", "Изменить"),
        "refresh": ("🔄", "Обновить"),
    },
}

#: Плоский словарь ключ -> значок по умолчанию
DEFAULTS: dict[str, str] = {
    key: value for group in GROUPS.values() for key, (value, _) in group.items()
}
#: Ключ -> человеческое название
TITLES: dict[str, str] = {
    key: title for group in GROUPS.values() for key, (_, title) in group.items()
}

TOKEN_RE = re.compile(r"\[\[(\w+)\]\]")


def em(key: str) -> str:
    """Значок по ключу: сперва из настроек панели, потом по умолчанию."""
    from app import runtime

    return runtime.get(f"emoji_{key}") or DEFAULTS.get(key, "")


def substitute(text: str) -> str:
    """Заменить все [[токены]] на значки."""
    return TOKEN_RE.sub(lambda m: em(m.group(1)), text)


def is_emoji_like(value: str) -> bool:
    """Грубая проверка: значок должен быть коротким и без букв.

    Строгая проверка на эмодзи не нужна — владелец может захотеть поставить
    любой символ вроде «•» или «›», лишь бы это не было предложением.
    """
    value = value.strip()
    if not value or len(value) > 8:
        return False
    return not any(char.isalnum() for char in value)

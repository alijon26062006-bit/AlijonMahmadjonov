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
        "point": ("👇", "Указатель вниз"),
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
    """Обычный значок — тот, что виден всем и годится для кнопок."""
    from app import runtime

    return runtime.get(f"emoji_{key}") or DEFAULTS.get(key, "")


def custom_id(key: str) -> str:
    """ID премиум-эмодзи для этого значка, если он задан."""
    from app import runtime

    return runtime.get(f"emoji_id_{key}")


def premium_on() -> bool:
    """Разрешено ли подставлять премиум-эмодзи.

    Выключено по умолчанию: если у владельца нет Telegram Premium,
    Telegram отвергает такие сообщения целиком — бот замолчал бы весь.
    Включается в панели только после успешной проверки.
    """
    from app import runtime

    return runtime.get_bool("custom_emoji_on")


def em_html(key: str) -> str:
    """Значок для сообщения: премиум-эмодзи, если задан и разрешён.

    Обычный значок остаётся внутри тега запасным вариантом — его увидят
    те, у кого премиум-эмодзи не отображается.
    """
    plain = em(key)
    emoji_id = custom_id(key)
    if not emoji_id or not premium_on():
        return plain
    return f'<tg-emoji emoji-id="{emoji_id}">{plain}</tg-emoji>'


def substitute(text: str) -> str:
    """Заменить [[токены]] на значки — с премиум-эмодзи, если они включены."""
    return TOKEN_RE.sub(lambda m: em_html(m.group(1)), text)


def substitute_plain(text: str) -> str:
    """То же, но всегда обычными значками — для кнопок и служебных мест,
    где разметка не поддерживается."""
    return TOKEN_RE.sub(lambda m: em(m.group(1)), text)


def extract_custom(message) -> tuple[str, str] | None:
    """Достать премиум-эмодзи из присланного сообщения.

    Возвращает (id, запасной значок) или None, если это обычный текст.
    Так владельцу не нужно искать ID руками — достаточно прислать эмодзи.
    """
    entities = getattr(message, "entities", None) or []
    text = getattr(message, "text", "") or ""
    for entity in entities:
        if getattr(entity, "type", "") != "custom_emoji":
            continue
        emoji_id = getattr(entity, "custom_emoji_id", "")
        if not emoji_id:
            continue
        # Telegram считает смещения в единицах UTF-16, а Python — в
        # символах. Для эмодзи вне базовой плоскости (а это почти все
        # премиум-эмодзи) обычный срез захватил бы соседний символ.
        start = getattr(entity, "offset", 0)
        length = getattr(entity, "length", 1)
        units = text.encode("utf-16-le")
        fallback = units[start * 2:(start + length) * 2].decode(
            "utf-16-le", errors="ignore"
        ).strip()
        return str(emoji_id), fallback or "⭐️"
    return None


def is_emoji_like(value: str) -> bool:
    """Грубая проверка: значок должен быть коротким и без букв.

    Строгая проверка на эмодзи не нужна — владелец может захотеть поставить
    любой символ вроде «•» или «›», лишь бы это не было предложением.
    """
    value = value.strip()
    if not value or len(value) > 8:
        return False
    return not any(char.isalnum() for char in value)

"""Анимация поверх сообщения: огонь, конфетти и т.п. (message effects).

Telegram проигрывает её, когда сообщение приходит, — только в личке с
ботом и без Premium у клиента. В Bot API это параметр message_effect_id;
сами номера эффектов в документации не перечислены, это общеизвестные
id стандартного набора. Если Telegram какой-то не примет, EffectGuard
отправит сообщение без него — ничего не ломается.

Включается и выключается в панели: 🎨 Оформление.
"""
from __future__ import annotations

from app import runtime

FIRE = "5104841245755180586"      # 🔥
PARTY = "5046509860389126442"     # 🎉
HEART = "5159385139981059251"     # ❤️
LIKE = "5107584321108051014"      # 👍

#: Где какой эффект. Только существующие сообщения — ничего нового.
WHERE = {
    "start": FIRE,          # /start
    "welcome": PARTY,       # первый /start нового клиента
    "paid": PARTY,          # оплата прошла, баланс пополнен
    "done": PARTY,          # заказ выполнен
    "promo": PARTY,         # промокод принят
    "referral": PARTY,      # пригласившему — бонус за нового клиента
}


def on() -> bool:
    return runtime.get("effects_on", "1") != "0"


def kw(name: str) -> dict:
    """Аргумент для отправки: {'message_effect_id': …} или пусто."""
    effect = WHERE.get(name)
    return {"message_effect_id": effect} if effect and on() else {}

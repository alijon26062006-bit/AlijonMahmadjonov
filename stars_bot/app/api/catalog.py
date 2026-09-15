"""Каталог товаров для API.

Своей таблицы товаров у бота нет и заводить её нельзя: звёзды считаются
по цене за штуку, Premium живёт в настройках, игровые пакеты приходят от
поставщика и меняются каждый день. Таблица-копия разъехалась бы с
настоящими ценами в первый же час, и разработчик покупал бы по цене,
которой уже нет.

Поэтому каталог собирается на лету из тех же источников, что и кнопки в
боте, а API отдаёт его в одном формате.

Деньги в ответах — целые числа в дирамах (1 сомони = 100 дирам). Дробных
чисел в деньгах нет нарочно: 0.1 + 0.2 в любом языке даёт не 0.3, и
разработчик, сложив цены на своей стороне, получил бы копеечные расхождения.
Рядом кладём amount_text — строку для показа человеку.
"""
from __future__ import annotations

from app import db, runtime
from app.money import fmt, stars_cost, steam_cost

#: Валюта расчётов. Меняется вместе с настройками бота.
def currency() -> str:
    from app.config import settings

    return getattr(settings, "currency_code", "") or "TJS"


def money(diram: int) -> dict:
    """Одна сумма в двух видах: для расчётов и для показа."""
    return {"amount": diram, "amount_text": f"{diram // 100}.{diram % 100:02d}",
            "currency": currency()}


def _stars() -> dict | None:
    if not runtime.get_bool("stars_enabled") or runtime.star_price_e4() <= 0:
        return None
    lo, hi = runtime.min_stars(), runtime.max_stars()
    return {
        "id": "stars",
        "type": "stars",
        "name": "Telegram Stars",
        "unit": "star",
        "variable": True,
        "min_quantity": lo,
        "max_quantity": hi,
        "unit_price": runtime.star_price_e4(),   # десятитысячные сомони
        "price_example": money(stars_cost(lo)) | {"quantity": lo},
        "customer": "Юзернейм получателя в Telegram, например @durov",
        "customer_required": True,
    }


def _premium() -> list[dict]:
    if not runtime.get_bool("premium_enabled"):
        return []
    out = []
    for plan in runtime.premium_plans():
        months = int(plan["months"])
        out.append({
            "id": f"premium:{months}",
            "type": "premium",
            "name": f"Telegram Premium — {months} мес.",
            "unit": "month",
            "variable": False,
            "quantity": months,
            "customer": "Юзернейм получателя в Telegram, например @durov",
            "customer_required": True,
            **money(int(plan["price"])),
        })
    return out


def _steam() -> list[dict]:
    if not runtime.steam_on():
        return []
    out = []
    for amount in runtime.steam_packs():
        out.append({
            "id": f"steam:{amount}",
            "type": "steam",
            "name": f"Steam — {amount} {runtime.steam_currency()}",
            "unit": runtime.steam_currency(),
            "variable": False,
            "quantity": amount,
            "customer": "Логин аккаунта Steam",
            "customer_required": True,
            **money(steam_cost(amount)),
        })
    return out


async def _games(conn, provider) -> list[dict]:
    """Игровые пакеты. Молчим о сломанном поставщике: остальной каталог
    должен отдаваться, даже если игры сейчас не отвечают."""
    from app.handlers.games import offers_of
    from app.services import suppliers

    if not runtime.get_bool("games_enabled"):
        return []

    out = []
    for game in await db.list_games(conn, only_enabled=True):
        try:
            offers = await offers_of(suppliers.for_games(provider), game, conn)
        except Exception:  # noqa: BLE001 — одна игра не должна гасить каталог
            continue
        for offer in offers:
            out.append({
                "id": f"game:{game.category_id}:{offer['offer_id']}",
                "type": "game",
                "name": f"{game.title} — {offer['name']}",
                "game": game.title,
                "game_id": game.category_id,
                "unit": "pack",
                "variable": False,
                "quantity": 1,
                "customer": ", ".join(game.field_names),
                "customer_required": True,
                "fields": list(game.field_names),
                "cost": offer["cost"],       # внутреннее: в ответ не уходит
                **money(offer["price"]),
            })
    return out


def public(item: dict) -> dict:
    """Товар так, как его видит чужой разработчик.

    Себестоимость и внутренние поля не отдаём: сколько товар стоит нам —
    не его дело, и по этой цифре считается наша наценка.
    """
    return {k: v for k, v in item.items() if k not in ("cost",)}


async def listing(conn, provider, kind: str = "") -> list[dict]:
    """Весь каталог или одна его часть."""
    items: list[dict] = []
    stars = _stars()
    if stars:
        items.append(stars)
    items += _premium()
    items += _steam()
    items += await _games(conn, provider)
    return [item for item in items if not kind or item["type"] == kind]


async def find(conn, provider, product_id: str) -> dict | None:
    """Один товар по его id. Ищем по тому же списку, что и отдаём:
    иначе появился бы товар, который виден в каталоге, но не покупается."""
    for item in await listing(conn, provider):
        if item["id"] == product_id:
            return item
    return None


def price_of(item: dict, quantity: int) -> int:
    """Во сколько обойдётся quantity этого товара, в дирамах."""
    if item["type"] == "stars":
        return stars_cost(quantity)
    return int(item["amount"])


def order_plan(item: dict, quantity: int) -> tuple[str, int]:
    """Во что превращается товар при заказе: (product_type, quantity).

    product_type — тот же, что у заказов из бота, чтобы отчёты, возвраты
    и статистика считали их вместе, а не двумя отдельными кучами.
    """
    if item["type"] == "stars":
        return "stars", quantity
    if item["type"] == "premium":
        return "premium", int(item["quantity"])
    if item["type"] == "steam":
        return "steam", int(item["quantity"])
    _, category_id, _offer = item["id"].split(":", 2)
    return f"game:{category_id}", 1


def offer_id_of(item: dict) -> str:
    return item["id"].split(":", 2)[2] if item["type"] == "game" else ""

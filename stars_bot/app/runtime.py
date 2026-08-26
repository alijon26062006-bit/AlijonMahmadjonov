"""Настройки, которые меняются из админ-панели и переживают перезапуск.

Значения лежат в таблице settings, а в памяти держится кэш — тексты и
клавиатуры собираются синхронно и не могут ждать запрос к базе.
При старте кэш заполняется из базы, недостающее берётся из .env.

Менять только через set(): он пишет в базу и обновляет кэш одной операцией,
иначе после перезапуска цена откатится на старую.
"""
from __future__ import annotations

import json
import logging

import aiosqlite

from app.config import BASE_DIR, settings

log = logging.getLogger(__name__)

PRICES_FILE = BASE_DIR / "prices.json"

# Ключ -> значение по умолчанию (берётся из .env при первом запуске).
DEFAULTS: dict[str, str] = {}
_cache: dict[str, str] = {}


def _premium_from_file() -> str:
    try:
        with PRICES_FILE.open(encoding="utf-8") as fh:
            return json.dumps(json.load(fh)["premium"], ensure_ascii=False)
    except Exception:  # noqa: BLE001 — файла может не быть, это не ошибка
        return json.dumps([
            {"months": 3, "price": 13000},
            {"months": 6, "price": 17500},
            {"months": 12, "price": 31500},
        ])


def _build_defaults() -> dict[str, str]:
    return {
        # цены
        "star_price_diram": str(settings.star_price_diram),
        "star_cost_diram": "0",          # себестоимость звезды, 0 = не задана
        "premium_costs": "{}",           # себестоимость Premium по срокам
        "auto_price": "0",               # обновлять цены самому
        "auto_price_every": "60",        # как часто, минуты
        "tz_hours": "5",                 # часовой пояс владельца
        "usd_rate_diram": "0",           # сколько дирам в одном долларе
        "margin_percent": "0",           # наценка к себестоимости
        "premium_plans": _premium_from_file(),
        "min_stars": str(settings.min_stars),
        "max_stars": str(settings.max_stars),
        # деньги
        "min_deposit_diram": str(settings.min_deposit_diram),
        "referral_percent": str(settings.referral_percent),
        # реквизиты
        "pay_card_number": settings.pay_card_number,
        "pay_card_holder": settings.pay_card_holder,
        "pay_card_bank": settings.pay_card_bank,
        "pay_city": settings.pay_city,
        "pay_extra": settings.pay_extra,
        # тексты
        "support_notice": "",
        # пути API сервиса выдачи, найденные перебором
        "fazer_balance_path": "",
        "fazer_order_path": "",
        # кошелёк и присмотр за выдачей
        "topup_at": "",                  # когда последний раз пополняли
        "stars_since_topup": "0",        # выдано звёзд с тех пор
        "premium_since_topup": "0",      # выдано месяцев Premium
        "fail_streak": "0",              # подряд неудавшихся выдач
        "autostop_after": "3",           # после скольких подряд гасить продажу
        "autostopped": "0",              # продажу выключил сам бот
        # доступность
        "stars_enabled": "1",
        "premium_enabled": "1",
        "deposit_enabled": "1",
    }


async def load(conn: aiosqlite.Connection) -> None:
    """Заполнить кэш: сначала значения из .env, поверх — сохранённые в базе."""
    global DEFAULTS
    DEFAULTS = _build_defaults()
    _cache.clear()
    _cache.update(DEFAULTS)

    async with conn.execute("SELECT key, value FROM settings") as cur:
        for row in await cur.fetchall():
            _cache[row["key"]] = row["value"]
    log.info("Настройки загружены: %d ключей", len(_cache))


async def set_value(conn: aiosqlite.Connection, key: str, value: str) -> None:
    await conn.execute(
        """INSERT INTO settings (key, value) VALUES (?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
        (key, value),
    )
    await conn.commit()
    _cache[key] = value
    log.info("Настройка %s изменена", key)


async def reset(conn: aiosqlite.Connection, key: str) -> None:
    await conn.execute("DELETE FROM settings WHERE key = ?", (key,))
    await conn.commit()
    _cache[key] = _defaults().get(key, "")


def _defaults() -> dict[str, str]:
    """Значения по умолчанию. Считаются лениво: модуль могут прочитать
    раньше, чем вызовут load(), и тогда всё молча возвращало бы пустоту."""
    global DEFAULTS
    if not DEFAULTS:
        DEFAULTS = _build_defaults()
    return DEFAULTS


def get(key: str, default: str = "") -> str:
    if key in _cache:
        return _cache[key]
    return _defaults().get(key, default)


def get_int(key: str, default: int = 0) -> int:
    try:
        return int(get(key) or default)
    except ValueError:
        return default


def get_bool(key: str) -> bool:
    return get(key) == "1"


# ------------------------------------------------------- удобные обёртки


def star_price() -> int:
    """Цена продажи одной звезды в дирамах."""
    return get_int("star_price_diram", settings.star_price_diram)


def star_cost() -> int:
    """Себестоимость звезды в дирамах. 0 — не задана."""
    return get_int("star_cost_diram")


def margin_percent() -> int:
    return get_int("margin_percent")


def usd_rate() -> int:
    """Сколько дирам в 1 долларе. 0 — курс не задан."""
    return get_int("usd_rate_diram")


def price_from_margin() -> int:
    """Цена продажи, посчитанная из себестоимости и наценки."""
    cost = star_cost()
    if cost <= 0:
        return star_price()
    return round(cost * (100 + margin_percent()) / 100)


def profit_per_star() -> int:
    """Сколько остаётся с одной звезды. Может быть отрицательным —
    это как раз то, что владельцу важно увидеть сразу."""
    cost = star_cost()
    return star_price() - cost if cost > 0 else 0


def premium_plans() -> list[dict]:
    try:
        plans = json.loads(get("premium_plans"))
        return sorted(plans, key=lambda plan: plan["months"])
    except (ValueError, KeyError, TypeError):
        log.warning("Битый premium_plans, беру значения по умолчанию")
        return json.loads(_premium_from_file())


async def save_premium_plans(conn: aiosqlite.Connection, plans: list[dict]) -> None:
    await set_value(conn, "premium_plans", json.dumps(plans, ensure_ascii=False))


def find_premium(months: int) -> dict | None:
    return next((plan for plan in premium_plans() if plan["months"] == months), None)


def min_stars() -> int:
    return get_int("min_stars", settings.min_stars)


def max_stars() -> int:
    return get_int("max_stars", settings.max_stars)


def min_deposit() -> int:
    return get_int("min_deposit_diram", settings.min_deposit_diram)


def referral_percent() -> int:
    return get_int("referral_percent", settings.referral_percent)


# --------------------------------------------------- присмотр за кошельком


def autostop_after() -> int:
    return max(get_int("autostop_after", 3), 1)


async def note_delivery_ok(
    conn: aiosqlite.Connection, product_type: str, quantity: int
) -> None:
    """Учесть удачную выдачу: обнулить серию неудач и записать расход."""
    if get_int("fail_streak"):
        await set_value(conn, "fail_streak", "0")
    key = "stars_since_topup" if product_type == "stars" else "premium_since_topup"
    await set_value(conn, key, str(get_int(key) + quantity))


async def note_delivery_fail(conn: aiosqlite.Connection) -> int:
    """Учесть неудачу. Возвращает длину серии подряд идущих неудач."""
    streak = get_int("fail_streak") + 1
    await set_value(conn, "fail_streak", str(streak))
    return streak


async def autostop(conn: aiosqlite.Connection) -> None:
    """Погасить продажу: дальше клиенты платили бы и получали возврат."""
    await set_value(conn, "stars_enabled", "0")
    await set_value(conn, "premium_enabled", "0")
    await set_value(conn, "autostopped", "1")
    log.error("Продажа выключена автоматически: выдача не проходит подряд")


async def mark_topup(conn: aiosqlite.Connection, when: str) -> None:
    """Отметить пополнение кошелька и обнулить счётчики расхода."""
    await set_value(conn, "topup_at", when)
    await set_value(conn, "stars_since_topup", "0")
    await set_value(conn, "premium_since_topup", "0")
    await set_value(conn, "fail_streak", "0")
    if get_bool("autostopped"):
        await set_value(conn, "stars_enabled", "1")
        await set_value(conn, "premium_enabled", "1")
        await set_value(conn, "autostopped", "0")


def premium_costs() -> dict[int, int]:
    """Себестоимость Premium по срокам, в дирамах."""
    try:
        return {int(k): int(v) for k, v in json.loads(get("premium_costs")).items()}
    except (ValueError, TypeError, AttributeError):
        return {}


async def save_premium_costs(conn: aiosqlite.Connection, costs: dict[int, int]) -> None:
    await set_value(conn, "premium_costs", json.dumps(
        {str(k): int(v) for k, v in costs.items()}
    ))


def cost_of(product_type: str, quantity: int) -> int:
    """Во сколько нам обходится заказ. 0 — себестоимость неизвестна."""
    if product_type == "stars":
        return star_cost() * quantity
    return premium_costs().get(quantity, 0)


def auto_price_on() -> bool:
    return get_bool("auto_price")

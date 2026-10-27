"""Валюты СНГ — только показ цен. Платят посетители из этих стран криптой (USDT), внутри всё в долларах.

Курс — рыночный (раз в сутки) плюс MARGIN_PCT и округление вверх: цена в местной валюте
никогда не ниже настоящей, на курсе мы не теряем. Таджикистан — как раньше: сомони по курсу оплат.
"""

from __future__ import annotations

import json
import logging
import time
from decimal import ROUND_UP, Decimal, InvalidOperation
from typing import Any

from . import cache, db
from .config import Config

log = logging.getLogger("donatix.fx")

# код: (страна, знак, знаков после запятой, примерный курс за $1 — пока не скачали свежий)
CURRENCIES: dict[str, tuple[str, str, int, str]] = {
    "RUB": ("RU", "₽", 0, "95"),
    "KZT": ("KZ", "₸", 0, "520"),
    "UZS": ("UZ", "сум", 0, "12800"),
    "KGS": ("KG", "сом", 0, "87"),
    "BYN": ("BY", "Br", 2, "3.3"),
    "AZN": ("AZ", "₼", 2, "1.7"),
    "AMD": ("AM", "֏", 0, "390"),
    "MDL": ("MD", "L", 2, "18"),
    "TMT": ("TM", "m", 2, "3.5"),
}
BY_COUNTRY = {v[0]: k for k, v in CURRENCIES.items()}
# Выбор в настройках: сомони и доллар — всем, плюс валюты СНГ. Код: (название, страна)
NAMES: dict[str, tuple[str, str]] = {
    "TJS": ("Сомони", "Таджикистан"),
    "USD": ("Доллар США", "США"),
    "RUB": ("Российский рубль", "Россия"),
    "KZT": ("Казахстанский тенге", "Казахстан"),
    "UZS": ("Узбекский сум", "Узбекистан"),
    "KGS": ("Киргизский сом", "Кыргызстан"),
    "BYN": ("Белорусский рубль", "Беларусь"),
    "AZN": ("Азербайджанский манат", "Азербайджан"),
    "AMD": ("Армянский драм", "Армения"),
    "MDL": ("Молдавский лей", "Молдова"),
    "TMT": ("Туркменский манат", "Туркменистан"),
}
ALL = tuple(NAMES)
MARGIN_PCT = Decimal("3")       # запас на курс и комиссию обмена — показанная цена не ниже настоящей
KEY = "fx.rates"
MAX_AGE = 86400
URL = "https://open.er-api.com/v6/latest/USD"


def for_country(cc: str) -> str:
    return BY_COUNTRY.get(cc or "", "")


def allowed(cc: str) -> tuple[str, ...]:
    """Валюта по умолчанию и быстрые кнопки в шапке: из Таджикистана (или пока страну не знаем) — сомони,
    из СНГ — его валюта и доллар, из остальных стран — доллар."""
    if cc in ("", "TJ"):
        return ("TJS", "USD")
    local = for_country(cc)
    return (local, "USD") if local else ("USD",)


def choose(cc: str, chosen: str) -> tuple[str, tuple[str, ...]]:
    """Валюта показа и быстрые кнопки. Не выбрал сам — по стране; выбрать можно любую из ALL
    (в настройках кабинета и в шапке админки) — тогда и она среди быстрых кнопок."""
    quick = allowed(cc)
    code = chosen if chosen in ALL else quick[0]
    return code, quick if code in quick else (code, *quick)


def options() -> list[dict[str, str]]:
    """Список для выбора валюты: код, название, страна и знак."""
    return [{"code": code, "name": name, "country": country, "sym": badge(code)}
            for code, (name, country) in NAMES.items()]


def badge(code: str) -> str:
    return {"TJS": "с.", "USD": "$"}.get(code) or symbol(code)


def symbol(code: str) -> str:
    return CURRENCIES[code][1] if code in CURRENCIES else ""


def digits(code: str) -> int:
    return CURRENCIES[code][2] if code in CURRENCIES else 2


def _stored(conn) -> dict[str, Any]:
    try:
        return json.loads(db.get_setting(conn, KEY) or "{}")
    except ValueError:
        return {}


def market(conn) -> dict[str, Decimal]:
    data = _stored(conn).get("rates", {})
    out = {}
    for code, (_, _, _, default) in CURRENCIES.items():
        try:
            out[code] = Decimal(str(data.get(code) or default))
        except InvalidOperation:
            out[code] = Decimal(default)
    return out


def rate(config: Config, code: str) -> Decimal | None:
    """Курс показа: местная валюта за $1 с запасом MARGIN_PCT. Кеш на минуту."""
    if code not in CURRENCIES:
        return None

    def load():
        pool = db.pool(config.db_path)
        c = pool.acquire()
        try:
            return market(c)
        finally:
            pool.release(c)
    m = cache.get_or_set("fx:rates", 60, load)
    return (m[code] * (1 + MARGIN_PCT / 100)).quantize(Decimal("0.0001"), rounding=ROUND_UP)


def refresh(conn, *, force: bool = False) -> bool:
    """Раз в сутки — рыночные курсы всех валют СНГ одним запросом."""
    if not force and time.time() - float(_stored(conn).get("ts") or 0) < MAX_AGE:
        return False
    import httpx
    try:
        r = httpx.get(URL, timeout=8, follow_redirects=True, headers={"User-Agent": "Donatix/1"})
        r.raise_for_status()
        data = r.json()
        got = {c: str(data["rates"][c]) for c in CURRENCIES if c in data.get("rates", {})}
    except Exception as exc:  # noqa: BLE001 — нет сети: остаются прошлые курсы
        log.warning("курсы СНГ не обновлены: %s", exc.__class__.__name__)
        return False
    if not got:
        return False
    db.set_setting(conn, KEY, json.dumps({"ts": time.time(), "rates": got}))
    cache.clear("fx:")
    return True


def fmt(usd: Decimal, code: str, rate_: Decimal) -> str:
    """$1.2345 → «15 900 сум» / «3.95 Br». Вверх, чтобы показанная цена не была ниже настоящей."""
    d = digits(code)
    value = (Decimal(usd) * rate_).quantize(Decimal(1).scaleb(-d), rounding=ROUND_UP)
    whole, _, frac = f"{value:.{d}f}".partition(".")
    sign = "-" if whole.startswith("-") else ""
    whole = whole.lstrip("-")
    groups = []
    while whole:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    text = sign + " ".join(groups or ["0"]) + (f".{frac}" if frac else "")
    return f"{text} {symbol(code)}"

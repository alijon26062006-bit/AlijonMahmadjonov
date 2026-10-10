"""Виртуальные номера (5sim.net): номер на один СМС-код для регистрации в Telegram, WhatsApp и т.д.

Как работает:
1. Клиент выбирает сервис и страну — цены берём у 5sim (самый дешёвый оператор, где есть номера) + наша наценка.
2. «Купить» — списываем с баланса, покупаем у 5sim с maxPrice = цена, которую видел клиент (дороже 5sim не возьмёт).
3. Страница номера раз в несколько секунд спрашивает 5sim — пришёл ли код. Код пришёл — показываем крупно.
4. Код не пришёл (отмена, время вышло, номер «забанен») — деньги возвращаются на баланс сами.

Ключ — только в .env: DONATIX_FIVESIM_TOKEN (JWT из кабинета 5sim → API). Наценка — DONATIX_FIVESIM_MARKUP (25 %).
Цены 5sim — в валюте аккаунта; если аккаунт в рублях — DONATIX_FIVESIM_RUB_RATE (рублей за $1).
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from decimal import ROUND_CEILING, Decimal
from typing import Any

import httpx

from . import accounts, cache, db
from .config import Config

log = logging.getLogger(__name__)

BASE = "https://5sim.net/v1"
TIMEOUT = httpx.Timeout(20, connect=8)
FINAL = ("FINISHED", "CANCELED", "TIMEOUT", "BANNED")

# Сервисы, которые показываем (ключ 5sim → название). Потом можно добавить ещё.
SERVICES = {"telegram": "Telegram", "whatsapp": "WhatsApp"}
# Аренда номера на срок: все СМС за это время (любые сервисы). Отменить у 5sim нельзя — возврат только если не купился
RENT = {"3hours": "3 часа", "1day": "1 день", "10days": "10 дней", "1month": "1 месяц"}


def product_title(product: str) -> str:
    return f"Аренда на {RENT[product]}" if product in RENT else SERVICES.get(product, product)

# Названия стран по-русски — для частых; остальные — как у 5sim, с большой буквы
COUNTRIES_RU = {
    "tajikistan": "Таджикистан", "uzbekistan": "Узбекистан", "kazakhstan": "Казахстан", "kyrgyzstan": "Кыргызстан",
    "usa": "США", "england": "Англия", "india": "Индия", "indonesia": "Индонезия", "philippines": "Филиппины",
    "vietnam": "Вьетнам", "thailand": "Таиланд", "malaysia": "Малайзия", "brazil": "Бразилия", "mexico": "Мексика",
    "canada": "Канада", "germany": "Германия", "france": "Франция", "netherlands": "Нидерланды", "poland": "Польша",
    "spain": "Испания", "italy": "Италия", "portugal": "Португалия", "sweden": "Швеция", "finland": "Финляндия",
    "georgia": "Грузия", "armenia": "Армения", "azerbaijan": "Азербайджан", "moldova": "Молдова",
    "turkmenistan": "Туркменистан", "mongolia": "Монголия", "pakistan": "Пакистан", "bangladesh": "Бангладеш",
    "nigeria": "Нигерия", "kenya": "Кения", "egypt": "Египет", "southafrica": "ЮАР", "colombia": "Колумбия",
    "argentina": "Аргентина", "chile": "Чили", "peru": "Перу", "cambodia": "Камбоджа", "laos": "Лаос",
    "myanmar": "Мьянма", "nepal": "Непал", "srilanka": "Шри-Ланка", "estonia": "Эстония", "latvia": "Латвия",
    "lithuania": "Литва", "romania": "Румыния", "bulgaria": "Болгария", "czech": "Чехия", "hongkong": "Гонконг",
    "israel": "Израиль", "saudiarabia": "Саудовская Аравия", "morocco": "Марокко", "ghana": "Гана",
}
STATUS_RU = {"PENDING": "Ждём СМС", "RECEIVED": "Код пришёл", "FINISHED": "Готово", "CANCELED": "Отменён",
             "TIMEOUT": "Время вышло", "BANNED": "Номер не подошёл", "FAILED": "Не удалось купить"}


# ISO-код страны — для флага. Основной источник — список стран 5sim (/guest/countries), это — запас
ISO = {"tajikistan": "tj", "uzbekistan": "uz", "kazakhstan": "kz", "kyrgyzstan": "kg", "usa": "us", "england": "gb",
       "india": "in", "indonesia": "id", "philippines": "ph", "vietnam": "vn", "thailand": "th", "malaysia": "my",
       "brazil": "br", "mexico": "mx", "canada": "ca", "germany": "de", "france": "fr", "netherlands": "nl",
       "poland": "pl", "spain": "es", "italy": "it", "portugal": "pt", "sweden": "se", "finland": "fi",
       "georgia": "ge", "armenia": "am", "azerbaijan": "az", "moldova": "md", "turkmenistan": "tm", "mongolia": "mn",
       "pakistan": "pk", "bangladesh": "bd", "nigeria": "ng", "kenya": "ke", "egypt": "eg", "southafrica": "za",
       "colombia": "co", "argentina": "ar", "chile": "cl", "peru": "pe", "cambodia": "kh", "laos": "la",
       "nepal": "np", "srilanka": "lk", "estonia": "ee", "latvia": "lv", "lithuania": "lt", "romania": "ro",
       "bulgaria": "bg", "czech": "cz", "hongkong": "hk", "israel": "il", "saudiarabia": "sa", "morocco": "ma",
       "ghana": "gh", "ukraine": "ua", "russia": "ru", "turkey": "tr", "china": "cn", "japan": "jp"}


def _countries(config: Config) -> dict[str, Any]:
    """Список стран 5sim (ISO, операторы и что они умеют: activation / hosting) — раз в сутки."""
    def load() -> dict[str, Any]:
        try:
            data = _get(config, "/guest/countries")
            return data if isinstance(data, dict) else {}
        except FiveSimError as exc:
            log.info("5sim: список стран не загрузился: %s", exc)
            return {}
    return cache.get_or_set("5sim:countries", 86400, load)


def _iso_map(config: Config) -> dict[str, str]:
    """Название страны у 5sim → ISO из их же списка стран; не загрузилось — запасной список."""
    out = dict(ISO)
    for name, info in _countries(config).items():
        iso = next(iter((info or {}).get("iso") or {}), "") if isinstance(info, dict) else ""
        if len(iso) == 2:
            out[name] = iso.lower()
    return out


def flag(config: Config, country: str) -> str:
    """Флаг-эмодзи по ISO-коду (🇹🇯). Нет кода — глобус."""
    iso = _iso_map(config).get(country, "") if config.fivesim_token else ISO.get(country, "")
    if len(iso) != 2 or not iso.isalpha():
        return "🌐"
    return "".join(chr(0x1F1E6 + ord(c) - ord("a")) for c in iso.lower())


class FiveSimError(Exception):
    pass


def enabled(config: Config) -> bool:
    return bool(config.fivesim_token)


def country_title(name: str) -> str:
    return COUNTRIES_RU.get(name, name[:1].upper() + name[1:])


def _client(config: Config) -> httpx.Client:
    return httpx.Client(base_url=BASE, timeout=TIMEOUT,
                        headers={"Authorization": f"Bearer {config.fivesim_token}", "Accept": "application/json"})


def _get(config: Config, path: str, params: dict | None = None) -> Any:
    try:
        with _client(config) as c:
            r = c.get(path, params=params)
    except httpx.HTTPError as exc:
        raise FiveSimError(f"5sim не отвечает ({exc.__class__.__name__})") from None
    text = r.text.strip()
    if r.status_code == 401:
        raise FiveSimError("5sim: неверный или просроченный токен")
    if r.status_code >= 400 or not text.startswith(("{", "[")):
        # 5sim пишет ошибки простым текстом: «no free phones», «not enough user balance»…
        raise FiveSimError(text[:120] or f"5sim: HTTP {r.status_code}")
    return r.json()


# ── Деньги ────────────────────────────────────────────────


def to_usd(config: Config, cost: Any) -> Decimal:
    value = Decimal(str(cost))
    rate = Decimal(str(config.fivesim_rub_rate or 0))
    return value / rate if rate > 0 else value


def sale_micro(config: Config, cost: Any) -> int:
    """Цена клиенту в микро-долларах: цена 5sim + наценка, вверх до цента."""
    usd = to_usd(config, cost) * (1 + Decimal(str(config.fivesim_markup)) / 100)
    return int(usd.quantize(Decimal("0.01"), rounding=ROUND_CEILING) * 10_000)


def _country_product(config: Config, country: str, product: str) -> dict[str, Any] | None:
    """Цена товара в стране у любого оператора: /guest/products/{страна}/any → {"1day": {"Qty", "Price"}}."""
    item = (_get(config, f"/guest/products/{country}/any") or {}).get(product)
    if not isinstance(item, dict) or not item.get("Qty") or not item.get("Price"):
        return None
    return {"cost": item["Price"], "count": item["Qty"]}


def _rent_countries(config: Config) -> list[str]:
    """Страны, где у 5sim есть операторы с арендой (hosting); не знаем — частые страны из нашего списка."""
    out = [name for name, info in _countries(config).items() if isinstance(info, dict) and any(
        isinstance(v, dict) and "hosting" in v for v in info.values())]
    return out or list(COUNTRIES_RU)


def _prices_by_country(config: Config, product: str, countries: list[str]) -> list[dict[str, Any]]:
    """Запасной путь (аренда, или 5sim не дал цены разом): по странам параллельно, не больше 60 стран."""
    from concurrent.futures import ThreadPoolExecutor

    def one(country: str) -> dict[str, Any] | None:
        try:
            got = _country_product(config, country, product)
        except FiveSimError:
            return None
        if got is None:
            return None
        return {"country": country, "title": country_title(country), "flag": flag(config, country),
                "cost": got["cost"], "count": got["count"], "rate": 0, "operator": "any",
                "price_micro": sale_micro(config, got["cost"])}
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = [r for r in pool.map(one, countries[:60]) if r]
    return sorted(rows, key=lambda x: (x["price_micro"], -x["count"]))


def prices(config: Config, service: str) -> list[dict[str, Any]]:
    """Страны с номерами для сервиса: самая дешёвая цена, где номера есть, и сколько их. Кэш 20 секунд."""
    if service in RENT:   # сроки аренды /guest/prices не принимает («product is incorrect») — по странам
        return cache.get_or_set(f"5sim:prices:{service}", 60,
                                lambda: _prices_by_country(config, service, _rent_countries(config)))

    def load() -> list[dict[str, Any]]:
        try:
            data = _get(config, "/guest/prices", {"product": service}).get(service) or {}
        except FiveSimError as exc:
            if "incorrect" not in str(exc).lower():
                raise
            return _prices_by_country(config, service, list(COUNTRIES_RU))
        out = []
        for country, ops in data.items():
            live = [o for o in ops.values() if isinstance(o, dict) and o.get("count", 0) > 0 and o.get("cost")]
            if not live:
                continue
            best = min(live, key=lambda o: o["cost"])
            rate = max((o.get("rate") or 0) for o in live)
            out.append({"country": country, "title": country_title(country), "flag": flag(config, country),
                        "cost": best["cost"],
                        "count": sum(o["count"] for o in live), "rate": rate,
                        "price_micro": sale_micro(config, best["cost"])})
        return sorted(out, key=lambda x: (x["price_micro"], -x["count"]))
    return cache.get_or_set(f"5sim:prices:{service}", 20, load)   # наличие номеров меняется быстро — свежее раз в 20 с


def quote(config: Config, service: str, country: str) -> dict[str, Any] | None:
    """Свежая цена перед покупкой (не из кэша) — чтобы клиент заплатил за то, что купим."""
    if service in RENT:
        got = _country_product(config, country, service)
        return None if got is None else {"cost": got["cost"], "operator": "any",
                                         "price_micro": sale_micro(config, got["cost"])}
    data = (_get(config, "/guest/prices", {"country": country, "product": service}).get(country) or {}).get(service) or {}
    live = [o for o in data.values() if isinstance(o, dict) and o.get("count", 0) > 0 and o.get("cost")]
    if not live:
        return None
    operator, best = min(((name, o) for name, o in data.items() if o in live), key=lambda x: x[1]["cost"])
    return {"cost": best["cost"], "operator": operator, "price_micro": sale_micro(config, best["cost"])}


def balance(config: Config) -> Any:
    return cache.get_or_set("5sim:balance", 60, lambda: _get(config, "/user/profile").get("balance"))


# ── Заказы ────────────────────────────────────────────────


def buy(conn: sqlite3.Connection, config: Config, user: sqlite3.Row, service: str, country: str) -> int:
    """Купить номер. Вернёт id нашего заказа. Не получилось — деньги не списаны (или сразу возвращены)."""
    if service not in SERVICES:   # аренду не продаём: у 5sim нет свободных номеров
        raise FiveSimError("Выберите сервис.")
    rent = service in RENT
    q = quote(config, service, country)
    if q is None:
        raise FiveSimError("В этой стране сейчас нет номеров — выберите другую.")
    title = f"{product_title(service)} · {country_title(country)}"
    with db.tx(conn):
        try:
            accounts.post_ledger(conn, user["id"], -q["price_micro"], f"Виртуальный номер {title}")
        except accounts.InsufficientBalance:
            raise FiveSimError("На балансе не хватает денег — пополните баланс.") from None
        vid = int(conn.execute(
            "INSERT INTO vnumbers (user_id, service, country, price_micro, cost, status, kind, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?, ?)",
            (user["id"], service, country, q["price_micro"], str(q["cost"]), "hosting" if rent else "activation",
             db.now(), db.now())).lastrowid)
    try:
        if rent:   # аренда — у самого дешёвого оператора из свежей цены: заплатим ровно то, что видел клиент
            res = _get(config, f"/user/buy/hosting/{country}/{q['operator']}/{service}")
        else:
            res = _get(config, f"/user/buy/activation/{country}/any/{service}", {"maxPrice": q["cost"]})
    except FiveSimError as exc:
        _refund(conn, vid, f"не удалось купить: {exc}", status="FAILED")
        text = str(exc).lower()
        if "no free phones" in text:
            raise FiveSimError("Номера в этой стране только что закончились — выберите другую.") from None
        if "not enough" in text:
            log.warning("5sim: на балансе поставщика не хватает денег")
            raise FiveSimError("Сервис временно недоступен — деньги вернулись на баланс.") from None
        raise FiveSimError("Не получилось купить номер — деньги вернулись на баланс. Попробуйте другую страну.") from None
    conn.execute("UPDATE vnumbers SET ext_id = ?, phone = ?, operator = ?, status = ?, expires = ?, updated_at = ? "
                 "WHERE id = ?", (str(res.get("id")), res.get("phone") or "", res.get("operator") or "",
                                  res.get("status") or "PENDING", res.get("expires") or "", db.now(), vid))
    return vid


def _refund(conn: sqlite3.Connection, vid: int, why: str, status: str) -> bool:
    """Вернуть деньги один раз (refunded 0 → 1 в той же транзакции)."""
    with db.tx(conn):
        v = conn.execute("SELECT * FROM vnumbers WHERE id = ? AND refunded = 0", (vid,)).fetchone()
        if v is None:
            return False
        conn.execute("UPDATE vnumbers SET refunded = 1, status = ?, note = ?, updated_at = ? WHERE id = ?",
                     (status, why[:200], db.now(), vid))
        accounts.post_ledger(conn, v["user_id"], v["price_micro"],
                             f"Возврат: виртуальный номер {product_title(v['service'])} — {why[:80]}")
    from .notify import notify
    notify(conn, None, v["user_id"], f"Номер {v['phone'] or ''} — код не пришёл, деньги вернулись на баланс.",
           f"/panel/numbers/{vid}")
    return True


def refresh(conn: sqlite3.Connection, config: Config, vid: int) -> sqlite3.Row:
    """Спросить 5sim о заказе: пришёл ли код, не вышло ли время. Код не пришёл и заказ закрыт — возврат."""
    v = conn.execute("SELECT * FROM vnumbers WHERE id = ?", (vid,)).fetchone()
    if v is None or not v["ext_id"] or v["status"] in FINAL + ("FAILED",):
        return v
    try:
        res = _get(config, f"/user/check/{v['ext_id']}")
    except FiveSimError as exc:
        log.info("5sim: проверка %s: %s", v["ext_id"], exc)
        return v
    status = res.get("status") or v["status"]
    sms = [s for s in res.get("sms") or [] if isinstance(s, dict)]
    code = next((s.get("code") or s.get("text") for s in reversed(sms) if s.get("code") or s.get("text")), "") or v["code"]
    import json
    all_sms = [{"from": str(s.get("sender") or "")[:60], "text": str(s.get("text") or "")[:500],
                "code": str(s.get("code") or "")[:40], "at": str(s.get("date") or s.get("created_at") or "")[:30]}
               for s in sms][-50:]
    conn.execute("UPDATE vnumbers SET status = ?, code = ?, sms_text = ?, sms_json = ?, updated_at = ? WHERE id = ?",
                 (status, code or "", (sms[-1].get("text") or "")[:500] if sms else v["sms_text"],
                  json.dumps(all_sms, ensure_ascii=False) if sms else v["sms_json"], db.now(), vid))
    # Аренду 5sim не возвращает — у неё деньги не возвращаем (кроме неудачной покупки, см. buy)
    if v["kind"] != "hosting" and status in ("CANCELED", "TIMEOUT", "BANNED") and not code:
        _refund(conn, vid, STATUS_RU.get(status, status).lower(), status)
    return conn.execute("SELECT * FROM vnumbers WHERE id = ?", (vid,)).fetchone()


def cancel(conn: sqlite3.Connection, config: Config, vid: int, user_id: int) -> None:
    v = conn.execute("SELECT * FROM vnumbers WHERE id = ? AND user_id = ?", (vid, user_id)).fetchone()
    if v is None:
        raise FiveSimError("Номер не найден.")
    if v["kind"] == "hosting":
        raise FiveSimError("Аренду отменить нельзя — номер ваш до конца срока.")
    if v["code"]:
        raise FiveSimError("Код уже пришёл — отменить нельзя.")
    if v["status"] in FINAL + ("FAILED",):
        raise FiveSimError("Заказ уже закрыт.")
    try:
        _get(config, f"/user/cancel/{v['ext_id']}")
    except FiveSimError as exc:
        raise FiveSimError(f"5sim не дал отменить: {exc}. Попробуйте через минуту.") from None
    _refund(conn, vid, "отменён клиентом", "CANCELED")


def watch(conn: sqlite3.Connection, config: Config) -> None:
    """Воркер: открытые заказы — раз в ~20 с (клиент мог закрыть страницу). Время вышло — возврат."""
    if not enabled(config):
        return
    for v in conn.execute("SELECT id FROM vnumbers WHERE status IN ('PENDING', 'RECEIVED') AND ext_id IS NOT NULL "
                          "AND updated_at < ? LIMIT 30", (_ago(15),)).fetchall():
        refresh(conn, config, v["id"])


def _ago(seconds: int) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%S")


_lock = threading.Lock()
_last = {"at": 0.0}


def maybe_watch(conn: sqlite3.Connection, config: Config) -> None:
    with _lock:
        if time.monotonic() - _last["at"] < 20:
            return
        _last["at"] = time.monotonic()
    watch(conn, config)

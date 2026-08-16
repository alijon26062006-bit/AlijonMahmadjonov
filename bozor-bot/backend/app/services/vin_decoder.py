"""Расшифровка VIN по открытой базе NHTSA (США).

Государственный реестр, бесплатный и без ключа. Отдаёт марку, модель, год,
кузов и двигатель. Знает машины, продававшиеся в США: Camry, Corolla, Accord
и прочее, что и ездит по Таджикистану. Праворульные с внутреннего рынка Японии
в нём отсутствуют — там вообще не VIN, а номер кузова, и публичной базы по ним
не существует.

База не отвечает на вопрос «угнана ли машина» — только расшифровывает номер.
Польза в другом: продавец пишет одно, номер говорит другое — это видит
модератор.

Сеть здесь вспомогательная. Любой сбой, таймаут или выключенная настройка
означают «сведений нет» — мастер идёт дальше, объявление не теряется.
"""
import json
import logging

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

CACHE_PREFIX = "vin:"
CACHE_TTL = 60 * 60 * 24 * 30      # VIN расшифровывается всегда одинаково

_shared = None


def _cache():
    """Общий клиент Redis, если вызывающий свой не передал: расшифровка
    из мастера и из проверок модератора попадает в один кэш."""
    global _shared
    if _shared is None:
        try:
            from redis.asyncio import Redis
            _shared = Redis.from_url(get_settings().redis_url)
        except Exception:
            _shared = False        # Redis недоступен — работаем без кэша
    return _shared or None


def _clean(value: str | None) -> str | None:
    """У NHTSA пустое поле приходит как "", "Not Applicable" или None."""
    if not value:
        return None
    v = value.strip()
    if not v or v.lower() in ("not applicable", "unknown", "n/a"):
        return None
    return v


def _shape(raw: dict) -> dict | None:
    """Из полусотни полей ответа берём то, что показываем человеку."""
    out = {
        "make": _clean(raw.get("Make")),
        "model": _clean(raw.get("Model")),
        "year": _clean(raw.get("ModelYear")),
        "body": _clean(raw.get("BodyClass")),
        "fuel": _clean(raw.get("FuelTypePrimary")),
        "engine_l": _clean(raw.get("DisplacementL")),
        "plant": _clean(raw.get("PlantCountry")),
    }
    if not out["make"] and not out["model"]:
        return None                 # база номер не узнала
    if out["year"] and out["year"].isdigit():
        out["year"] = int(out["year"])
    else:
        out["year"] = None
    if out["engine_l"]:
        try:                        # "2.5000" → "2.5"
            out["engine_l"] = f'{float(out["engine_l"]):.1f}'
        except ValueError:
            out["engine_l"] = None
    return {k: v for k, v in out.items() if v is not None}


async def decode(vin: str, redis=None) -> dict | None:
    """Возвращает сведения о машине либо None, если узнать не удалось."""
    s = get_settings()
    if not s.vin_decode_enabled:
        return None
    vin = vin.strip().upper()
    if len(vin) != 17:
        return None
    if redis is None:
        redis = _cache()

    key = CACHE_PREFIX + vin
    if redis is not None:
        try:
            hit = await redis.get(key)
            if hit is not None:
                hit = hit.decode() if isinstance(hit, bytes) else hit
                # "-" — запомненный отрицательный ответ, чтобы не ходить впустую
                return None if hit == "-" else json.loads(hit)
        except Exception:
            pass                    # Redis лёг — просто спросим базу

    url = f"{s.vin_api_url.rstrip('/')}/{vin}?format=json"
    try:
        async with httpx.AsyncClient(timeout=s.vin_api_timeout) as client:
            r = await client.get(url)
            r.raise_for_status()
            results = r.json().get("Results") or []
    except Exception as e:
        log.info("VIN %s: база не ответила (%s)", vin, type(e).__name__)
        return None

    info = _shape(results[0]) if results else None
    if redis is not None:
        try:
            await redis.set(key, json.dumps(info, ensure_ascii=False) if info else "-",
                            ex=CACHE_TTL)
        except Exception:
            pass
    return info


def summary(info: dict | None) -> str | None:
    """Одна строка для мастера и карточки модератора."""
    if not info:
        return None
    parts = [str(info[k]) for k in ("year", "make", "model") if info.get(k)]
    line = " ".join(parts)
    tail = []
    if info.get("engine_l"):
        tail.append(f'{info["engine_l"]} л')
    if info.get("body"):
        tail.append(info["body"])
    if tail:
        line = f"{line} ({', '.join(tail)})" if line else ", ".join(tail)
    return line or None


def mismatch(info: dict | None, declared_brand: str | None,
             declared_year: int | None) -> list[str]:
    """Расхождения между тем, что написал продавец, и тем, что говорит номер.

    Сравниваем мягко: база пишет «TOYOTA», продавец — «Toyota», это одно и то
    же. Модель не сравниваем вовсе: «Camry» против «Camry Hybrid» дало бы
    ложную тревогу на каждом втором объявлении.
    """
    out: list[str] = []
    if not info:
        return out
    if declared_brand and info.get("make"):
        a = declared_brand.strip().lower()
        b = info["make"].strip().lower()
        if a not in b and b not in a:
            out.append(f'марка: указана «{declared_brand}», по VIN — «{info["make"]}»')
    if declared_year and info.get("year") and abs(int(declared_year) - info["year"]) > 1:
        out.append(f'год: указан {declared_year}, по VIN — {info["year"]}')
    return out

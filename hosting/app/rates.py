"""Курс валюты для пополнения: сколько сомони (или другой валюты) перевести за 1 доллар баланса.

Если в Настройках указан свой курс — используется он. Иначе курс берётся с open.er-api.com
(бесплатно, без ключа) и кэшируется на 6 часов. Последний полученный курс сохраняется в базе
и используется, если сервис временно недоступен.
"""
from __future__ import annotations

import json
import logging
import threading
import time

import httpx

from .db import Database

log = logging.getLogger("hosting.rates")
CACHE_SEC = 6 * 3600
CURRENCY_NAMES = {"TJS": "сомони", "UZS": "сум", "KZT": "тенге", "RUB": "руб.", "USD": "$", "EUR": "€", "KGS": "сом"}


class Rates:
    def __init__(self, db: Database, fetch=None):
        self.db = db
        self._lock = threading.Lock()
        self._mem: dict[tuple[str, str], tuple[float, float]] = {}
        self.fetch = fetch or self._fetch_open_er_api

    @staticmethod
    def _fetch_open_er_api(base: str, quote: str) -> float:
        r = httpx.get(f"https://open.er-api.com/v6/latest/{base}", timeout=10)
        r.raise_for_status()
        data = r.json()
        return float(data["rates"][quote])

    def get(self, base: str, quote: str, manual: float = 0.0) -> dict | None:
        """{"rate": 10.95, "source": "manual|auto|saved", "updated_at": ts} или None, если курса нет."""
        if base == quote:
            return {"rate": 1.0, "source": "same", "updated_at": int(time.time())}
        if manual and manual > 0:
            return {"rate": float(manual), "source": "manual", "updated_at": None}
        key = (base, quote)
        with self._lock:
            hit = self._mem.get(key)
            if hit and time.time() - hit[1] < CACHE_SEC:
                return {"rate": hit[0], "source": "auto", "updated_at": int(hit[1])}
        try:
            rate = self.fetch(base, quote)
            if not rate or rate <= 0:
                raise ValueError("пустой курс")
            now = time.time()
            with self._lock:
                self._mem[key] = (rate, now)
            self.db.set_setting(f"rate:{base}:{quote}", json.dumps({"rate": rate, "at": int(now)}))
            return {"rate": rate, "source": "auto", "updated_at": int(now)}
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as e:
            log.warning("rate %s/%s: %s", base, quote, e)
            saved = self.db.get_setting(f"rate:{base}:{quote}")
            if saved:
                d = json.loads(saved)
                return {"rate": float(d["rate"]), "source": "saved", "updated_at": d["at"]}
            return None

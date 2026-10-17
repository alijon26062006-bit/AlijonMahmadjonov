"""Страна посетителя по IP — без чужих сервисов на каждый запрос.

Раз в месяц воркер скачивает бесплатную базу DB-IP «country lite» (CSV, лицензия CC BY 4.0)
и оставляет в ней только страны СНГ — файл маленький, поиск — двоичный, за микросекунды.
Нет файла или адрес не найден — страна неизвестна (""), сайт работает как раньше: сомони.
"""

from __future__ import annotations

import bisect
import csv
import gzip
import io
import ipaddress
import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import Config

log = logging.getLogger("donatix.geo")

# Таджикистан и СНГ (плюс соседи, откуда тоже приходят игроки)
COUNTRIES = ("TJ", "RU", "KZ", "UZ", "KG", "BY", "AZ", "AM", "MD", "TM")
URL = "https://download.db-ip.com/free/dbip-country-lite-{ym}.csv.gz"
MAX_AGE_DAYS = 25

_lock = threading.Lock()
_cache: dict[str, Any] = {"path": None, "mtime": None, "v4": ([], []), "v6": ([], [])}


def path(config: Config) -> Path:
    return Path(config.db_path).parent / "geo_cis.json"


def _load(config: Config) -> dict[str, Any]:
    p = path(config)
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return _cache
    if _cache["path"] == p and _cache["mtime"] == mtime:
        return _cache
    with _lock:
        try:
            data = json.loads(p.read_text())
        except (OSError, ValueError):
            return _cache
        for fam in ("v4", "v6"):
            rows = sorted(data.get(fam, []))
            _cache[fam] = ([int(r[0]) for r in rows], rows)
        _cache["path"], _cache["mtime"] = p, mtime
    return _cache


OTHER = "XX"   # база есть, а адреса в ней нет — страна не из СНГ


def ready(config: Config) -> bool:
    return bool(_load(config)["v4"][0])


def country(config: Config, ip: str | None) -> str:
    """Код страны (TJ, UZ, RU…), OTHER — не СНГ, "" — не знаем (нет базы, свой адрес)."""
    try:
        addr = ipaddress.ip_address((ip or "").strip())
    except ValueError:
        return ""
    if addr.is_private or addr.is_loopback:
        return ""
    starts, rows = _load(config)["v4" if addr.version == 4 else "v6"]
    n = int(addr)
    i = bisect.bisect_right(starts, n) - 1
    if i >= 0 and rows[i][0] <= n <= rows[i][1]:
        return str(rows[i][2])
    return OTHER if starts or ready(config) else ""


def build(csv_text: str) -> dict[str, list]:
    """Из CSV DB-IP (start,end,country) — только наши страны, диапазоны числами."""
    out: dict[str, list] = {"v4": [], "v6": []}
    for row in csv.reader(io.StringIO(csv_text)):
        if len(row) < 3 or row[2] not in COUNTRIES:
            continue
        try:
            a, b = ipaddress.ip_address(row[0]), ipaddress.ip_address(row[1])
        except ValueError:
            continue
        out["v4" if a.version == 4 else "v6"].append([int(a), int(b), row[2]])
    return out


def update(config: Config, *, force: bool = False) -> bool:
    """Скачать свежую базу, если файлу больше MAX_AGE_DAYS. True — обновили."""
    p = path(config)
    try:
        if not force and time.time() - p.stat().st_mtime < MAX_AGE_DAYS * 86400:
            return False
    except OSError:
        pass
    import httpx
    now = datetime.now(timezone.utc)
    months = [now.strftime("%Y-%m"), (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")]
    for ym in months:   # в начале месяца новой базы может ещё не быть — берём прошлую
        try:
            r = httpx.get(URL.format(ym=ym), timeout=60, follow_redirects=True, headers={"User-Agent": "Donatix/1"})
            r.raise_for_status()
            data = build(gzip.decompress(r.content).decode("utf-8", "replace"))
        except Exception as exc:  # noqa: BLE001 — нет сети или файла: попробуем прошлый месяц / в другой раз
            log.warning("база стран %s: %s", ym, exc.__class__.__name__)
            continue
        if not data["v4"]:
            continue
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.replace(p)
        log.info("база стран обновлена (%s): %d диапазонов", ym, len(data["v4"]) + len(data["v6"]))
        return True
    return False

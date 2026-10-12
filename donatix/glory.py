"""Glory для клана Free Fire (ffglory.pro): группа ботов набирает клану очки славы (glory).

Как работает:
1. Клиент выбирает регион сервера и вводит ID клана. Цена = цена кредита FFGlory (обычный или премиум регион)
   + наша наценка (DONATIX_FFGLORY_MARKUP, 25 %).
2. «Запустить» — списываем с баланса и запускаем группу у FFGlory (у них уходит 1 кредит).
   Не запустилась (нет кредитов, лимит, клан уже занят) — деньги сразу возвращаются.
3. Страница заказа — «прямой эфир»: раз в 15 секунд спрашиваем FFGlory, сколько очков у клана сейчас,
   название/уровень/участники клана, работает ли группа. Сколько набрано = очки сейчас − очки при запуске.
4. Группа остановилась (сама или клиент нажал «Остановить») — заказ закрыт. После запуска деньги не возвращаются.

Ключи — только в .env: DONATIX_FFGLORY_KEY (api_key аккаунта) и DONATIX_FFGLORY_MASTER (x-api-key).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Any

import httpx

from . import accounts, cache, db
from .config import Config

log = logging.getLogger(__name__)

BASE = "https://ffglory.pro"
TIMEOUT = httpx.Timeout(20, connect=8)
OPEN = ("starting", "running")
STATUS_RU = {"starting": "Запускается", "running": "Работает", "stopped": "Остановлена", "failed": "Не запустилась"}


class GloryError(Exception):
    pass


def enabled(config: Config) -> bool:
    return bool(config.ffglory_key and config.ffglory_master)


def _call(config: Config, method: str, path: str, body: dict | None = None, auth: bool = True) -> Any:
    try:
        with httpx.Client(base_url=BASE, timeout=TIMEOUT) as c:
            r = c.request(method, path, params={"api_key": config.ffglory_key} if auth else None,
                          headers={"x-api-key": config.ffglory_master} if auth else None, json=body)
    except httpx.HTTPError as exc:
        raise GloryError(f"FFGlory не отвечает ({exc.__class__.__name__})") from None
    try:
        data = r.json()
    except ValueError:
        data = None
    if r.status_code >= 400:
        msg = (data or {}).get("error") if isinstance(data, dict) else ""
        err = GloryError(str(msg or r.text[:120] or f"HTTP {r.status_code}"))
        err.status = r.status_code   # type: ignore[attr-defined]
        raise err
    if data is None:
        raise GloryError("FFGlory ответил не JSON")
    return data


# ── Цены ────────────────────────────────────────────────


def pricing(config: Config) -> dict[str, Any]:
    """Регионы и цена кредита. Публичный запрос, кэш 10 минут."""
    return cache.get_or_set("glory:pricing", 600, lambda: _call(config, "GET", "/api/pricing", auth=False))


def sale_micro(config: Config, usd: Any) -> int:
    value = Decimal(str(usd)) * (1 + Decimal(str(config.ffglory_markup)) / 100)
    return int(value.quantize(Decimal("0.01"), rounding=ROUND_CEILING) * 10_000)


# Флаг региона: код FFGlory → страна (ISO). Регион из многих стран — значок континента.
_FLAG_ISO = {"IND": "IN", "NA": "US", "US": "US", "CIS": "RU", "RU": "RU", "EU": "EU", "UK": "GB", "SA": "SA"}
_FLAG_ZONE = {"ME": "🌍", "MENA": "🌍", "SAC": "🌎", "LATAM": "🌎", "SEA": "🌏", "ASIA": "🌏", "AF": "🌍"}


def flag(code: str) -> str:
    code = (code or "").strip().upper()
    if code in _FLAG_ZONE:
        return _FLAG_ZONE[code]
    iso = _FLAG_ISO.get(code, code)
    if len(iso) != 2 or not iso.isalpha():
        return "🌐"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso)


def price_micro(conn: sqlite3.Connection | None, config: Config, cost: Any) -> int:
    """Цена клиенту: одна цена в сомони для всех регионов (DONATIX_FFGLORY_PRICE_TJS, 20 с.) по курсу сайта;
    если не задана — цена кредита FFGlory + наценка."""
    tjs = Decimal(str(config.ffglory_price_tjs or 0))
    if tjs > 0 and conn is not None:
        from .payments import settings
        rate = Decimal(str(settings(conn, config)["tjs_rate"] or 0))
        if rate > 0:
            return int((tjs / rate * 10_000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return sale_micro(config, cost)


def regions(config: Config, conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
    """Включённые регионы с нашей ценой и флагом."""
    p = pricing(config)
    out = []
    for r in p.get("regions") or []:
        if not isinstance(r, dict) or not r.get("enabled") or not r.get("id"):
            continue
        tier = "premium" if r.get("tier") == "premium" else "basic"
        cost = p.get(f"{tier}_credit_usd")
        if cost is None:
            continue
        code = str(r.get("region_code") or r["id"])
        out.append({"id": str(r["id"]), "title": r.get("region_name") or str(r["id"]).upper(),
                    "code": code, "flag": flag(code), "tier": tier, "cost": cost,
                    "price_micro": price_micro(conn, config, cost)})
        out[-1]["loss"] = out[-1]["price_micro"] < int(Decimal(str(cost)) * 10_000)   # продаём дешевле, чем берёт FFGlory
    return sorted(out, key=lambda x: (x["tier"] != "basic", x["title"]))


# ── Разбор ответов (формат get-glory / get-clan-info в документации не описан — ищем по известным именам) ──

_GLORY_KEYS = ("glory", "total_glory", "current_glory", "clan_glory", "glory_points", "points", "score")


def _find(obj: Any, keys: tuple[str, ...], depth: int = 0) -> Any:
    if depth > 4:
        return None
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and obj[k] not in (None, "", [], {}):
                return obj[k]
        for v in obj.values():
            got = _find(v, keys, depth + 1)
            if got is not None:
                return got
    if isinstance(obj, list):
        for v in obj[:5]:
            got = _find(v, keys, depth + 1)
            if got is not None:
                return got
    return None


def parse_glory(resp: Any) -> int | None:
    if isinstance(resp, (int, float)) and not isinstance(resp, bool):
        return int(resp)
    val = _find(resp, _GLORY_KEYS)
    try:
        return int(float(str(val).replace(",", "").replace(" ", ""))) if val is not None else None
    except ValueError:
        return None


def parse_clan(resp: Any) -> dict[str, Any]:
    name = _find(resp, ("clan_name", "name", "clanName"))
    level = _find(resp, ("clan_level", "level", "clanLevel"))
    members = _find(resp, ("member_count", "members_count", "memberNum", "members"))
    if isinstance(members, list):
        members = len(members)
    cap = _find(resp, ("capacity", "max_members", "capacity_members", "maxMembers"))
    out = {"name": str(name)[:60] if isinstance(name, (str, int)) else "",
           "level": level if isinstance(level, (int, str)) else "",
           "members": members if isinstance(members, (int, str)) else "",
           "capacity": cap if isinstance(cap, (int, str)) else ""}
    return {k: v for k, v in out.items() if v not in ("", None)}


# ── Заказ ────────────────────────────────────────────────


def _clean_clan(clan_id: str) -> str:
    clan_id = "".join(ch for ch in (clan_id or "") if ch.isdigit())
    if not 5 <= len(clan_id) <= 15:
        raise GloryError("ID клана — только цифры (от 5 до 15). Его видно в игре: Клан → информация.")
    return clan_id


def buy(conn: sqlite3.Connection, config: Config, user: sqlite3.Row, region: str, clan_id: str) -> int:
    clan_id = _clean_clan(clan_id)
    try:
        reg = next((r for r in regions(config, conn) if r["id"] == region), None)
    except GloryError:
        raise GloryError("Сервис сейчас недоступен — попробуйте через минуту.") from None
    if reg is None:
        raise GloryError("Выберите регион сервера.")
    if conn.execute("SELECT 1 FROM glory_orders WHERE clan_id = ? AND status IN ('starting', 'running')",
                    (clan_id,)).fetchone():
        raise GloryError("Для этого клана уже работает группа — дождитесь, пока она закончит.")
    with db.tx(conn):
        try:
            accounts.post_ledger(conn, user["id"], -reg["price_micro"], f"Glory для клана {clan_id} ({reg['title']})")
        except accounts.InsufficientBalance:
            raise GloryError("На балансе не хватает денег — пополните баланс.") from None
        gid = int(conn.execute(
            "INSERT INTO glory_orders (user_id, region, tier, clan_id, price_micro, cost_usd, status, created_at, "
            "updated_at) VALUES (?, ?, ?, ?, ?, ?, 'starting', ?, ?)",
            (user["id"], reg["id"], reg["tier"], clan_id, reg["price_micro"], str(reg["cost"]), db.now(),
             db.now())).lastrowid)
    group_id, bots, err = "", 0, None
    try:
        res = _call(config, "POST", "/api/client/auto-clan-group", {"region": reg["id"], "clan_id": clan_id})
        group_id = str(_find(res, ("group_id", "groupId", "group")) or "")
        if group_id.startswith("{"):            # «group»: {...} — id внутри
            group_id = str(_find(_find(res, ("group",)), ("id", "group_id")) or "")
        bots = _find(res, ("bot_count", "bots", "container_count"))
        if not group_id:
            log.warning("FFGlory: запуск без group_id в ответе: %s", str(res)[:300])
    except GloryError as exc:
        err = exc
    if not group_id and getattr(err, "status", 0) not in (400, 401, 402):
        # Ответ не понят или оборвался, а группа могла запуститься — ищем её по ID клана, прежде чем возвращать деньги
        found = _group_by_clan(config, clan_id)
        if found:
            group_id = str(found.get("group_id"))
            bots = found.get("running_count") or found.get("container_count") or bots
    if not group_id:
        exc = err or GloryError("нет group_id в ответе")
        _refund(conn, gid, f"не запустилась: {exc}")
        code = getattr(exc, "status", 0)
        if code == 402:
            log.warning("FFGlory: на аккаунте закончились кредиты")
            raise GloryError("Сервис временно недоступен — деньги вернулись на баланс.") from None
        if code in (403, 409):
            raise GloryError("Для этого клана сейчас нельзя запустить ещё одну группу — деньги вернулись на "
                             "баланс. Попробуйте позже.") from None
        raise GloryError("Не получилось запустить — деньги вернулись на баланс. Проверьте ID клана и регион.") from None
    try:
        bots = int(bots or 0)
    except (TypeError, ValueError):
        bots = 0
    conn.execute("UPDATE glory_orders SET group_id = ?, bots = ?, status = 'running', updated_at = ? WHERE id = ?",
                 (group_id, bots, db.now(), gid))
    return gid


def _refund(conn: sqlite3.Connection, gid: int, why: str) -> bool:
    with db.tx(conn):
        g = conn.execute("SELECT * FROM glory_orders WHERE id = ? AND refunded = 0", (gid,)).fetchone()
        if g is None:
            return False
        conn.execute("UPDATE glory_orders SET refunded = 1, status = 'failed', note = ?, updated_at = ? WHERE id = ?",
                     (why[:200], db.now(), gid))
        accounts.post_ledger(conn, g["user_id"], g["price_micro"], f"Возврат: Glory для клана {g['clan_id']}")
    return True


def _group(config: Config, group_id: str) -> dict[str, Any] | None:
    groups = cache.get_or_set("glory:groups", 10, lambda: _call(config, "GET", "/api/client/my-groups"))
    if isinstance(groups, dict):
        groups = groups.get("groups") or []
    return next((g for g in groups or [] if isinstance(g, dict) and str(g.get("group_id")) == group_id), None)


def _group_by_clan(config: Config, clan_id: str) -> dict[str, Any] | None:
    """Работающая группа нашего аккаунта для этого клана (свежий список, без кэша)."""
    cache.clear("glory:groups")
    try:
        groups = _call(config, "GET", "/api/client/my-groups")
    except GloryError:
        return None
    if isinstance(groups, dict):
        groups = groups.get("groups") or []
    return next((g for g in groups or [] if isinstance(g, dict) and str(g.get("clan_id")) == clan_id
                 and str(g.get("status", "")).lower() in ("running", "starting", "pending")), None)


def refresh(conn: sqlite3.Connection, config: Config, gid: int) -> sqlite3.Row:
    """Свежие данные у FFGlory: статус группы, очки, клан. Не чаще раза в 10 с на заказ."""
    g = conn.execute("SELECT * FROM glory_orders WHERE id = ?", (gid,)).fetchone()
    if g is None or g["status"] not in OPEN or not g["group_id"]:
        return g
    if g["updated_at"] > _ago(10) and g["glory_start"] is not None:   # только что обновляли
        return g
    try:
        info = _group(config, g["group_id"])
        status = "running" if info and str(info.get("status", "")).lower() == "running" else "stopped"
        uptime = str((info or {}).get("uptime") or g["uptime"])[:20]
        bots = int((info or {}).get("running_count") or (info or {}).get("container_count") or g["bots"] or 0)
        glory, clan = g["glory"], json.loads(g["clan_json"] or "{}")
        if status == "running":
            act = lambda a: _call(config, "POST", "/api/client/group-action", {"action": a, "group_id": g["group_id"]})
            got = parse_glory(act("get-glory"))
            if got is not None:
                glory = got
            if not clan or not clan.get("name"):
                clan = parse_clan(act("get-clan-info")) or clan
    except GloryError as exc:
        log.info("FFGlory: обновление %s: %s", g["group_id"], exc)
        conn.execute("UPDATE glory_orders SET updated_at = ? WHERE id = ?", (db.now(), gid))
        return conn.execute("SELECT * FROM glory_orders WHERE id = ?", (gid,)).fetchone()
    start = g["glory_start"] if g["glory_start"] is not None else (glory if glory else None)
    conn.execute("UPDATE glory_orders SET status = ?, glory = ?, glory_start = ?, clan_json = ?, uptime = ?, bots = ?, "
                 "updated_at = ? WHERE id = ?", (status, glory or 0, start, json.dumps(clan, ensure_ascii=False),
                                                 uptime, bots, db.now(), gid))
    if status == "stopped" and g["status"] == "running":
        from .notify import notify
        notify(conn, None, g["user_id"], f"Glory для клана {g['clan_id']}: группа закончила работу.",
               f"/panel/glory/{gid}")
    return conn.execute("SELECT * FROM glory_orders WHERE id = ?", (gid,)).fetchone()


def stop(conn: sqlite3.Connection, config: Config, gid: int, user_id: int) -> None:
    g = conn.execute("SELECT * FROM glory_orders WHERE id = ? AND user_id = ?", (gid, user_id)).fetchone()
    if g is None:
        raise GloryError("Заказ не найден.")
    if g["status"] != "running":
        raise GloryError("Группа уже не работает.")
    _call(config, "POST", "/api/client/group-action", {"action": "stop", "group_id": g["group_id"]})
    cache.clear("glory:groups")
    conn.execute("UPDATE glory_orders SET status = 'stopped', note = 'остановлена клиентом', updated_at = ? "
                 "WHERE id = ?", (db.now(), gid))


def view(g: sqlite3.Row) -> dict[str, Any]:
    clan = json.loads(g["clan_json"] or "{}")
    start = g["glory_start"]
    return {"id": g["id"], "clan_id": g["clan_id"], "region": g["region"], "flag": flag(g["region"]),
            "status": g["status"],
            "status_title": STATUS_RU.get(g["status"], g["status"]), "open": g["status"] in OPEN,
            "glory": g["glory"], "farmed": max(0, g["glory"] - start) if start is not None else 0,
            "clan": clan, "uptime": g["uptime"], "bots": g["bots"], "price_micro": g["price_micro"],
            "refunded": bool(g["refunded"]), "note": g["note"], "created_at": g["created_at"]}


def _ago(seconds: int) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).strftime("%Y-%m-%dT%H:%M:%S")


def watch(conn: sqlite3.Connection, config: Config) -> None:
    """Воркер: работающие группы — раз в минуту (клиент мог закрыть страницу), чтобы знать, когда закончились."""
    if not enabled(config):
        return
    for g in conn.execute("SELECT id FROM glory_orders WHERE status = 'running' AND updated_at < ? LIMIT 20",
                          (_ago(60),)).fetchall():
        refresh(conn, config, g["id"])


_lock = threading.Lock()
_last = {"at": 0.0}


def maybe_watch(conn: sqlite3.Connection, config: Config) -> None:
    with _lock:
        if time.monotonic() - _last["at"] < 60:
            return
        _last["at"] = time.monotonic()
    watch(conn, config)


def relink(conn: sqlite3.Connection, config: Config, order_id: int | None = None) -> list[str]:
    """Заказы «Не запустилась», у которых группа на самом деле работает у FFGlory: привязать группу,
    чтобы были видны живые очки. Деньги второй раз НЕ списываются (клиенту их уже вернули)."""
    sql = "SELECT * FROM glory_orders WHERE status = 'failed'"
    args: tuple = ()
    if order_id:
        sql, args = sql + " AND id = ?", (order_id,)
    else:
        sql, args = sql + " AND created_at >= ?", (_ago(3 * 86400),)
    out = []
    for g in conn.execute(sql + " ORDER BY id DESC", args).fetchall():
        if conn.execute("SELECT 1 FROM glory_orders WHERE clan_id = ? AND status IN ('starting', 'running')",
                        (g["clan_id"],)).fetchone():
            out.append(f"#{g['id']} клан {g['clan_id']}: у клана уже есть работающий заказ — пропущен")
            continue
        found = _group_by_clan(config, g["clan_id"])
        if not found:
            out.append(f"#{g['id']} клан {g['clan_id']}: работающей группы у FFGlory нет")
            continue
        conn.execute("UPDATE glory_orders SET status = 'running', group_id = ?, bots = ?, glory_start = NULL, "
                     "note = 'группа привязана вручную, деньги повторно не списаны', updated_at = ? WHERE id = ?",
                     (str(found.get("group_id")), int(found.get("running_count") or found.get("container_count") or 0),
                      db.now(), g["id"]))
        refresh(conn, config, g["id"])
        out.append(f"#{g['id']} клан {g['clan_id']}: группа {found.get('group_id')} привязана ✓")
    return out

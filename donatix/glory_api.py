"""Боты для гильдии (Glory клана Free Fire) через API — для ботов и сайтов партнёров.

Одни и те же адреса в /api/v1/glory/… и /api/v2/glory/…:
  GET  /glory/regions              регионы, цена в USD и сомони
  POST /glory/orders               {"region": "bd", "clan_id": "3012345678"} — запустить, деньги списываются с баланса
  GET  /glory/orders               последние 50 запусков
  GET  /glory/orders/{id}          «прямой эфир»: статус, очки сейчас, набрано, клан (название, уровень, участники)
  POST /glory/orders/{id}/stop     остановить (деньги после запуска не возвращаются)
Не запустилось — деньги возвращаются сами, в ответе ошибка с кодом.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from . import glory
from .api import ApiError, _limit, api_user
from .config import Config
from .deps import get_config, get_conn
from .money import fmt

routers = [APIRouter(prefix="/api/v1/glory", tags=["Боты для гильдии"]),
           APIRouter(prefix="/api/v2/glory", tags=["Боты для гильдии"], include_in_schema=False)]


def _on(config: Config) -> None:
    if not glory.enabled(config):
        raise ApiError("Боты для гильдии сейчас недоступны.", "not_available", 503)


def _out(g) -> dict[str, Any]:
    v = glory.view(g)
    return {"id": f"gl-{v['id']}", "clan_id": v["clan_id"], "region": v["region"], "status": v["status"],
            "status_title": v["status_title"], "glory": v["glory"], "farmed": v["farmed"], "clan": v["clan"],
            "uptime": v["uptime"], "bots": v["bots"], "price_usd": fmt(v["price_micro"]), "refunded": v["refunded"],
            "created_at": v["created_at"]}


def _gid(order_id: str) -> int:
    raw = order_id.removeprefix("gl-")
    if not raw.isdigit() or len(raw) > 12:
        raise ApiError("Заказ не найден.", "not_found", 404)
    return int(raw)


class GloryIn(BaseModel):
    region: str = Field(max_length=20)
    clan_id: str = Field(max_length=30)


def _regions(request: Request, user=Depends(api_user), conn=Depends(get_conn), config: Config = Depends(get_config)):
    _on(config)
    _limit(request, "catalog", str(user["id"]))
    from .payments import settings
    rate = settings(conn, config)["tjs_rate"]
    try:
        items = glory.regions(config, conn)
    except glory.GloryError:
        raise ApiError("Сервис временно недоступен.", "temporarily_unavailable", 503) from None
    return {"ok": True, "items": [{"id": r["id"], "name": r["title"], "code": r["code"], "premium": r["tier"] == "premium",
                                   "price_usd": fmt(r["price_micro"]),
                                   "price_tjs": f"{r['price_micro'] / 10_000 * float(rate):.2f}"} for r in items]}


def _create(body: GloryIn, request: Request, user=Depends(api_user), conn=Depends(get_conn),
            config: Config = Depends(get_config)):
    _on(config)
    _limit(request, "orders", str(user["id"]))
    try:
        gid = glory.buy(conn, config, user, body.region.strip(), body.clan_id)
    except glory.GloryError as exc:
        text = str(exc)
        code = ("insufficient_balance" if "не хватает" in text else "invalid_clan_id" if "ID клана" in text
                else "invalid_region" if "регион" in text.lower() else "clan_busy" if "уже работает" in text
                else "launch_failed")
        raise ApiError(text, code, 402 if code == "insufficient_balance" else 409 if code == "clan_busy" else 400) from None
    g = conn.execute("SELECT * FROM glory_orders WHERE id = ?", (gid,)).fetchone()
    return {"ok": True, "order": _out(g)}


def _list(request: Request, user=Depends(api_user), conn=Depends(get_conn)):
    _limit(request, "status", str(user["id"]))
    rows = conn.execute("SELECT * FROM glory_orders WHERE user_id = ? ORDER BY id DESC LIMIT 50", (user["id"],))
    return {"ok": True, "items": [_out(g) for g in rows]}


def _one(order_id: str, request: Request, user=Depends(api_user), conn=Depends(get_conn),
         config: Config = Depends(get_config)):
    _limit(request, "status", str(user["id"]))
    gid = _gid(order_id[:20])
    g = conn.execute("SELECT * FROM glory_orders WHERE id = ? AND user_id = ?", (gid, user["id"])).fetchone()
    if g is None:
        raise ApiError("Заказ не найден.", "not_found", 404)
    if glory.enabled(config):
        g = glory.refresh(conn, config, gid)
    return {"ok": True, "order": _out(g)}


def _stop(order_id: str, request: Request, user=Depends(api_user), conn=Depends(get_conn),
          config: Config = Depends(get_config)):
    _on(config)
    _limit(request, "orders", str(user["id"]))
    gid = _gid(order_id[:20])
    try:
        glory.stop(conn, config, gid, user["id"])
    except glory.GloryError as exc:
        raise ApiError(str(exc), "not_found" if "не найден" in str(exc) else "invalid_state", 404 if "не найден" in str(exc) else 409) from None
    return {"ok": True, "order": _out(conn.execute("SELECT * FROM glory_orders WHERE id = ?", (gid,)).fetchone())}


for r in routers:
    r.add_api_route("/regions", _regions, methods=["GET"])
    r.add_api_route("/orders", _create, methods=["POST"], status_code=201)
    r.add_api_route("/orders", _list, methods=["GET"])
    r.add_api_route("/orders/{order_id}", _one, methods=["GET"])
    r.add_api_route("/orders/{order_id}/stop", _stop, methods=["POST"])

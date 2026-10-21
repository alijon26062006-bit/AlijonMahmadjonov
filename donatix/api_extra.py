"""API для партнёров: виртуальные номера (5sim) и Telegram-подарки — те же покупки, что на сайте.

Цены как на сайте (без отдельной наценки для API). Деньги списываются с баланса аккаунта, которому
принадлежит ключ. Не получилось купить — деньги не списаны или возвращены сразу, как и на сайте.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import db, fivesim, refs, tggifts
from .api import MAX_JSON, ApiError, _limit, api_user
from .config import Config
from .deps import get_config, get_conn
from .money import fmt

router = APIRouter(prefix="/api/v1", tags=["API"])


def _need(enabled: bool, what: str) -> None:
    if not enabled:
        raise ApiError(f"{what} сейчас недоступны.", "service_unavailable", 503)


def _number_error(exc: Exception) -> ApiError:
    text = str(exc)
    if "баланс" in text.lower() and "вернулись" not in text:
        return ApiError(text, "insufficient_balance", 402)
    return ApiError(text, "order_failed", 400)


def _number_view(v: sqlite3.Row) -> dict[str, Any]:
    return {"id": v["id"], "service": v["service"], "country": v["country"], "status": v["status"],
            "phone": v["phone"] or None, "code": v["code"] or None, "sms": v["sms_text"] or None,
            "price_usd": fmt(v["price_micro"]), "expires": v["expires"] or None,
            "refunded": bool(v["refunded"]), "note": v["note"] or None, "created_at": v["created_at"]}


def _own_number(conn: sqlite3.Connection, vid: int, user_id: int) -> sqlite3.Row:
    v = conn.execute("SELECT * FROM vnumbers WHERE id = ? AND user_id = ?", (vid, user_id)).fetchone()
    if v is None:
        raise ApiError("Заказ не найден.", "order_not_found", 404)
    return v


class NumberIn(BaseModel):
    service: str = Field(max_length=32)     # telegram, whatsapp, tiktok, instagram, google, facebook, discord, viber
    country: str = Field(max_length=40)     # код страны из GET /numbers/countries


@router.get("/numbers/services")
def number_services(request: Request, user=Depends(api_user), config: Config = Depends(get_config)) -> dict[str, Any]:
    _limit(request, "catalog", str(user["id"]))
    _need(fivesim.enabled(config), "Виртуальные номера")
    return {"ok": True, "items": [{"service": k, "title": v} for k, v in fivesim.SERVICES.items()]}


@router.get("/numbers/countries")
def number_countries(request: Request, service: str = Query(default="", max_length=32),
                     user=Depends(api_user), config: Config = Depends(get_config)) -> dict[str, Any]:
    _limit(request, "catalog", str(user["id"]))
    _need(fivesim.enabled(config), "Виртуальные номера")
    if service not in fivesim.SERVICES:
        raise ApiError("Укажите сервис из GET /numbers/services.", "unknown_service", 400)
    try:
        rows = fivesim.prices(config, service)
    except fivesim.FiveSimError:
        raise ApiError("Список стран сейчас не загрузился. Попробуйте через минуту.", "upstream_error", 503) from None
    return {"ok": True, "items": [{"country": r["country"], "title": r["title"], "flag": r["flag"],
                                   "price_usd": fmt(r["price_micro"]), "available": r["count"]} for r in rows]}


@router.post("/numbers/orders", status_code=201)
def number_buy(body: NumberIn, request: Request, user=Depends(api_user), conn=Depends(get_conn),
               config: Config = Depends(get_config)) -> JSONResponse:
    _limit(request, "orders", str(user["id"]))
    _need(fivesim.enabled(config), "Виртуальные номера")
    if body.service not in fivesim.SERVICES:
        raise ApiError("Укажите сервис из GET /numbers/services.", "unknown_service", 400)
    try:
        vid = fivesim.buy(conn, config, user, body.service, body.country[:40])
    except fivesim.FiveSimError as exc:
        raise _number_error(exc) from None
    return JSONResponse({"ok": True, "order": _number_view(_own_number(conn, vid, user["id"]))}, status_code=201)


@router.get("/numbers/orders")
def number_list(request: Request, limit: int = Query(default=20, ge=1, le=100), user=Depends(api_user),
                conn=Depends(get_conn)) -> dict[str, Any]:
    _limit(request, "catalog", str(user["id"]))
    rows = conn.execute("SELECT * FROM vnumbers WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                        (user["id"], limit)).fetchall()
    return {"ok": True, "items": [_number_view(r) for r in rows]}


@router.get("/numbers/orders/{vid}")
def number_get(vid: int, request: Request, user=Depends(api_user), conn=Depends(get_conn),
               config: Config = Depends(get_config)) -> dict[str, Any]:
    """Каждый запрос спрашивает 5sim: пришёл ли код. Код не пришёл и время вышло — деньги вернутся сами."""
    _limit(request, "catalog", str(user["id"]))
    v = _own_number(conn, vid, user["id"])
    if fivesim.enabled(config):
        v = fivesim.refresh(conn, config, vid) or v
    return {"ok": True, "order": _number_view(v)}


@router.post("/numbers/orders/{vid}/cancel")
def number_cancel(vid: int, request: Request, user=Depends(api_user), conn=Depends(get_conn),
                  config: Config = Depends(get_config)) -> dict[str, Any]:
    _limit(request, "orders", str(user["id"]))
    _own_number(conn, vid, user["id"])
    try:
        fivesim.cancel(conn, config, vid, user["id"])
    except fivesim.FiveSimError as exc:
        raise ApiError(str(exc), "cancel_failed", 400) from None
    return {"ok": True, "order": _number_view(_own_number(conn, vid, user["id"]))}


# ── Подарки Telegram ───────────────────────────────────────────


class GiftIn(BaseModel):
    gift_id: str = Field(max_length=64)            # из GET /gifts
    recipient: str = Field(default="", max_length=64)   # @username получателя; пусто — ссылка для друга
    text: str = Field(default="", max_length=tggifts.TEXT_MAX)


def _gift_view(conn: sqlite3.Connection, o: dict[str, Any]) -> dict[str, Any]:
    bot = db.get_setting(conn, "gifts.bot_username") or ""
    link = (f"https://t.me/{bot}?start=g_{o['link_token']}"
            if o["status"] == "awaiting_recipient" and bot and o.get("link_token") else None)
    return {"id": o["id"], "ref": refs.ref("gift", o["id"]), "gift_id": o["gift_id"], "stars": o["star_count"],
            "price_usd": fmt(o["price_micro"]), "status": o["status"], "recipient": o["recipient"] or None,
            "link": link, "error": o["error"] or None, "created_at": o["created_at"]}


@router.get("/gifts")
def gift_list(request: Request, user=Depends(api_user), conn=Depends(get_conn),
              config: Config = Depends(get_config)) -> dict[str, Any]:
    _limit(request, "catalog", str(user["id"]))
    _need(tggifts.enabled(config), "Подарки")
    items = tggifts.listing(conn, config, None)
    return {"ok": True, "items": [{"gift_id": g["id"], "stars": g["stars"], "emoji": g["emoji"],
                                   "image": (config.base_url + g["img"]) if g["img"] else None,
                                   "price_usd": fmt(g["price_micro"]), "left": g["left"], "total": g["total"]}
                                  for g in items]}


@router.post("/gifts/orders", status_code=201)
def gift_buy(body: GiftIn, request: Request, user=Depends(api_user), conn=Depends(get_conn),
             config: Config = Depends(get_config)) -> JSONResponse:
    _limit(request, "orders", str(user["id"]))
    _need(tggifts.enabled(config), "Подарки")
    rid, rname = None, ""
    if body.recipient.strip():
        name = body.recipient.strip().lstrip("@")
        rname = "@" + name
        known = tggifts.find_username(conn, name)
        if known:   # получатель уже нажимал Start в боте — подарок уходит сразу
            rid = int(known["tg_id"])
    try:
        o = tggifts.buy(conn, config, user, body.gift_id, recipient_id=rid, recipient=rname, text=body.text,
                        price_user=None)
    except tggifts.GiftError as exc:
        if "баланс" in str(exc).lower():
            raise ApiError(str(exc), "insufficient_balance", 402) from None
        raise ApiError(str(exc), "order_failed", 400) from None
    return JSONResponse({"ok": True, "order": _gift_view(conn, o)}, status_code=201)


@router.get("/gifts/orders/{oid}")
def gift_get(oid: int, request: Request, user=Depends(api_user), conn=Depends(get_conn)) -> dict[str, Any]:
    _limit(request, "catalog", str(user["id"]))
    o = tggifts.get(conn, oid)
    if not o or o.get("user_id") != user["id"]:
        raise ApiError("Заказ не найден.", "order_not_found", 404)
    return {"ok": True, "order": _gift_view(conn, o)}

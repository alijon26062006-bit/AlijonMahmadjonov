"""API в формате FazerCards (/api/v2) — чтобы готовые боты работали через Donatix.

Бот партнёра (stars_bot_template и любой другой, написанный под FazerCards) меняет
только адрес FAZER_BASE_URL и ключ: ключ — это обычный API-ключ Donatix (dx_live_…),
цены — уже с наценкой партнёра, списание — с его баланса в Donatix.

Повторяем ровно те ответы, которые такие боты читают: см. docs/fazercards/api-reference.md.
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field

from . import account_check, accounts, catalog, orders
from .api import ApiError, _limit, api_user
from .config import Config
from .deps import get_config, get_conn
from .money import fmt, fmt_unit, to_decimal

router = APIRouter(prefix="/api/v2", tags=["API v2 (совместимый формат)"])


def _order_out(row: sqlite3.Row) -> dict[str, Any]:
    v = orders.public_view(row)
    return {"id": v["order_id"], "order_id": v["order_id"], "status": v["status"], "kind": v["kind"],
            "product_name": v["product_name"], "quantity": v["quantity"], "total_usd": v["total_usd"],
            "error": v["error"], "payload": v["delivery"], "created_at": v["created_at"]}


def _price(user, config: Config, p: dict[str, Any]) -> Decimal:
    from .money import apply_markup
    return apply_markup(to_decimal(p["base_price"]), accounts.markup_for(user, config, p["kind"]))


def _buy(request: Request, conn, config: Config, user, product_id: str, quantity: Any,
         fields: dict[str, str], idem: str | None) -> dict[str, Any]:
    _limit(request, "orders", str(user["id"]))
    try:
        order, _ = orders.create_order(conn, config, request.app.state.supplier, user, product_id=product_id,
                                       quantity=quantity, fields=fields, client_idem_key=idem, source="api")
    except orders.OrderError as exc:
        raise ApiError(str(exc), exc.code, exc.http_status) from None
    return {"ok": True, "order": _order_out(order)}


# ── Баланс ───────────────────────────────────────────────────


@router.get("/balance")
def balance(user=Depends(api_user)) -> dict[str, Any]:
    return {"ok": True, "balance": fmt(user["balance_micro"]), "currency": "USD"}


@router.get("/me")
def me(user=Depends(api_user)) -> dict[str, Any]:
    return {"ok": True, "login": user["login"], "email": user["email"], "balance": fmt(user["balance_micro"]),
            "currency": "USD"}


# ── Telegram ─────────────────────────────────────────────────


@router.get("/telegram/stars")
def stars_quote(request: Request, user=Depends(api_user), conn=Depends(get_conn),
                config: Config = Depends(get_config)) -> dict[str, Any]:
    _limit(request, "catalog", str(user["id"]))
    p = catalog.get_product(conn, "tg-stars")
    if p is None:
        raise ApiError("Telegram Stars сейчас недоступны.", "not_available", 503)
    return {"ok": True, "price_per_star": fmt_unit(_price(user, config, p)),
            "min_amount": p["min_qty"], "max_amount": p["max_qty"], "currency": "USD"}


@router.get("/telegram/premium")
def premium_quote(request: Request, user=Depends(api_user), conn=Depends(get_conn),
                  config: Config = Depends(get_config)) -> dict[str, Any]:
    _limit(request, "catalog", str(user["id"]))
    plans = []
    for p in catalog.list_products(conn, kind="telegram_premium"):
        months = p["supplier_ref"].get("months")
        if months:
            plans.append({"months": int(months), "price_usd": fmt_unit(_price(user, config, p))})
    return {"ok": True, "plans": sorted(plans, key=lambda x: x["months"]), "currency": "USD"}


class StarsIn(BaseModel):
    telegram_username: str = Field(max_length=64)
    quantity: int = 0


class PremiumIn(BaseModel):
    telegram_username: str = Field(max_length=64)
    months: int = 0


@router.post("/telegram/stars/buy")
def stars_buy(body: StarsIn, request: Request, idempotency_key: str | None = Header(default=None),
              user=Depends(api_user), conn=Depends(get_conn), config: Config = Depends(get_config)):
    return _buy(request, conn, config, user, "tg-stars", body.quantity,
                {"telegram_username": body.telegram_username}, idempotency_key)


@router.post("/telegram/premium/buy")
def premium_buy(body: PremiumIn, request: Request, idempotency_key: str | None = Header(default=None),
                user=Depends(api_user), conn=Depends(get_conn), config: Config = Depends(get_config)):
    return _buy(request, conn, config, user, f"tg-premium-{body.months}", 1,
                {"telegram_username": body.telegram_username}, idempotency_key)


# ── Пополнение игр ───────────────────────────────────────────


def _fields_out(p: dict[str, Any]) -> list[dict[str, str]]:
    return [{"name": f["key"], "key": f["key"], "label": f.get("label") or f["key"],
             "type": f.get("type") or "text", **({"options": f["options"]} if f.get("options") else {})}
            for f in p["fields"]]


def _categories(conn, supplier, only_checkable: bool = False) -> list[dict[str, Any]]:
    from . import cache
    return cache.get_or_set(f"compat:cats:{only_checkable}", 60, lambda: _categories_now(conn, supplier, only_checkable))


def _categories_now(conn, supplier, only_checkable: bool = False) -> list[dict[str, Any]]:
    checkable = account_check.supported(supplier)
    out, seen = [], set()
    for p in catalog.list_products(conn, kind="topup", limit=10000):
        if p["category_id"] in seen:
            continue
        can = p["category_id"] in checkable or account_check.can_check(supplier, p)
        if only_checkable and not can:
            continue
        seen.add(p["category_id"])
        out.append({"category_id": p["category_id"], "name": p["category_name"], "fields": _fields_out(p),
                    "imageurl": p.get("image_url"), "validate": can})
    return out


@router.get("/topups")
@router.get("/topups/categories")
def topup_categories(request: Request, user=Depends(api_user), conn=Depends(get_conn)) -> dict[str, Any]:
    _limit(request, "catalog", str(user["id"]))
    items = _categories(conn, request.app.state.supplier)
    return {"ok": True, "kind": "topup", "items": items, "categories": items,
            "meta": {"total": len(items), "has_more": False, "next_cursor": None}}


@router.get("/topups/offers")
def topup_offers(category_id: str, request: Request, user=Depends(api_user), conn=Depends(get_conn),
                 config: Config = Depends(get_config)) -> dict[str, Any]:
    _limit(request, "catalog", str(user["id"]))
    products = catalog.list_products(conn, kind="topup", category_id=category_id, limit=500)
    if not products:
        raise ApiError("Unknown category", "category_not_found", 404)
    offers = [{"offer_id": p["id"], "name": p["name"], "price_usd": fmt_unit(_price(user, config, p)),
               "region": p.get("region")} for p in products]
    return {"ok": True, "category_id": category_id, "name": products[0]["category_name"],
            "imageurl": products[0].get("image_url"), "fields": _fields_out(products[0]), "offers": offers}


@router.get("/topups/validate-id")
def validate_list(request: Request, user=Depends(api_user), conn=Depends(get_conn)) -> dict[str, Any]:
    _limit(request, "catalog", str(user["id"]))
    return {"ok": True, "items": _categories(conn, request.app.state.supplier, only_checkable=True)}


class ValidateIn(BaseModel):
    category_id: str = Field(max_length=64)
    fields: dict[str, str] = Field(default_factory=dict)


@router.post("/topups/validate-id")
def validate_id(body: ValidateIn, request: Request, user=Depends(api_user), conn=Depends(get_conn)):
    _limit(request, "status", str(user["id"]))
    products = catalog.list_products(conn, kind="topup", category_id=body.category_id, limit=1)
    if not products:
        raise ApiError("Unknown category", "category_not_found", 404)
    supplier = request.app.state.supplier
    if not account_check.can_check(supplier, products[0]):
        return {"ok": True, "status": "unsupported"}
    r = account_check.check(supplier, products[0], {k: str(v) for k, v in body.fields.items()})
    if r["valid"] is None:
        return {"ok": True, "status": "unsupported"}
    if not r["valid"]:
        raise ApiError("Player not found", "player_not_found", 400)
    return {"ok": True, "valid": True, "player_name": r["player_name"], "region": r["region"]}


class TopupOrderIn(BaseModel):
    category_id: str = Field(default="", max_length=64)
    offer_id: str = Field(max_length=64)
    fields: dict[str, str] = Field(default_factory=dict)
    quantity: int = 1


@router.post("/topups/order")
def topup_order(body: TopupOrderIn, request: Request, idempotency_key: str | None = Header(default=None),
                user=Depends(api_user), conn=Depends(get_conn), config: Config = Depends(get_config)):
    p = catalog.get_product(conn, body.offer_id)
    if p is None or p["kind"] != "topup" or (body.category_id and p["category_id"] != body.category_id):
        raise ApiError("Offer not found in this category", "offer_not_found", 404)
    return _buy(request, conn, config, user, p["id"], 1, {k: str(v) for k, v in body.fields.items()}, idempotency_key)


# ── Steam ────────────────────────────────────────────────────


@router.get("/steam-topup/rates")
def steam_rates(request: Request, currency: str = "RUB", user=Depends(api_user), conn=Depends(get_conn),
                config: Config = Depends(get_config)) -> dict[str, Any]:
    """Цена 1 единицы валюты кошелька в USD (для партнёра, с наценкой). По умолчанию — рубли."""
    _limit(request, "catalog", str(user["id"]))
    p = catalog.get_product(conn, "steam-topup")
    if p is None:
        raise ApiError("Пополнение Steam сейчас недоступно.", "not_available", 503)
    per_usd = _price(user, config, p)
    rates = p["supplier_ref"].get("rates") or {}
    all_rates = {c: fmt_unit(per_usd / to_decimal(r)) for c, r in rates.items() if to_decimal(r) > 0}
    cur = currency.upper() if currency.upper() in all_rates else ("RUB" if "RUB" in all_rates else "USD")
    return {"ok": True, "rate": {"price_usd": all_rates.get(cur, fmt_unit(per_usd)), "currency": cur},
            "rates": all_rates, "wallet_rates": rates}


class SteamLoginIn(BaseModel):
    login: str = Field(default="", max_length=64)
    steamLogin: str = Field(default="", max_length=64)  # noqa: N815 — так называет поле FazerCards


@router.post("/steam-topup/check-login")
def steam_check(body: SteamLoginIn, request: Request, user=Depends(api_user)):
    _limit(request, "status", str(user["id"]))
    login = (body.login or body.steamLogin).strip()
    try:
        ok = request.app.state.supplier.check_steam_login(login)
    except Exception:  # noqa: BLE001 — для бота это «проверить не удалось»
        raise ApiError("Steam check temporarily unavailable", "temporarily_unavailable", 503) from None
    return {"ok": True, "exists": bool(ok), "can_refill": bool(ok), "name": login}


class SteamOrderIn(BaseModel):
    login: str = Field(default="", max_length=64)
    steamLogin: str = Field(default="", max_length=64)  # noqa: N815
    amount: str | int | float = 0
    currency: str = "RUB"


@router.post("/steam-topup/order")
def steam_order(body: SteamOrderIn, request: Request, idempotency_key: str | None = Header(default=None),
                user=Depends(api_user), conn=Depends(get_conn), config: Config = Depends(get_config)):
    fields = {"steam_login": (body.login or body.steamLogin).strip(), "currency": body.currency.upper(),
              "amount": str(body.amount)}
    return _buy(request, conn, config, user, "steam-topup", 1, fields, idempotency_key)


# ── Заказы ───────────────────────────────────────────────────


@router.get("/orders/{order_id}")
def order_one(order_id: str, request: Request, user=Depends(api_user), conn=Depends(get_conn)):
    _limit(request, "status", str(user["id"]))
    row = orders.find_user_order(conn, user["id"], order_id)
    if row is None:
        raise ApiError("Order not found", "not_found", 404)
    row = orders.refresh_if_stale(conn, request.app.state.supplier, row)
    return {"ok": True, "order": _order_out(row)}


@router.get("/orders")
def order_list(request: Request, limit: int = 50, page: int = 1, user=Depends(api_user), conn=Depends(get_conn)):
    _limit(request, "status", str(user["id"]))
    limit, page = min(max(limit, 1), 200), min(max(page, 1), 100_000)
    total = conn.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user["id"],)).fetchone()[0]
    rows = conn.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
                        (user["id"], limit, (page - 1) * limit)).fetchall()
    items = [_order_out(r) for r in rows]
    return {"ok": True, "orders": items, "items": items, "total": total, "page": page, "limit": limit}


# ── Остальные разделы FazerCards: готовые боты обращаются к ним — раньше получали 404 ──


@router.get("/transactions")
def transactions(request: Request, page: int = 1, limit: int = 20, user=Depends(api_user), conn=Depends(get_conn)):
    from . import api
    return api.transactions(request, page, limit, user, conn)


@router.get("/transactions/{transaction_id}")
def transaction_one(transaction_id: str, request: Request, user=Depends(api_user), conn=Depends(get_conn)):
    from . import api
    return api.transaction(transaction_id[:40], request, user, conn)


@router.get("/subscription")
def subscription(user=Depends(api_user)) -> dict[str, Any]:
    """Подписок у Donatix нет: тариф всегда активен (бот, который проверяет подписку, не останавливается)."""
    return {"ok": True, "plan": user["tier"], "planExpiresAt": None, "planAutoRenew": False,
            "subscriptionActive": True, "currency": "USD"}


@router.get("/subscription/plans")
@router.get("/website/subscription-prices")
def subscription_plans() -> dict[str, Any]:
    return {"ok": True, "plans": [], "note": "Donatix работает без подписки — платите только за заказы."}


def _cats(conn, kind: str) -> list[dict[str, Any]]:
    out, seen = [], set()
    for p in catalog.list_products(conn, kind=kind, limit=10000):
        if p["category_id"] in seen:
            continue
        seen.add(p["category_id"])
        out.append(p)
    return out


def _page_meta(items: list, limit: int, cursor: str) -> tuple[list, dict[str, Any]]:
    start = int(cursor) if cursor.isdigit() else 0
    limit = min(max(limit, 1), 500)
    chunk = items[start:start + limit]
    more = start + limit < len(items)
    return chunk, {"total": len(items), "has_more": more, "next_cursor": str(start + limit) if more else None}


@router.get("/giftcards")
def giftcard_categories(request: Request, limit: int = 50, cursor: str = "", user=Depends(api_user),
                        conn=Depends(get_conn)) -> dict[str, Any]:
    _limit(request, "catalog", str(user["id"]))
    items = [{"category_id": p["category_id"], "name": p["category_name"], "imageurl": p.get("image_url")}
             for p in _cats(conn, "gift_card")]
    items, meta = _page_meta(items, limit, cursor[:12])
    return {"ok": True, "kind": "gift_card", "items": items, "meta": meta}


@router.get("/giftcards/cards")
def giftcard_cards(category_id: str, request: Request, user=Depends(api_user), conn=Depends(get_conn),
                   config: Config = Depends(get_config)) -> dict[str, Any]:
    _limit(request, "catalog", str(user["id"]))
    products = catalog.list_products(conn, kind="gift_card", category_id=category_id[:64], limit=500)
    if not products:
        raise ApiError("Unknown category", "category_not_found", 404)
    offers = [{"card_id": p["id"], "name": p["name"], "price_usd": fmt_unit(_price(user, config, p)),
               "stock": p.get("stock"), "min_order_quantity": p["min_qty"], "max_order_quantity": p["max_qty"]}
              for p in products]
    return {"ok": True, "category_id": category_id, "name": products[0]["category_name"], "offers": offers}


class GiftOrderIn(BaseModel):
    category_id: str = Field(default="", max_length=64)
    card_id: str = Field(max_length=64)
    quantity: int = 1


@router.post("/giftcards/order")
def giftcard_order(body: GiftOrderIn, request: Request, idempotency_key: str | None = Header(default=None),
                   user=Depends(api_user), conn=Depends(get_conn), config: Config = Depends(get_config)):
    p = catalog.get_product(conn, body.card_id)
    if p is None or p["kind"] != "gift_card" or (body.category_id and p["category_id"] != body.category_id):
        raise ApiError("Card not found in this category", "offer_not_found", 404)
    return _buy(request, conn, config, user, p["id"], body.quantity, {}, idempotency_key)


@router.get("/gamekeys")
def gamekey_games(request: Request, limit: int = 200, cursor: str = "", user=Depends(api_user),
                  conn=Depends(get_conn)) -> dict[str, Any]:
    _limit(request, "catalog", str(user["id"]))
    items = []
    for p in _cats(conn, "game_key"):
        ref = p["supplier_ref"]
        items.append({"name": p["category_name"], "game_id": p["category_id"], "region": p.get("region"),
                      "platform": ref.get("platform"), "region_restriction": bool(ref.get("region_restriction")),
                      "appid": ref.get("appid"), "imageurl": p.get("image_url")})
    items, meta = _page_meta(items, limit, cursor[:12])
    return {"ok": True, "kind": "game_key", "items": items, "meta": meta}


@router.get("/gamekeys/keys")
def gamekey_keys(game_id: str, request: Request, user=Depends(api_user), conn=Depends(get_conn),
                 config: Config = Depends(get_config)) -> dict[str, Any]:
    _limit(request, "catalog", str(user["id"]))
    products = catalog.list_products(conn, kind="game_key", category_id=game_id[:64], limit=500)
    if not products:
        raise ApiError("Unknown game", "category_not_found", 404)
    ref = products[0]["supplier_ref"]
    keys = [{"key_id": p["id"], "name": p["name"], "price_usd": fmt_unit(_price(user, config, p)),
             "stock": p.get("stock"), "region": p.get("region"), "min_order_quantity": p["min_qty"],
             "max_order_quantity": p["max_qty"]} for p in products]
    return {"ok": True, "GameName": products[0]["category_name"], "game_id": game_id, "platform": ref.get("platform"),
            "region_restriction": bool(ref.get("region_restriction")), "imageurl": products[0].get("image_url"),
            "keys": keys}


@router.get("/gamekeys/region-restriction")
def gamekey_regions(game_id: str, request: Request, user=Depends(api_user)) -> dict[str, Any]:
    _limit(request, "catalog", str(user["id"]))
    from . import gamekeys
    data = gamekeys.regions(request.app.state.supplier, game_id[:64])
    return {"ok": True, "region_type": data.get("region_type", ""), "has_availability": bool(data.get("available")),
            "available": data.get("available", []), "unavailable": data.get("unavailable", [])}


class KeyOrderIn(BaseModel):
    game_id: str = Field(default="", max_length=64)
    key_id: str = Field(max_length=64)
    quantity: int = 1


@router.post("/gamekeys/order")
def gamekey_order(body: KeyOrderIn, request: Request, idempotency_key: str | None = Header(default=None),
                  user=Depends(api_user), conn=Depends(get_conn), config: Config = Depends(get_config)):
    p = catalog.get_product(conn, body.key_id)
    if p is None or p["kind"] != "game_key" or (body.game_id and p["category_id"] != body.game_id):
        raise ApiError("Key not found for this game", "offer_not_found", 404)
    return _buy(request, conn, config, user, p["id"], body.quantity, {}, idempotency_key)


@router.get("/steam-topup/public-rates")
def steam_public_rates(request: Request, conn=Depends(get_conn)) -> dict[str, Any]:
    p = catalog.get_product(conn, "steam-topup")
    if p is None:
        raise ApiError("Пополнение Steam сейчас недоступно.", "not_available", 503)
    return {"ok": True, "wallet_rates": p["supplier_ref"].get("rates") or {}}


@router.get("/steam-gifts/games")
def steam_gift_games(request: Request, q: str = "", limit: int = 100, user=Depends(api_user), conn=Depends(get_conn)):
    from . import api
    return api.steam_gift_games(request, q[:100], limit, user, conn)


@router.get("/steam-gifts/games/{appid}")
def steam_gift_game(appid: int, request: Request, user=Depends(api_user), conn=Depends(get_conn),
                    config: Config = Depends(get_config)):
    from . import api
    _limit(request, "catalog", str(user["id"]))
    return api.steam_gift_view(request, conn, config, user, appid)


class SteamGiftIn(BaseModel):
    invite_url: str = Field(max_length=300)
    sub_id: int
    app_id: int
    region: str = Field(max_length=16)


@router.post("/steam-gifts/order")
def steam_gift_order(body: SteamGiftIn, request: Request, idempotency_key: str | None = Header(default=None),
                     user=Depends(api_user), conn=Depends(get_conn), config: Config = Depends(get_config)):
    fields = {"invite_url": body.invite_url.strip(), "sub_id": str(body.sub_id), "app_id": str(body.app_id),
              "region": body.region.strip()}
    return _buy(request, conn, config, user, "steam-gift", 1, fields, idempotency_key)


@router.get("/payments/methods")
def payment_methods(request: Request, user=Depends(api_user), conn=Depends(get_conn),
                    config: Config = Depends(get_config)):
    from . import api
    return api.payment_methods(request, user, conn, config)


class PaymentV2In(BaseModel):
    method: str = Field(max_length=32)
    amount: str | int | float = 0


@router.post("/payments/create")
def payment_create(body: PaymentV2In, request: Request, user=Depends(api_user), conn=Depends(get_conn),
                   config: Config = Depends(get_config)):
    from . import api
    return api.payment_create(api.PaymentIn(method=body.method, amount_usd=str(body.amount)), request, user, conn, config)


@router.get("/payments/{payment_id}")
def payment_one(payment_id: int, user=Depends(api_user), conn=Depends(get_conn), config: Config = Depends(get_config)):
    from . import api
    if not 1 <= payment_id <= 2**62:
        raise ApiError("Заявка не найдена.", "not_found", 404)
    return api.payment_one(payment_id, user, conn, config)

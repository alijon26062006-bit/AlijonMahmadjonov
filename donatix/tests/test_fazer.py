"""Клиент FazerCards на подменённом HTTP: проверяем, что шлём именно то, что в их документации."""

import json

import httpx
import pytest

from donatix.suppliers import SupplierRejected, SupplierUnavailable
from donatix.suppliers.fazer import FazerSupplier


def make(handler):
    return FazerSupplier("KEY", "https://api.fzr.cards/api/v2", transport=httpx.MockTransport(handler),
                         catalog_pause=0)


def test_catalog():
    def handler(req: httpx.Request):
        assert req.headers["X-API-Key"] == "KEY"
        p = req.url.path.removeprefix("/api/v2")
        if p == "/telegram/stars":
            return httpx.Response(200, json={"ok": True, "price_per_star": "0.0150000", "min_amount": 50,
                                             "max_amount": 10000})
        if p == "/telegram/premium":
            return httpx.Response(200, json={"ok": True, "plans": [{"months": 3, "price_usd": "12.0000"}]})
        if p == "/topups":
            if req.url.params.get("cursor") == "c2":
                return httpx.Response(200, json={"ok": True, "items": [{"category_id": "ff", "name": "Free Fire"}],
                                                 "meta": {"has_more": False, "next_cursor": None}})
            return httpx.Response(200, json={"ok": True, "items": [{"category_id": "cat_pubgm_1", "name": "PUBG"}],
                                             "meta": {"has_more": True, "next_cursor": "c2"}})
        if p == "/topups/offers":
            cid = req.url.params["category_id"]
            if cid == "ff":
                return httpx.Response(403, json={"ok": False, "error": "not in plan"})
            return httpx.Response(200, json={"ok": True, "name": "PUBG Mobile",
                                             "offers": [{"offer_id": "offer_60uc", "name": "60 UC",
                                                         "price_usd": "0.9900"}],
                                             "fields": [{"key": "player_id", "label": "Player ID", "type": "text"}]})
        if p == "/giftcards":
            return httpx.Response(200, json={"ok": True, "items": [{"category_id": "gc_steam_1", "name": "Steam USD"}],
                                             "meta": {"has_more": False}})
        if p == "/giftcards/cards":
            return httpx.Response(200, json={"ok": True, "name": "Steam USD", "offers": [
                {"card_id": "card_10usd", "name": "Steam — $10", "price_usd": "10.5000", "stock": 100,
                 "min_order_quantity": 1, "max_order_quantity": 10}]})
        return httpx.Response(404, json={"ok": False, "error": "nope"})

    items = {p.id: p for p in make(handler).fetch_catalog()}
    stars = items["tg-stars"]
    assert str(stars.base_price) == "0.0150000" and stars.max_qty == 10000
    assert items["tg-premium-3"].supplier_ref == {"months": 3}
    topup = next(p for p in items.values() if p.kind == "topup")
    assert topup.supplier_ref == {"category_id": "cat_pubgm_1", "offer_id": "offer_60uc"}
    assert topup.fields[0]["key"] == "player_id"
    gc = next(p for p in items.values() if p.kind == "gift_card")
    assert gc.stock == 100 and gc.max_qty == 10
    assert len(items) == 4  # Free Fire (403) пропущен


def test_create_order_sends_documented_body():
    seen = {}

    def handler(req: httpx.Request):
        seen["path"] = req.url.path
        seen["body"] = json.loads(req.content)
        seen["idem"] = req.headers.get("Idempotency-Key")
        return httpx.Response(200, json={"ok": True, "order": {"id": "ord-9002", "kind": "topup",
                                                                "status": "processing"}})

    s = make(handler)
    product = {"kind": "topup", "supplier_ref": {"category_id": "cat_pubgm_1", "offer_id": "offer_60uc"}}
    res = s.create_order(product, 1, {"player_id": "123"}, "idem-1")
    assert seen == {"path": "/api/v2/topups/order", "idem": "idem-1",
                    "body": {"category_id": "cat_pubgm_1", "offer_id": "offer_60uc", "fields": {"player_id": "123"}}}
    assert res.order_id == "ord-9002" and res.status == "processing"

    s.create_order({"kind": "telegram_stars", "supplier_ref": {}}, 100, {"telegram_username": "@durov"}, "k")
    assert seen["path"] == "/api/v2/telegram/stars/buy"
    assert seen["body"] == {"telegram_username": "@durov", "quantity": 100}

    s.create_order({"kind": "gift_card", "supplier_ref": {"category_id": "gc", "card_id": "c"}}, 3, {}, "k")
    assert seen["body"] == {"category_id": "gc", "card_id": "c", "quantity": 3}


def test_errors():
    s = make(lambda req: httpx.Response(400, json={"ok": False, "error": "Insufficient balance", "code": "x"}))
    with pytest.raises(SupplierRejected) as e:
        s.create_order({"kind": "telegram_stars", "supplier_ref": {}}, 50, {"telegram_username": "@a1234"}, "k")
    assert e.value.http_status == 400 and e.value.code == "x"

    s = make(lambda req: httpx.Response(502, text="bad gateway"))
    with pytest.raises(SupplierUnavailable):
        s.get_order("ord-1")

    def boom(req):
        raise httpx.ConnectTimeout("timeout", request=req)
    with pytest.raises(SupplierUnavailable):
        make(boom).balance()


def test_get_order_and_balance():
    def handler(req: httpx.Request):
        if req.url.path.endswith("/balance"):
            return httpx.Response(200, json={"ok": True, "balance": "100.0000", "currency": "USD"})
        return httpx.Response(200, json={"ok": True, "order": {"id": "ord-9001", "kind": "gift_card",
                                                                "status": "completed", "payload": {"codes": ["AAA"]}}})
    s = make(handler)
    o = s.get_order("ord-9001")
    assert o.status == "completed" and o.delivery == {"codes": ["AAA"]}
    assert str(s.balance()) == "100.0000"

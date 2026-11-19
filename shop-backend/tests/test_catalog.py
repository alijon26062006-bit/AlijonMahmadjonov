import httpx

from tests.conftest import API_KEY, register

OFFERS = {
    "ok": True, "kind": "topup", "category_id": "pubg-auto", "name": "PUBG Mobile (Auto)", "note": "Region: Global",
    "imageurl": "https://x/cover.png",
    "offers": [{"offer_id": "60uc", "name": "60 UC", "price_usd": "0.9077"},
               {"offer_id": 7, "name": "First Purchase Pack", "price_usd": "0.8866"}],
    "fields": [{"key": "player_id", "label": "Player ID", "type": "text", "options": []}],
}


def test_topup_list_paginates_and_hides_images(client, mock):
    pages = {
        None: {"ok": True, "kind": "topup", "items": [{"category_id": "pubg-auto", "name": "PUBG Mobile (Auto)", "imageurl": "u"}],
               "meta": {"total": 2, "limit": 500, "next_cursor": "c2", "has_more": True}},
        "c2": {"ok": True, "kind": "topup", "items": [{"category_id": "ff-cis", "name": "Free Fire (CIS)", "note": "CIS"}],
               "meta": {"total": 2, "limit": 500, "next_cursor": None, "has_more": False}},
    }
    route = mock.get("/topups").mock(side_effect=lambda req: httpx.Response(200, json=pages[req.url.params.get("cursor")]))
    r = client.get("/api/catalog/topups")
    assert r.status_code == 200
    assert r.json()["items"] == [{"id": "pubg-auto", "name": "PUBG Mobile (Auto)", "note": ""},
                                 {"id": "ff-cis", "name": "Free Fire (CIS)", "note": "CIS"}]
    assert route.calls.last.request.headers["X-API-Key"] == API_KEY
    client.get("/api/catalog/topups")  # cached
    assert route.call_count == 2


def test_topup_detail_applies_markup_and_hides_cost(client, mock):
    mock.get("/topups/offers").respond(json=OFFERS)
    mock.get("/topups/validate-id").respond(json={"ok": True, "kind": "topup", "items": [
        {"category_id": "pubg-auto", "name": "PUBG Mobile", "fields": []}]})
    r = client.get("/api/catalog/topups/pubg-auto")
    body = r.json()
    assert r.status_code == 200
    assert body["offers"] == [{"id": "60uc", "name": "60 UC", "price": "1.00"},
                              {"id": "7", "name": "First Purchase Pack", "price": "0.98"}]
    assert body["can_check_id"] is True and body["fields"][0]["key"] == "player_id"
    text = r.text
    assert "0.9077" not in text and "imageurl" not in text and API_KEY not in text


def test_markup_change_by_admin(client, mock):
    mock.get("/topups/offers").respond(json=OFFERS)
    mock.get("/topups/validate-id").respond(json={"ok": True, "kind": "topup", "items": []})
    register(client, email="user@example.com", username="usr1")
    assert client.put("/api/admin/settings/markup", json={"percent": "20"}).status_code == 403
    client.cookies.clear()
    register(client, email="boss@example.com", username="boss")
    assert client.put("/api/admin/settings/markup", json={"percent": "20"}).json() == {"percent": "20"}
    r = client.get("/api/catalog/topups/pubg-auto")
    assert r.json()["offers"][0]["price"] == "1.09"  # 0.9077 * 1.2 = 1.08924 -> 1.09


def test_check_id_valid_invalid_unsupported(client, mock):
    mock.get("/topups/validate-id").respond(json={"ok": True, "kind": "topup", "items": [
        {"category_id": "pubg-auto", "name": "PUBG Mobile", "fields": [{"key": "player_id"}]}]})
    route = mock.post("/topups/validate-id")
    route.respond(json={"ok": True, "category_id": "pubg-auto", "valid": True, "player_name": "Hero", "region": "RU"})
    r = client.post("/api/catalog/topups/pubg-auto/check-id", json={"fields": {"player_id": " 5123456789 "}})
    assert r.json() == {"supported": True, "valid": True, "player_name": "Hero", "region": "RU"}
    assert b'"player_id":"5123456789"' in route.calls.last.request.content
    route.respond(status_code=422, json={"ok": False, "error": "cannot confirm"})
    r = client.post("/api/catalog/topups/pubg-auto/check-id", json={"fields": {"player_id": "1"}})
    assert r.json()["valid"] is False
    r = client.post("/api/catalog/topups/other/check-id", json={"fields": {"player_id": "1"}})
    assert r.json() == {"supported": False}


def test_telegram_quotes_with_markup(client, mock):
    mock.get("/telegram/stars").respond(json={"ok": True, "kind": "telegram_stars", "price_per_star": "0.0153750",
                                             "min_amount": 50, "max_amount": 100000, "rates_updated_at": "x"})
    mock.get("/telegram/premium").respond(json={"ok": True, "kind": "telegram_premium", "rates_updated_at": "x",
                                               "plans": [{"months": 3, "price_usd": "12.2898"}]})
    r = client.get("/api/catalog/telegram").json()
    assert r["stars"] == {"price_per_star": "0.0169125", "min": 50, "max": 100000}
    assert r["premium"] == [{"months": 3, "price": "13.52"}]


def test_supplier_down_and_errors(client, mock):
    mock.get("/topups").mock(side_effect=httpx.ConnectError("boom"))
    r = client.get("/api/catalog/topups")
    assert r.status_code == 502 and API_KEY not in r.text
    mock.get("/topups/offers").respond(status_code=404, json={"ok": False, "error": "not found"})
    mock.get("/topups/validate-id").respond(json={"ok": True, "kind": "topup", "items": []})
    assert client.get("/api/catalog/topups/missing").status_code == 404


def test_admin_supplier_status(client, mock):
    mock.get("/me").respond(json={"ok": True, "login": "x", "email": "e", "plan": "bronze", "planExpiresAt": "2026-12-12",
                                  "planAutoRenew": True, "subscriptionActive": True,
                                  "summary": {"totalSpent": "1", "totalOrders": 1}, "createdAt": "x", "lastActiveAt": None})
    mock.get("/balance").respond(json={"ok": True, "balance": "24.9355", "currency": "USD"})
    register(client, email="boss@example.com", username="boss")
    r = client.get("/api/admin/supplier/status").json()
    assert r["ok"] is True and r["balance"] == "24.9355" and r["subscription_active"] is True
    mock.get("/me").respond(status_code=403, json={"ok": False, "error": "inactive", "code": "subscription_inactive"})
    r = client.get("/api/admin/supplier/status").json()
    assert r == {"ok": False, "error": "inactive", "code": "subscription_inactive"}

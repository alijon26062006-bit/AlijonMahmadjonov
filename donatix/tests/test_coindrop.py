"""CoinDrop: каталог, заказ и статус через поддельный HTTP-слой (без настоящего coindrop.uz)."""
import httpx

from donatix.suppliers.coindrop import CoinDropSupplier
from donatix.suppliers.multi import MultiSupplier
from donatix.suppliers.mock import MockSupplier

GAMES = {"games": [
    {"game_key": "standoff-2", "name": "Standoff 2", "id_type": "numeric", "type": "standard"},
    {"game_key": "mlbb", "name": "Mobile Legends", "id_type": "numeric", "requires_server": True,
     "server_label": "Zone ID"},
    {"game_key": "telegram-stars", "name": "Telegram Stars", "amount_based": True, "id_type": "text"},  # пропустить
    {"game_key": "roblox-us", "name": "Roblox", "type": "voucher"},                                     # пропустить
]}
PRODUCTS = {
    "standoff-2": {"products": [
        {"product_id": "so100", "name": "100 Gold", "price_usd": "0.90", "retail_usd": "1.20"},
        {"product_id": "so500", "name": "500 Gold", "price_usd": "4.10"},
    ]},
    "mlbb": {"products": [{"product_id": "88", "name": "86 Diamonds", "price_usd": "1.15"}]},
}


def _handler(request: httpx.Request) -> httpx.Response:
    assert request.headers.get("X-API-Key") == "cd_test"
    path = request.url.path
    if path.endswith("/games"):
        return httpx.Response(200, json=GAMES)
    for key, body in PRODUCTS.items():
        if path.endswith(f"/games/{key}/products"):
            return httpx.Response(200, json=body)
    if path.endswith("/orders") and request.method == "POST":
        import json as _j
        b = _j.loads(request.content)
        if b["player_id"] == "000":
            return httpx.Response(422, json={"detail": "Insufficient balance"})
        return httpx.Response(200, json={"success": True, "order_id": 512, "status": "delivered",
                                         "product_name": b["product_id"], "message": "Delivered"})
    if "/orders/512" in path:
        return httpx.Response(200, json={"order_id": 512, "status": "delivered"})
    if path.endswith("/balance"):
        return httpx.Response(200, json={"balance_usd": "42.50"})
    return httpx.Response(404, json={"detail": "not found"})


def _supplier(**kw):
    s = CoinDropSupplier("cd_test", "https://coindrop.uz/api/v1", catalog_pause=0, **kw)
    s._client = httpx.Client(base_url="https://coindrop.uz/api/v1",
                             headers={"X-API-Key": "cd_test"}, transport=httpx.MockTransport(_handler))
    return s


def test_catalog_only_numeric_topups():
    items = {p.id: p for p in _supplier().fetch_catalog()}
    assert "cd-standoff-2-so100" in items and "cd-standoff-2-so500" in items and "cd-mlbb-88" in items
    assert all("telegram" not in i and "roblox" not in i for i in items)      # amount-based и ваучеры пропущены
    so = items["cd-standoff-2-so100"]
    assert so.kind == "topup" and so.category_id == "cd_standoff-2" and str(so.base_price) == "0.90"
    assert so.category_name == "Standoff 2" and so.supplier_ref["game_key"] == "standoff-2"
    assert [f["key"] for f in so.fields] == ["player_id"]
    assert [f["key"] for f in items["cd-mlbb-88"].fields] == ["player_id", "server_id"]   # сервер добавлен


def test_only_games_filter():
    items = list(_supplier(only_games=["standoff-2"]).fetch_catalog())
    assert items and all(p.category_id == "cd_standoff-2" for p in items)


def test_order_and_status():
    s = _supplier()
    prod = {"kind": "topup", "supplier_ref": {"provider": "coindrop", "game_key": "standoff-2",
                                              "product_id": "so100", "requires_server": False}}
    order = s.create_order(prod, 1, {"player_id": "52425715863"}, "dx-abc")
    assert order.order_id == "cd:512" and order.status == "completed"
    st = s.get_order("cd:512")
    assert st.status == "completed"


def test_insufficient_balance_is_rejected():
    from donatix.suppliers.base import SupplierRejected
    s = _supplier()
    prod = {"kind": "topup", "supplier_ref": {"provider": "coindrop", "game_key": "standoff-2",
                                              "product_id": "so100", "requires_server": False}}
    try:
        s.create_order(prod, 1, {"player_id": "000"}, "dx-x")
        assert False
    except SupplierRejected as exc:
        assert exc.code == "insufficient_balance"


def test_balance():
    assert str(_supplier().balance()) == "42.50"


def test_multi_routes_by_provider_and_order_id():
    cd = _supplier()
    multi = MultiSupplier(MockSupplier(), [cd])
    fazer_prod = {"kind": "topup", "supplier_ref": {}}
    cd_prod = {"kind": "topup", "supplier_ref": {"provider": "coindrop", "game_key": "standoff-2",
                                                 "product_id": "so100", "requires_server": False}}
    assert multi._for_product(cd_prod) is cd
    assert multi._for_product(fazer_prod) is multi.primary
    assert multi._for_order_id("cd:512") is cd
    assert multi._for_order_id("fzr-99") is multi.primary
    # каталог = основной + CoinDrop
    ids = {p.id for p in multi.fetch_catalog()}
    assert "cd-standoff-2-so100" in ids and any(not i.startswith("cd-") for i in ids)
    assert multi.is_idempotent("topup") is True   # у mock topup идемпотентен

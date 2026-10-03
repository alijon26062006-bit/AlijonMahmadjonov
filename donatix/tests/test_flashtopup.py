"""FlashTopup: подпись запроса, список игр, поиск ника по ID."""

import hashlib
import hmac
import json

import httpx

from donatix import account_check, flashtopup


def _transport(seen):
    def handler(req: httpx.Request):
        seen.append(req)
        path = req.url.path
        if path.endswith("/products"):
            return httpx.Response(200, json={"success": True, "data": [
                {"product_code": "TOPUP_FREE_FIRE", "name": "Free Fire (Global)", "validation_code": "freefire"},
                {"product_code": "TOPUP_MLBB", "name": "Mobile Legends", "validation_code": "mlbb"}]})
        body = json.loads(req.content)
        if body["user_id"] == "000":
            return httpx.Response(422, json={"success": False, "error": {"code": "INVALID_PLAYER_ID",
                                                                         "message": "Invalid UserID"}})
        return httpx.Response(200, json={"success": True, "data": {"account_name": "ALI_PRO"}})
    return httpx.MockTransport(handler)


def test_signature_and_nick():
    seen = []
    ft = flashtopup.FlashTopup("ID1", "secret", transport=_transport(seen))
    game = ft.match("Free Fire")
    assert game["validation_code"] == "freefire"
    r = ft.check_id("freefire", "5123456789")
    assert r == {"valid": True, "player_name": "ALI_PRO", "message": ""}
    req = seen[-1]
    canonical = "\n".join(["POST", "/api/reseller/v2/check-id", req.headers["X-FT-Timestamp"],
                           req.headers["X-FT-Nonce"], hashlib.sha256(req.content).hexdigest()])
    assert req.headers["X-FT-Signature"] == hmac.new(b"secret", canonical.encode(), hashlib.sha256).hexdigest()
    assert ft.check_id("freefire", "000")["valid"] is False


def test_site_uses_flash_when_supplier_cannot(app, conn, supplier, monkeypatch):
    seen = []
    monkeypatch.setattr(account_check, "_flash", flashtopup.FlashTopup("ID1", "s", transport=_transport(seen)))
    monkeypatch.setattr(supplier, "validate_id_categories", lambda: [], raising=False)
    account_check.reset()
    from donatix.catalog import get_product
    p = next(get_product(conn, r[0]) for r in conn.execute(
        "SELECT id FROM products WHERE category_id = 'free_fire' LIMIT 1"))
    assert account_check.can_check(supplier, p)
    key = p["fields"][0]["key"]
    r = account_check.check(supplier, p, {key: "5123456789"})
    assert r["valid"] and r["player_name"] == "ALI_PRO" and r["strict"] is False
    bad = account_check.check(supplier, p, {key: "000"})
    assert bad["valid"] is False and bad["strict"] is False      # чужая проверка заказ не блокирует

from decimal import Decimal

from conftest import balance, web_login
from fastapi.testclient import TestClient

from donatix import accounts, cryptopay, payments

ADDR = "TXyzABCDEFGHJKLMNPQRSTUVWXYZabcdef"


def _method(conn, config, auto, details):
    payments.save_methods(conn, [{"code": "usdt", "title": "USDT", "currency": "USDT", "details": details,
                                  "enabled": True, "auto": auto}])


def _client(app, conn):
    uid = accounts.create_user(conn, email="c@example.com", login="client1", password="password123",
                               status="active")
    c = TestClient(app)
    token = web_login(c, "c@example.com", "password123")
    return uid, c, token


def test_trc20_auto_credit(app, config, conn, monkeypatch):
    _method(conn, config, "trc20", f"USDT TRC20: {ADDR}")
    uid, c, token = _client(app, conn)
    r = c.post("/panel/balance", data={"csrf": token, "method": "usdt", "amount": "20"}, follow_redirects=False)
    assert r.headers["location"].endswith("/pay")
    p = conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchone()
    amount = Decimal(p["pay_amount"])
    assert p["auto_kind"] == "trc20" and p["pay_address"] == ADDR and Decimal("20") < amount < Decimal("20.01")
    page = c.get(r.headers["location"]).text
    assert p["pay_amount"] in page and ADDR in page

    txs = []
    monkeypatch.setattr(cryptopay, "_get_json", lambda url, params, headers: {"data": txs})
    assert cryptopay.check_all(conn, config) == 0          # денег ещё нет
    ts = cryptopay._ms(p["created_at"]) + 5000
    txs.append({"transaction_id": "tx-wrong", "to": ADDR, "value": "20000000", "block_timestamp": ts,
                "token_info": {"address": cryptopay.USDT_TRC20, "decimals": 6}})
    txs.append({"transaction_id": "tx-ok", "to": ADDR, "value": str(int(amount * 1_000_000)), "block_timestamp": ts,
                "token_info": {"address": cryptopay.USDT_TRC20, "decimals": 6}})
    cryptopay.reset()
    assert cryptopay.check_all(conn, config) == 1
    assert balance(conn, uid) == 200_000
    assert c.get(f"/panel/data/payment/{p['id']}").json()["status"] == "paid"
    # тот же перевод второй раз не засчитывается
    cryptopay.reset()
    assert cryptopay.check_all(conn, config) == 0


def test_trc20_needs_address(conn, config):
    import pytest
    with pytest.raises(payments.PaymentError):
        _method(conn, config, "trc20", "без адреса")


def test_binance_pay(app, config, conn, monkeypatch):
    config.binance_pay_key, config.binance_pay_secret = "key", "secret"
    _method(conn, config, "binance", "")
    uid = accounts.create_user(conn, email="b@example.com", login="botshop", password="password123",
                               status="active")
    key = accounts.create_api_key(conn, uid, "bot")
    state = {"status": "INITIAL"}
    calls = []

    def fake(cfg, path, body):
        calls.append(path)
        if path.endswith("/order"):
            return {"checkoutUrl": "https://pay.binance.com/checkout/abc", "prepayId": "1"}
        return {"status": state["status"]}
    monkeypatch.setattr(cryptopay, "_binance_post", fake)
    api = TestClient(app)
    r = api.post("/api/v1/payments", headers={"X-API-Key": key}, json={"method": "usdt", "amount_usd": "15"}).json()
    pay = r["payment"]
    assert pay["auto"] == "binance" and pay["pay_url"].startswith("https://pay.binance.com")
    ext = conn.execute("SELECT ext_id FROM payments WHERE id = ?", (pay["id"],)).fetchone()[0]
    # фальшивое уведомление «оплачено» ничего не даёт — статус спрашиваем у Binance
    TestClient(app).post("/pay/binance/webhook", json={"data": {"merchantTradeNo": ext}})
    assert balance(conn, uid) == 0
    state["status"] = "PAID"
    TestClient(app).post("/pay/binance/webhook", json={"data": {"merchantTradeNo": ext}})
    assert balance(conn, uid) == 150_000


def test_binance_error_cancels(app, config, conn, monkeypatch):
    config.binance_pay_key, config.binance_pay_secret = "key", "secret"
    _method(conn, config, "binance", "")

    def boom(cfg, path, body):
        raise cryptopay.CryptoPayError("Binance Pay: invalid key")
    monkeypatch.setattr(cryptopay, "_binance_post", boom)
    uid, c, token = _client(app, conn)
    r = c.post("/panel/balance", data={"csrf": token, "method": "usdt", "amount": "20"})
    assert "invalid key" in r.text
    assert conn.execute("SELECT status FROM payments").fetchone()[0] == "cancelled"


def test_bybit_uid_auto_credit(app, config, conn, monkeypatch):
    config.bybit_key, config.bybit_secret = "k", "s"
    _method(conn, config, "bybit", "Bybit UID 123456789")
    uid, c, token = _client(app, conn)
    r = c.post("/panel/balance", data={"csrf": token, "method": "usdt", "amount": "30"}, follow_redirects=False)
    p = conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchone()
    assert p["auto_kind"] == "bybit" and p["pay_address"] == "123456789"
    assert "По UID" in c.get(r.headers["location"]).text
    ts = cryptopay._ms(p["created_at"]) + 3000
    internal = [{"id": "555", "amount": p["pay_amount"], "status": 2, "createdTime": str(ts), "coin": "USDT"}]

    def fake(cfg, path, params):
        return {"rows": internal if "internal" in path else []}
    monkeypatch.setattr(cryptopay, "_bybit_get", fake)
    assert cryptopay.check_all(conn, config) == 1
    assert balance(conn, uid) == 300_000


def test_bybit_needs_uid(conn, config):
    import pytest
    with pytest.raises(payments.PaymentError):
        _method(conn, config, "bybit", "без номера")


def test_bybit_network_address_from_bybit(app, config, conn, monkeypatch):
    """Способ «Bybit» с выбранной сетью: адрес пополнения сайт берёт у Bybit сам, UID не нужен."""
    config.bybit_key, config.bybit_secret = "k", "s"
    cryptopay._addr_cache.clear()
    payments.save_methods(conn, [{"code": "usdt", "title": "USDT TRC20", "currency": "USDT:TRC20", "details": "",
                                  "enabled": True, "auto": "bybit"}])
    deposits = []

    def fake(cfg, path, params):
        if path.endswith("query-address"):
            return {"coin": "USDT", "chains": [
                {"chainType": "ERC20", "chain": "ETH", "addressDeposit": "0xabc", "tagDeposit": ""},
                {"chainType": "TRC20", "chain": "TRX", "addressDeposit": "TXyzBybitDepositAddr", "tagDeposit": ""}]}
        return {"rows": deposits if path.endswith("query-record") else []}
    monkeypatch.setattr(cryptopay, "_bybit_get", fake)
    uid, c, token = _client(app, conn)
    r = c.post("/panel/balance", data={"csrf": token, "method": "usdt", "amount": "20"}, follow_redirects=False)
    p = conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchone()
    assert p["auto_kind"] == "bybit" and p["pay_address"] == "TXyzBybitDepositAddr"
    page = c.get(r.headers["location"]).text
    assert "TXyzBybitDepositAddr" in page and "сеть <b>TRC20</b>" in page and "qr-box" in page
    deposits.append({"txID": "0xdead", "amount": p["pay_amount"], "depositStatus": 3,
                     "successAt": str(cryptopay._ms(p["created_at"]) + 5000), "coin": "USDT"})
    assert cryptopay.check_all(conn, config) == 1
    assert balance(conn, uid) == 200_000


def test_usdt_15_minutes_then_closed_but_late_transfer_credited(app, config, conn, monkeypatch):
    """USDT: на оплату 15 минут — потом заявка закрыта. Перевод чуть позже всё равно зачисляется."""
    from datetime import datetime, timedelta, timezone
    _method(conn, config, "trc20", f"USDT TRC20: {ADDR}")
    uid, c, token = _client(app, conn)
    r = c.post("/panel/balance", data={"csrf": token, "method": "usdt", "amount": "20"}, follow_redirects=False)
    p = conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchone()
    page = c.get(r.headers["location"]).text
    assert 'id="ap-timer"' in page and "Оплатите за" in page
    old = (datetime.now(timezone.utc) - timedelta(minutes=16)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    conn.execute("UPDATE payments SET created_at = ? WHERE id = ?", (old, p["id"]))
    page = c.get(r.headers["location"]).text
    assert "15 минут" in page and 'id="ap-timer"' not in page
    assert conn.execute("SELECT status FROM payments WHERE id = ?", (p["id"],)).fetchone()[0] == "cancelled"
    # хвост суммы занят — новой заявке такой же не выдадут
    assert p["pay_amount"] in {r[0] for r in conn.execute("SELECT pay_amount FROM payments")}
    txs = [{"transaction_id": "tx-late", "to": ADDR, "value": str(int(Decimal(p["pay_amount"]) * 1_000_000)),
            "block_timestamp": cryptopay._ms(old) + 17 * 60_000,
            "token_info": {"address": cryptopay.USDT_TRC20, "decimals": 6}}]
    monkeypatch.setattr(cryptopay, "_get_json", lambda url, params, headers: {"data": txs})
    cryptopay.reset()
    assert cryptopay.check_all(conn, config) == 1
    assert balance(conn, uid) == 200_000
    assert conn.execute("SELECT status FROM payments WHERE id = ?", (p["id"],)).fetchone()[0] == "paid"

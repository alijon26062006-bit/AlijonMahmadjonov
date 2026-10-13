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
    assert p["auto_kind"] == "trc20" and p["pay_address"] == ADDR and amount == Decimal("20")   # ровная сумма
    page = c.get(r.headers["location"]).text
    assert "20 USDT" in page and ADDR in page and "В процессе" in page

    txs = []
    monkeypatch.setattr(cryptopay, "_get_json", lambda url, params, headers: {"data": txs})
    assert cryptopay.check_all(conn, config) == 0          # денег ещё нет
    ts = cryptopay._ms(p["created_at"]) + 5000
    txs.append({"transaction_id": "tx-wrong", "to": ADDR, "value": "19990000", "block_timestamp": ts,
                "token_info": {"address": cryptopay.USDT_TRC20, "decimals": 6}})
    txs.append({"transaction_id": "tx-ok", "to": ADDR, "value": str(int(amount * 1_000_000)), "block_timestamp": ts,
                "token_info": {"address": cryptopay.USDT_TRC20, "decimals": 6}})
    cryptopay.reset()
    assert cryptopay.check_all(conn, config) == 1
    assert balance(conn, uid) == 200_000
    assert c.get(f"/panel/data/payment/{p['id']}").json()["status"] == "paid"
    assert "✓ Выполнено" in c.get(f"/panel/balance/{p['id']}/pay").text   # зелёный статус
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
    assert "TXyzBybitDepositAddr" in page and "USDT TRC20" in page and "qr-box" in page and "Отправьте ровно эту сумму" in page
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
    assert 'id="ap-timer"' in page and "В процессе" in page
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


def test_balance_crypto_pane(app, config, conn):
    """Крипта: одна плитка «Криптовалюта · USDT», внутри сумма с кнопками и карточки сетей."""
    payments.save_methods(conn, [
        {"code": "u1", "title": "USDT TRC20", "currency": "USDT:TRC20", "details": "", "enabled": True, "auto": "bybit"},
        {"code": "u2", "title": "USDT BEP20", "currency": "USDT:BEP20", "details": "", "enabled": True, "auto": "bybit"}])
    uid, c, token = _client(app, conn)
    page = c.get("/panel/balance").text
    assert "Криптовалюта · USDT" in page and 'id="cx-pane"' in page and 'id="cryptoform"' in page
    assert "USDT (TRC20)" in page and "USDT (BEP20)" in page and "1 000 USDT" in page


def test_usdt_round_amount_tail_only_on_clash(conn, config):
    """Сумма ровная; «хвост» — только когда такую же сумму уже ждём от другого клиента."""
    assert cryptopay.unique_amount(conn, Decimal("10")) == Decimal("10.00")
    conn.execute("INSERT INTO payments (user_id, method, amount_micro, pay_amount, pay_currency, status, auto_kind, "
                 "created_at) VALUES (1, 'usdt', 100000, '10.00', 'USDT', 'pending', 'bybit', ?)", (cryptopay.db.now(),))
    other = cryptopay.unique_amount(conn, Decimal("10"))
    assert Decimal("10") < other < Decimal("10.1") and len(str(other).split(".")[1]) == 3   # 10.001…
    assert cryptopay.unique_amount(conn, Decimal("15")) == Decimal("15.00")


def test_bybit_networks_ready_cards_and_limits(app, config, conn, monkeypatch):
    """Bybit: сети сразу готовыми карточками (TRC20, BEP20, TON, Aptos), у каждой 3 – 5 000 USDT."""
    from conftest import csrf_of
    config.bybit_key, config.bybit_secret = "k", "s"
    cryptopay._addr_cache.clear()
    cryptopay._min_cache.clear()
    payments.save_methods(conn, [{"code": "usdt", "title": "USDT", "currency": "USDT:BEP20", "details": "",
                                  "enabled": True, "auto": "bybit"}])
    conf = payments.settings(conn, config)
    cards = [m for m in conf["all_methods"] if m.get("base") == "usdt"]
    assert [m["network"] for m in cards] == ["TRC20", "BEP20", "TON", "APTOS"]
    assert all(m["min_usd"] == "3" and m["max_usd"] == "5000" for m in cards)

    def fake(cfg, path, params):
        if path.endswith("query-address"):
            return {"chains": [{"chainType": "Aptos", "chain": "APTOS", "addressDeposit": "0xaptos", "tagDeposit": ""},
                               {"chainType": "BEP20", "chain": "BSC", "addressDeposit": "0xbsc", "tagDeposit": ""}]}
        if path.endswith("coin/query-info"):
            return {"rows": [{"coin": "USDT", "chains": [{"chain": "APTOS", "depositMin": "4"}]}]}
        return {"rows": []}
    monkeypatch.setattr(cryptopay, "_bybit_get", fake)
    uid, c, token = _client(app, conn)
    page = c.get("/panel/balance").text
    assert "USDT (Aptos)" in page and "3 – 5 000 USDT за транзакцию" in page
    r = c.post("/panel/balance", data={"csrf": token, "method": "usdt-bep20", "amount": "2"}, follow_redirects=True)
    assert "Минимум для USDT (BEP20) — 3 USDT" in r.text
    r = c.post("/panel/balance", data={"csrf": token, "method": "usdt-bep20", "amount": "6000"}, follow_redirects=True)
    assert "Максимум для USDT (BEP20)" in r.text
    r = c.post("/panel/balance", data={"csrf": token, "method": "usdt-aptos", "amount": "3"}, follow_redirects=True)
    assert "Минимум для USDT (Aptos) — 4 USDT" in r.text            # у Bybit минимум выше нашего
    # старый код «usdt» (боты, API) — его сеть BEP20
    r = c.post("/panel/balance", data={"csrf": token, "method": "usdt", "amount": "10"}, follow_redirects=False)
    p = conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchone()
    assert p["method"] == "usdt-bep20" and p["pay_address"] == "0xbsc" and p["pay_amount"] == "10.00"

    # админка: галочки сетей и свои пределы
    adm = TestClient(app)
    web_login(adm, "admin@example.com", "adminpass123")
    page = adm.get("/admin/pay-settings").text
    assert "Сети USDT" in page and 'name="m0_net_APTOS"' in page
    form = {"csrf": csrf_of(page), "n": "1", "tjs_rate": "10.9", "min_tjs": "0", "low_usd": "0",
            "m0_code": "usdt", "m0_title": "USDT", "m0_currency": "USDT", "m0_details": "", "m0_auto": "bybit",
            "m0_enabled": "1", "m0_nets": "1"}
    for n in payments.BYBIT_NETS:
        form |= {f"m0_min_{n}": "3", f"m0_max_{n}": "5000"}
    form |= {"m0_net_TRC20": "1", "m0_net_SOL": "1", "m0_min_SOL": "5"}
    adm.post("/admin/pay-settings", data=form)
    cards = [m for m in payments.settings(conn, config)["all_methods"] if m.get("base") == "usdt"]
    assert [(m["network"], m["min_usd"]) for m in cards] == [("TRC20", "3"), ("SOL", "5")]


def test_tail_only_for_same_amount_on_same_network(app, config, conn, monkeypatch):
    """Двое платят по 10 $ в BEP20 — второму 10.0xx. Третий платит 10 $ в TRC20 — ровно 10 (другой адрес).
    Перевод в TRC20 не засчитывается заявке BEP20, даже если сумма та же."""
    config.bybit_key, config.bybit_secret = "k", "s"
    cryptopay._addr_cache.clear()
    cryptopay._min_cache.clear()
    payments.save_methods(conn, [{"code": "usdt", "title": "USDT", "currency": "USDT:BEP20", "details": "",
                                  "enabled": True, "auto": "bybit"}])
    deposits = []

    def fake(cfg, path, params):
        if path.endswith("query-address"):
            return {"chains": [{"chainType": "BEP20", "chain": "BSC", "addressDeposit": "0xBsc", "tagDeposit": ""},
                               {"chainType": "TRC20", "chain": "TRX", "addressDeposit": "TTron", "tagDeposit": ""}]}
        return {"rows": deposits if path.endswith("deposit/query-record") else []}
    monkeypatch.setattr(cryptopay, "_bybit_get", fake)
    got = []
    for i, net in enumerate(("bep20", "bep20", "trc20")):
        accounts.create_user(conn, email=f"u{i}@example.com", login=f"user{i}", password="password123", status="active")
        c = TestClient(app)
        token = web_login(c, f"u{i}@example.com", "password123")
        c.post("/panel/balance", data={"csrf": token, "method": f"usdt-{net}", "amount": "10"}, follow_redirects=False)
        got.append(conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchone())
    assert got[0]["pay_amount"] == "10.00" and got[2]["pay_amount"] == "10.00"
    assert Decimal("10") < Decimal(got[1]["pay_amount"]) < Decimal("10.1")
    # 10 USDT пришли на TRC20-адрес — зачислится только заявке TRC20
    deposits.append({"txID": "0xt", "amount": "10", "depositStatus": 3, "toAddress": "TTron",
                     "successAt": str(cryptopay._ms(got[2]["created_at"]) + 5000)})
    cryptopay.reset()
    assert cryptopay.check_all(conn, config) == 1
    st = {r["id"]: r["status"] for r in conn.execute("SELECT id, status FROM payments")}
    assert st[got[2]["id"]] == "paid" and st[got[0]["id"]] == "pending"


def test_tail_always_three_digits(conn, config):
    """Хвост — всегда третья цифра (10.001…10.099, без 10.010): не совпадёт с чужой ровной суммой 10.01."""
    conn.execute("INSERT INTO payments (user_id, method, amount_micro, pay_amount, pay_currency, status, auto_kind, "
                 "created_at) VALUES (1, 'usdt', 100000, '10.00', 'USDT', 'pending', 'bybit', ?)", (cryptopay.db.now(),))
    for _ in range(300):
        tail = str(cryptopay.unique_amount(conn, Decimal("10"))).split(".")[1]
        assert len(tail) == 3 and tail[-1] != "0"

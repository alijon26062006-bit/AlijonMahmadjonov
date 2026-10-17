"""Подарки Telegram и мини-приложение /tg: поддельный Bot API, без сети."""
import hashlib
import hmac
import json
import time
from dataclasses import replace
from urllib.parse import urlencode

import pytest

from conftest import balance

from donatix import accounts, db, tggifts

TOKEN = "123:gift-token"
GIFTS = [{"id": "g15", "star_count": 15, "sticker": {"emoji": "🧸"}},
         {"id": "g25", "star_count": 25, "sticker": {"emoji": "🌹"}},
         {"id": "gprem", "star_count": 50, "is_premium": True, "sticker": {"emoji": "💎"}},
         {"id": "gsold", "star_count": 100, "remaining_count": 0, "total_count": 10, "sticker": {"emoji": "🏆"}}]


class FakeTG:
    def __init__(self):
        self.balance, self.sent, self.txs, self.mode = 1000, [], [], "ok"

    def __call__(self, config, method, timeout=20, **p):
        if method == "getAvailableGifts":
            return {"gifts": GIFTS}
        if method == "getMyStarBalance":
            return {"amount": self.balance}
        if method == "getStarTransactions":
            return {"transactions": self.txs[p.get("offset", 0):p.get("offset", 0) + p.get("limit", 100)]}
        if method == "sendGift":
            if self.mode == "429":
                raise tggifts.ApiError(429, "Too Many Requests", 5)
            if self.mode == "400":
                raise tggifts.ApiError(400, "Bad Request: user not found")
            if self.mode == "net":
                self.txs.append({"id": f"tx{len(self.txs)}", "amount": 15, "date": int(time.time()),
                                 "receiver": {"type": "user", "transaction_type": "gift_purchase",
                                              "user": {"id": p["user_id"]}, "gift": {"id": p["gift_id"]}}})
                raise tggifts.NetError("ReadTimeout")
            self.sent.append(p)
            self.balance -= 15
            return True
        return {}


@pytest.fixture
def fake(monkeypatch):
    f = FakeTG()
    monkeypatch.setattr(tggifts, "call", f)
    monkeypatch.setattr("donatix.worker.notify_admin", lambda *a, **k: None)
    return f


@pytest.fixture
def gcfg(config):
    return replace(config, gift_bot_token=TOKEN)


def _user(conn, login="giftbuyer", money=1_000_000):
    uid = accounts.create_user(conn, email=f"{login}@example.com", login=login, password="password123", status="active")
    with db.tx(conn):
        accounts.post_ledger(conn, uid, money, "Пополнение")
    return accounts.get_user(conn, uid)


def test_sync_hides_premium_and_sold_out(conn, gcfg, fake):
    assert tggifts.sync(conn, gcfg, force=True) == 2
    assert [g["id"] for g in tggifts.listing(conn, gcfg, None)] == ["g15", "g25"]


def test_price_follows_star_price(conn, gcfg, fake):
    tggifts.sync(conn, gcfg, force=True)
    u = _user(conn)
    p15 = tggifts.price_micro(conn, gcfg, u, 15)
    assert p15 == pytest.approx(int(tggifts.star_price_usd(conn, gcfg, u) * 15 * 10_000), abs=1)
    db.set_setting(conn, "gifts.markup_pct", "10")
    assert tggifts.price_micro(conn, gcfg, u, 15) > p15


def test_buy_self_and_send(conn, gcfg, fake):
    tggifts.sync(conn, gcfg, force=True)
    u = _user(conn)
    o = tggifts.buy(conn, gcfg, u, "g15", recipient_id=555, recipient="Me", text="Табрик!")
    assert o["status"] == "paid" and balance(conn, u["id"]) == 1_000_000 - o["price_micro"]
    assert tggifts.send_pending(conn, gcfg) == 1
    assert fake.sent[0] == {"user_id": 555, "gift_id": "g15", "text": "Табрик!"}
    assert tggifts.get(conn, o["id"])["status"] == "sent"
    assert tggifts.send_pending(conn, gcfg) == 0          # второй раз не отправляем


def test_429_stays_paid(conn, gcfg, fake):
    tggifts.sync(conn, gcfg, force=True)
    o = tggifts.buy(conn, gcfg, _user(conn), "g15", recipient_id=1)
    fake.mode = "429"
    tggifts.send_pending(conn, gcfg)
    assert tggifts.get(conn, o["id"])["status"] == "paid"


def test_400_fails_and_refunds(conn, gcfg, fake):
    tggifts.sync(conn, gcfg, force=True)
    u = _user(conn)
    o = tggifts.buy(conn, gcfg, u, "g15", recipient_id=1)
    fake.mode = "400"
    tggifts.send_pending(conn, gcfg)
    got = tggifts.get(conn, o["id"])
    assert got["status"] == "failed" and "user not found" in got["error"]
    assert balance(conn, u["id"]) == 1_000_000


def test_network_unknown_then_reconciled(conn, gcfg, fake):
    tggifts.sync(conn, gcfg, force=True)
    o = tggifts.buy(conn, gcfg, _user(conn), "g15", recipient_id=777)
    fake.mode = "net"
    tggifts.send_pending(conn, gcfg)
    assert tggifts.get(conn, o["id"])["status"] == "unknown"
    assert tggifts.reconcile(conn, gcfg) == 1                 # нашли в истории Stars — не повторяем
    got = tggifts.get(conn, o["id"])
    assert got["status"] == "sent" and got["tx_id"] == "tx0"


def test_unknown_not_found_goes_back_to_paid(conn, gcfg, fake):
    tggifts.sync(conn, gcfg, force=True)
    o = tggifts.buy(conn, gcfg, _user(conn), "g15", recipient_id=777)
    conn.execute("UPDATE gift_orders SET status = 'unknown', sending_at = ? WHERE id = ?",
                 (time.time() - 20 * 60, o["id"]))
    tggifts.reconcile(conn, gcfg)
    assert tggifts.get(conn, o["id"])["status"] == "paid"


def test_not_enough_stars_waits(conn, gcfg, fake):
    tggifts.sync(conn, gcfg, force=True)
    o = tggifts.buy(conn, gcfg, _user(conn), "g25", recipient_id=1)
    fake.balance = 10
    assert tggifts.send_pending(conn, gcfg) == 0
    assert tggifts.get(conn, o["id"])["status"] == "paid" and not fake.sent


def test_friend_link_claim_and_expire(conn, gcfg, fake):
    tggifts.sync(conn, gcfg, force=True)
    u = _user(conn)
    o = tggifts.buy(conn, gcfg, u, "g15", recipient="@friend")
    assert o["status"] == "awaiting_recipient"
    c = tggifts.claim_link(conn, o["link_token"], {"id": 4242, "first_name": "Ali", "username": "friend"})
    assert c["claimed"] and c["recipient_id"] == 4242 and c["status"] == "paid"
    assert not tggifts.claim_link(conn, o["link_token"], {"id": 1})["claimed"]     # второй раз — нет
    o2 = tggifts.buy(conn, gcfg, u, "g15", recipient="@nobody")
    conn.execute("UPDATE gift_orders SET created_at = '2000-01-01T00:00:00' WHERE id = ?", (o2["id"],))
    before = balance(conn, u["id"])
    assert tggifts.expire(conn, gcfg) == 1
    assert balance(conn, u["id"]) == before + o2["price_micro"]
    assert tggifts.find_username(conn, "@Friend")["tg_id"] == 4242


def test_insufficient_balance(conn, gcfg, fake):
    tggifts.sync(conn, gcfg, force=True)
    with pytest.raises(tggifts.GiftError):
        tggifts.buy(conn, gcfg, _user(conn, money=10), "g15", recipient_id=1)


# ── мини-приложение ──

def _init(token, user):
    data = {"auth_date": str(int(time.time())), "user": json.dumps(user), "query_id": "q"}
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


@pytest.fixture
def tgclient(app, gcfg, fake):
    app.state.config = gcfg
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_app_requires_signature(tgclient):
    assert tgclient.post("/tg/api/init", json={}).status_code == 403
    assert tgclient.post("/tg/api/init", json={}, headers={"X-Tg-Init": _init("bad:token", {"id": 1})}).status_code == 403
    assert "Telegram Stars" in tgclient.get("/tg").text or tgclient.get("/tg").status_code == 200


def test_app_init_and_buy_flow(tgclient, conn, gcfg, fake):
    tggifts.sync(conn, gcfg, force=True)
    h = {"X-Tg-Init": _init(TOKEN, {"id": 9001, "first_name": "Uways", "username": "uwayscoder", "language_code": "ru"})}
    d = tgclient.post("/tg/api/init", json={}, headers=h).json()
    assert d["me"]["id"] == 9001 and d["me"]["balance"] == 0 and len(d["gifts"]) == 2
    assert d["stars"] and d["stars"]["min"] >= 50
    r = tgclient.post("/tg/api/buy", json={"type": "gift", "gift_id": "g15", "to": "self"}, headers=h).json()
    assert r["ok"] is False and r["need"] > 0                    # денег нет — предложим пополнить
    uid = conn.execute("SELECT user_id FROM shop_users WHERE tg_id = 9001").fetchone()[0]
    with db.tx(conn):
        accounts.post_ledger(conn, uid, 10_000_000, "Пополнение")
    r = tgclient.post("/tg/api/buy", json={"type": "gift", "gift_id": "g15", "to": "self"}, headers=h).json()
    assert r["ok"] and not r.get("link")
    o = conn.execute("SELECT * FROM gift_orders WHERE user_id = ?", (uid,)).fetchone()
    assert o["recipient_id"] == 9001 and o["status"] == "paid"
    r = tgclient.post("/tg/api/buy", json={"type": "gift", "gift_id": "g25", "to": "friend", "username": "@stranger"},
                      headers=h).json()
    assert r["ok"] and "start=g_" in r["link"]
    r = tgclient.post("/tg/api/buy", json={"type": "stars", "qty": 50, "to": "self", "idem": "x1"}, headers=h).json()
    assert r["ok"], r
    assert conn.execute("SELECT source FROM orders WHERE user_id = ? AND kind = 'telegram_stars'", (uid,)).fetchone()[0] == "tgapp"
    hist = tgclient.post("/tg/api/history", json={}, headers=h).json()["items"]
    assert len(hist) == 3


def test_admin_gifts_page(client, conn):
    from conftest import web_login
    web_login(client, "admin@example.com", "adminpass123")
    assert "Подарки Telegram" in client.get("/admin/gifts").text


def _bot(gcfg, calls):
    from donatix import giftbot
    b = giftbot.GiftBot(gcfg)
    b.api = lambda method, **p: calls.append((method, p)) or {}
    return b


def test_bot_topup_only_admin_and_precheckout(conn, gcfg, fake):
    from dataclasses import replace as _r
    cfg = _r(gcfg, shop_admin_ids="111")
    calls = []
    b = _bot(cfg, calls)

    def msg(uid, text):
        return {"message": {"chat": {"id": uid, "type": "private"}, "from": {"id": uid}, "text": text}}
    b.handle(conn, msg(222, "/topup 500"))
    assert not any(m == "sendInvoice" for m, _ in calls)       # не админ — счёта нет
    b.handle(conn, msg(111, "/topup 500"))
    inv = next(p for m, p in calls if m == "sendInvoice")
    assert inv["currency"] == "XTR" and inv["provider_token"] == "" and inv["prices"][0]["amount"] == 500
    b.handle(conn, {"pre_checkout_query": {"id": "q1", "from": {"id": 111}, "invoice_payload": inv["payload"]}})
    assert ("answerPreCheckoutQuery", {"pre_checkout_query_id": "q1", "ok": True, "error_message": None}) in calls
    b.handle(conn, {"pre_checkout_query": {"id": "q2", "from": {"id": 222}, "invoice_payload": inv["payload"]}})
    assert any(m == "answerPreCheckoutQuery" and p["ok"] is False for m, p in calls)


def test_bot_start_claims_gift(conn, gcfg, fake):
    tggifts.sync(conn, gcfg, force=True)
    o = tggifts.buy(conn, gcfg, _user(conn), "g15", recipient="@pal")
    calls = []
    _bot(gcfg, calls).handle(conn, {"message": {"chat": {"id": 31, "type": "private"},
                                                "from": {"id": 31, "first_name": "Pal", "language_code": "ru"},
                                                "text": f"/start g_{o['link_token']}"}})
    assert tggifts.get(conn, o["id"])["recipient_id"] == 31
    assert any(m == "sendMessage" and "web_app" in json.dumps(p) for m, p in calls)   # кнопка «Открыть магазин»

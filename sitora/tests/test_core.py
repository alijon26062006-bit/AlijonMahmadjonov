import pytest

from sitora import db, receipt, shop
from sitora.money import fmt, price, to_diram
from sitora.tg import check_init_data, sign_init_data
from sitora.worker import ATTENTION_AFTER, Worker
from conftest import TOKEN


def user(conn, uid=1, name="ali_dev", balance=0):
    shop.touch_user(conn, {"id": uid, "username": name, "first_name": "Али"})
    if balance:
        with db.tx(conn):
            shop.move(conn, uid, balance, "seed")


def bal(conn, uid=1):
    return conn.execute("SELECT balance FROM users WHERE id = ?", (uid,)).fetchone()[0]


def test_money():
    assert fmt(124050000) == "1 240 500" and fmt(1950) == "19,5" and fmt(-725) == "-7,25"
    assert to_diram("19,5") == 1950
    assert price(__import__("decimal").Decimal("1.5"), 11, 10) == 1820   # 1.5*11*1.1 = 18.15 → вверх до 10 дирам


def test_init_data_signature():
    good = sign_init_data({"id": 5, "username": "x"}, TOKEN)
    assert check_init_data(good, TOKEN)["id"] == 5
    assert check_init_data(good, "999:other") is None                      # чужой бот
    assert check_init_data(good.replace("x", "y"), TOKEN) is None          # подмена данных
    assert check_init_data(sign_init_data({"id": 5}, TOKEN, auth_date=1), TOKEN) is None   # старая подпись


def test_catalog_and_quote(conn):
    cat = shop.catalog(conn)
    assert [p["qty"] for p in cat["stars"]["packs"]] == [50, 100, 250, 500, 1000, 2500]
    assert cat["premium"][0] == {"months": 3, "price": price(__import__("decimal").Decimal("12"), 11, 10)}
    assert shop.quote(conn, {"kind": "stars", "qty": 100})["price"] == price(__import__("decimal").Decimal("1.5"), 11, 10)
    with pytest.raises(shop.ShopError):
        shop.quote(conn, {"kind": "stars", "qty": 10})       # меньше минимума


def test_order_needs_money_and_valid_username(conn):
    user(conn)
    with pytest.raises(shop.ShopError, match="не хватает"):
        shop.place_order(conn, 1, {"kind": "stars", "qty": 100, "to": "@ali_dev"})
    user(conn, balance=100000)
    with pytest.raises(shop.ShopError, match="username"):
        shop.place_order(conn, 1, {"kind": "stars", "qty": 100, "to": "@a"})
    assert bal(conn) == 100000                                    # ничего не списано


def test_stars_order_completes(config, conn, supplier, fake):
    user(conn, balance=100000)
    o = shop.place_order(conn, 1, {"kind": "stars", "qty": 100, "to": "https://t.me/ali_dev"})
    assert o["recipient"] == "ali_dev" and bal(conn) == 100000 - o["price"]
    w = Worker(config, None, supplier)
    w.send_new()
    m, path, idem, body = fake.calls[-1]
    assert path.endswith("/telegram/stars/buy") and idem == f"sitora-{o['id']}" and body == {"telegram_username": "ali_dev", "quantity": 100}
    w.poll()
    assert conn.execute("SELECT status FROM orders WHERE id = ?", (o["id"],)).fetchone()[0] == "completed"


def test_rejected_order_is_refunded_once(config, conn, supplier, fake):
    user(conn, balance=100000)
    o = shop.place_order(conn, 1, {"kind": "premium", "months": 3, "to": "@ali_dev"})
    fake.fail = "reject"
    w = Worker(config, None, supplier)
    w.send_new()
    assert bal(conn) == 100000
    assert shop.refund(conn, o["id"], "again") is False           # второй раз не вернём


def test_no_connection_never_refunds_and_reuses_key(config, conn, supplier, fake):
    user(conn, balance=100000)
    o = shop.place_order(conn, 1, {"kind": "stars", "qty": 50, "to": "@ali_dev"})
    fake.fail = "net"
    w = Worker(config, None, supplier)
    for _ in range(ATTENTION_AFTER):
        w.send_new()
    row = conn.execute("SELECT * FROM orders WHERE id = ?", (o["id"],)).fetchone()
    assert row["status"] == "attention" and bal(conn) == 100000 - o["price"]   # деньги не вернули — неизвестно
    assert {c[2] for c in fake.calls} == {f"sitora-{o['id']}"}                  # всегда тот же ключ
    fake.fail = None
    conn.execute("UPDATE orders SET tries = 24 WHERE id = ?", (o["id"],))
    w.send_new()
    assert conn.execute("SELECT status FROM orders WHERE id = ?", (o["id"],)).fetchone()[0] == "processing"


def test_supplier_failed_later_refunds(config, conn, supplier, fake):
    user(conn, balance=100000)
    o = shop.place_order(conn, 1, {"kind": "stars", "qty": 50, "to": "@ali_dev"})
    fake.order = {"ok": True, "order": {"status": "refunded"}}
    w = Worker(config, None, supplier)
    w.send_new(); w.poll()
    assert bal(conn) == 100000 and conn.execute("SELECT status FROM orders").fetchone()[0] == "failed"


def test_gift_to_self_and_by_link(config, conn, bot, faketg):
    user(conn, balance=100000)
    a = shop.place_order(conn, 1, {"kind": "gift", "gift_id": "g1"})
    assert a["status"] == "paid" and a["recipient_id"] == 1
    b = shop.place_order(conn, 1, {"kind": "gift", "gift_id": "g1", "to": "@friend_x"})
    assert b["status"] == "awaiting_recipient" and b["gift_token"]
    w = Worker(config, bot, None)
    w.send_gifts()
    assert faketg.methods().count("sendGift") == 1
    user(conn, uid=2, name="friend_x")
    got = shop.claim_gift(conn, b["gift_token"], 2)
    assert got["recipient_id"] == 2 and shop.claim_gift(conn, b["gift_token"], 3) is None   # ссылка одноразовая
    w.send_gifts()
    assert conn.execute("SELECT status FROM orders WHERE id = ?", (b["id"],)).fetchone()[0] == "sent"


def test_gift_known_username_goes_direct(conn):
    user(conn, balance=100000)
    user(conn, uid=2, name="Friend_X")
    o = shop.place_order(conn, 1, {"kind": "gift", "gift_id": "g1", "to": "@friend_x"})
    assert o["status"] == "paid" and o["recipient_id"] == 2


def test_gift_refused_by_telegram_is_refunded(config, conn, bot, faketg):
    user(conn, balance=100000)
    shop.place_order(conn, 1, {"kind": "gift", "gift_id": "g1"})
    faketg.gift_error = "Bad Request: BALANCE_TOO_LOW"
    Worker(config, bot, None).send_gifts()
    assert bal(conn) == 100000


def test_unclaimed_gift_expires(config, conn):
    user(conn, balance=100000)
    o = shop.place_order(conn, 1, {"kind": "gift", "gift_id": "g1", "to": "@nobody_here"})
    conn.execute("UPDATE orders SET created_at = '2020-01-01T00:00:00Z' WHERE id = ?", (o["id"],))
    Worker(config, None, None).expire_gifts()
    assert bal(conn) == 100000


def test_topup_with_intent_buys_after_confirm(conn):
    user(conn)
    intent = {"kind": "stars", "qty": 100, "to": "@ali_dev"}
    need = shop.quote(conn, intent)["price"]
    t = shop.create_topup(conn, 1, "alif", need, intent)
    assert "+992 90 000 00 00" in shop.topup_view(conn, t)["details"]
    conn.execute("UPDATE topups SET status = 'pending' WHERE id = ?", (t["id"],))
    done = shop.decide_topup(conn, t["id"], True, "admin")
    assert shop.decide_topup(conn, t["id"], True, "admin2") is None       # второй раз не зачислит
    o = shop.run_intent(conn, done)
    assert o["title"] == "100 Stars" and bal(conn) == 0


def test_receipt_rules():
    ours = "Алиф +992 90 000 00 00 Али\nДС 4444 5555 6666 7777"
    assert receipt.refuse({"is_receipt": False}, ours) == receipt.NOT_RECEIPT
    assert receipt.refuse({"is_receipt": True, "recipient": ""}, ours) == receipt.NO_DETAILS
    assert receipt.refuse({"is_receipt": True, "recipient": "+992 93 111 22 33"}, ours) == receipt.WRONG_DETAILS
    assert receipt.refuse({"is_receipt": True, "recipient": "+992 90 *** 00 00"}, ours) is None
    assert receipt.refuse({"is_receipt": True, "recipient": "4444 55** **** 7777"}, ours) is None
    assert receipt.refuse({"is_receipt": True, "recipient": "Али В."}, ours) is None          # только имя — админу
    assert receipt.refuse(None, ours) is None                                                # ИИ не прочитал — админу


def test_client_price_formula_matches_server(conn):
    import math
    per = shop.catalog(conn)["stars"]["per_star_diram"]
    for q in (50, 77, 133, 999, 4321):
        assert math.ceil(q * per / 10 - 1e-9) * 10 == shop.stars_price(conn, q)

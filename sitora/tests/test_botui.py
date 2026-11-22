"""Магазин и админ-панель в чате бота: кнопки, ввод текстом, ручные цены, права."""
import json
import time
from urllib.parse import parse_qs

from sitora import db, shop
from sitora.bot import Handler

PNG = b"\x89PNG\r\n\x1a\n" + b"1" * 64


def msg(uid, text=None, username="ali_dev", **extra):
    m = {"from": {"id": uid, "username": username, "first_name": "Али", "language_code": "ru"},
         "chat": {"id": uid, "type": "private"}, **extra}
    if text is not None:
        m["text"] = text
    return {"message": m}


def press(uid, data, mid=10, username="ali_dev"):
    return {"callback_query": {"id": "q", "data": data, "message": {"message_id": mid},
                               "from": {"id": uid, "username": username, "first_name": "Али"}}}


def sent(faketg, n=1):
    """Последние тексты, которые бот отправил или поставил в сообщение."""
    out = []
    for m, body in faketg.calls:
        if m in ("sendMessage", "editMessageText"):
            q = parse_qs(body.decode())
            out.append((q.get("text", [""])[0], json.loads(q.get("reply_markup", ["{}"])[0] or "{}")))
    return out[-n:] if n > 1 else out[-1]


def buttons(markup):
    return [x.get("callback_data") for row in markup.get("inline_keyboard", []) for x in row]


def test_buy_stars_inside_bot(config, conn, bot, faketg):
    h = Handler(config, bot)
    h.handle(msg(1, "/start"))
    conn.execute("UPDATE users SET balance = 50000 WHERE id = 1")
    h.handle(press(1, "c:stars"))
    text, kb = sent(faketg)
    assert "Telegram Stars" in text and "c:sq:100" in buttons(kb)
    h.handle(press(1, "c:sq:100"))
    h.handle(msg(1, "@friend_tj"))
    text, kb = sent(faketg)
    assert "@friend_tj" in text and "c:pay" in buttons(kb)
    h.handle(press(1, "c:pay"))
    text, _ = sent(faketg)
    assert "оплачен" in text
    o = conn.execute("SELECT * FROM orders").fetchone()
    assert o["recipient"] == "friend_tj" and o["qty"] == 100 and o["cost_usd"] == "1.500"
    assert conn.execute("SELECT state FROM chat_state WHERE user_id = 1").fetchone() is None


def test_custom_qty_and_bad_username(config, conn, bot, faketg):
    h = Handler(config, bot)
    h.handle(msg(1, "/start"))
    h.handle(press(1, "c:sown"))
    h.handle(msg(1, "abc"))
    assert "число" in sent(faketg)[0]
    h.handle(msg(1, "333"))
    h.handle(msg(1, "плохой ник"))
    assert "@username" in sent(faketg)[0]
    h.handle(press(1, "c:self"))
    text, kb = sent(faketg)
    assert "333 Stars" in text and "c:tneed" in buttons(kb)   # денег нет — предлагаем пополнить ровно на недостающее


def test_topup_in_chat_with_photo_receipt(config, conn, bot, faketg):
    faketg.file_bytes = PNG
    h = Handler(config, bot)
    h.handle(msg(1, "/start"))
    h.handle(press(1, "c:top"))
    h.handle(msg(1, "0,5"))
    assert "Минимальная" in sent(faketg)[0]
    h.handle(msg(1, "20"))
    h.handle(press(1, "c:tm:alif"))
    text, _ = sent(faketg)
    assert "20,00" in text or "20 " in text
    h.handle(msg(1, photo=[{"file_id": "P1"}]))
    t = conn.execute("SELECT * FROM topups").fetchone()
    assert t["status"] == "pending" and t["amount"] == 2000
    for _ in range(50):
        if conn.execute("SELECT admin_msgs FROM topups").fetchone()[0]:
            break
        time.sleep(0.02)
    h.handle(press(999, f"tp:ok:{t['id']}", username="boss"))
    assert conn.execute("SELECT balance FROM users WHERE id = 1").fetchone()[0] == 2000


def test_photo_without_topup_is_explained(config, conn, bot, faketg):
    h = Handler(config, bot)
    h.handle(msg(1, photo=[{"file_id": "P1"}]))
    assert "Пополнить" in sent(faketg)[0]


def test_admin_sets_manual_pack_price(config, conn, bot, faketg):
    h = Handler(config, bot)
    h.handle(msg(999, "/start", username="boss"))
    h.handle(msg(999, "/admin", username="boss"))
    assert "Панель" in sent(faketg)[0]
    h.handle(press(999, "a:ps", username="boss"))
    h.handle(press(999, "a:pk:stars:500", username="boss"))
    text, kb = sent(faketg)
    assert "Закупка" in text and "Прибыль" in text
    h.handle(press(999, "a:pfix:stars:500", username="boss"))
    h.handle(msg(999, "95", username="boss"))
    assert "95,00" in sent(faketg)[0] or "95" in sent(faketg)[0]
    assert shop.quote(conn, {"kind": "stars", "qty": 500})["price"] == 9500
    assert shop.quote(conn, {"kind": "stars", "qty": 501})["price"] != 9500       # своё кол-во — по формуле
    assert {p["qty"]: p["price"] for p in shop.public_catalog(conn)["stars"]["packs"]}[500] == 9500
    h.handle(press(999, "a:phide:stars:500", username="boss"))
    assert 500 not in [p["qty"] for p in shop.public_catalog(conn)["stars"]["packs"]]
    h.handle(press(999, "a:pauto:stars:500", username="boss"))
    h.handle(press(999, "a:phide:stars:500", username="boss"))
    assert shop.quote(conn, {"kind": "stars", "qty": 500})["price"] != 9500


def test_admin_premium_and_gift_prices_and_new_pack(config, conn, bot, faketg):
    h = Handler(config, bot)
    h.handle(msg(999, "/start", username="boss"))
    h.handle(press(999, "a:pfix:premium:3", username="boss"))
    h.handle(msg(999, "150,5", username="boss"))
    assert shop.quote(conn, {"kind": "premium", "months": 3})["price"] == 15050
    h.handle(press(999, "a:pfix:gift:g1", username="boss"))
    h.handle(msg(999, "4", username="boss"))
    assert shop.quote(conn, {"kind": "gift", "gift_id": "g1"})["price"] == 400
    h.handle(press(999, "a:padd", username="boss"))
    h.handle(msg(999, "750 140", username="boss"))
    packs = {p["qty"]: p["price"] for p in shop.public_catalog(conn)["stars"]["packs"]}
    assert packs[750] == 14000
    h.handle(press(999, "a:pdel:750", username="boss"))
    assert 750 not in [p["qty"] for p in shop.public_catalog(conn)["stars"]["packs"]]


def test_client_cannot_use_admin_buttons(config, conn, bot, faketg):
    h = Handler(config, bot)
    h.handle(msg(1, "/start"))
    h.handle(press(1, "a:pfix:stars:500"))
    h.handle(msg(1, "1"))
    assert shop.fixed_prices(conn) == {}
    h.handle(press(1, "a:pause"))
    assert not shop.paused(conn)
    h.handle(press(1, "a:addadm"))
    assert shop.admin_list(conn, config) == [999]


def test_pause_blocks_sales(config, conn, bot, faketg):
    h = Handler(config, bot)
    h.handle(msg(999, "/start", username="boss"))
    h.handle(press(999, "a:pause", username="boss"))
    assert shop.paused(conn)
    conn.execute("UPDATE users SET balance = 50000 WHERE id = 999")
    h.handle(press(999, "c:sq:100", username="boss"))
    h.handle(press(999, "c:self", username="boss"))
    h.handle(press(999, "c:pay", username="boss"))
    assert "пауз" in sent(faketg)[0]
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0


def test_admin_balance_block_broadcast_and_admins(config, conn, bot, faketg):
    h = Handler(config, bot)
    h.handle(msg(1, "/start"))
    h.handle(msg(999, "/start", username="boss"))
    h.handle(press(999, "a:give:1", username="boss"))
    h.handle(msg(999, "50 бонус", username="boss"))
    assert conn.execute("SELECT balance FROM users WHERE id = 1").fetchone()[0] == 5000
    h.handle(press(999, "a:ban:1", username="boss"))
    assert conn.execute("SELECT banned FROM users WHERE id = 1").fetchone()[0] == 1
    h.handle(press(999, "a:bc", username="boss"))
    h.handle(msg(999, "Скидки сегодня!", username="boss"))
    h.handle(press(999, "a:bcgo", username="boss"))
    for _ in range(100):
        if any("Рассылка готова" in x[0] for x in sent(faketg, 50)):
            break
        time.sleep(0.02)
    assert any("Рассылка готова: доставлено 1 из 1" in x[0] for x in sent(faketg, 50))   # заблокированному не шлём
    h.handle(press(999, "a:addadm", username="boss"))
    h.handle(msg(999, "777", username="boss"))
    assert 777 in shop.admin_list(conn, config)
    h.handle(press(999, "a:deladm:777", username="boss"))
    assert 777 not in shop.admin_list(conn, config)


def test_admin_settings_rate_markup_min(config, conn, bot, faketg):
    h = Handler(config, bot)
    h.handle(msg(999, "/start", username="boss"))
    for what, val in (("rate", "11,5"), ("markup", "15"), ("min", "5")):
        h.handle(press(999, f"a:pset:{what}", username="boss"))
        h.handle(msg(999, val, username="boss"))
    assert str(shop.rate(conn)) == "11.5" and str(shop.markup(conn)) == "15" and shop.min_topup(conn) == 500
    h.handle(press(999, "a:pset:rate", username="boss"))
    h.handle(msg(999, "99", username="boss"))
    assert str(shop.rate(conn)) == "11.5"


def test_admin_orders_refund_and_stats(config, conn, bot, faketg):
    h = Handler(config, bot)
    h.handle(msg(1, "/start"))
    conn.execute("UPDATE users SET balance = 50000 WHERE id = 1")
    o = shop.place_order(conn, 1, {"kind": "stars", "qty": 100, "to": "@friend_tj"})
    h.handle(msg(999, "/start", username="boss"))
    h.handle(press(999, f"a:o:{o['id']}", username="boss"))
    h.handle(press(999, f"a:oa:{o['id']}:refund", username="boss"))
    assert conn.execute("SELECT status FROM orders").fetchone()[0] == "failed"
    assert conn.execute("SELECT balance FROM users WHERE id = 1").fetchone()[0] == 50000
    h.handle(press(999, "a:st", username="boss"))
    assert "Статистика" in sent(faketg)[0]
    for screen in ("a:home", "a:chk", "a:ord", "a:pr", "a:pp", "a:pg:0", "a:cards", "a:cl", "a:set", "a:u:1"):
        h.handle(press(999, screen, username="boss"))
        assert sent(faketg)[0]

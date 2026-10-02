"""Бот-магазин проекта: покупка кнопками, баланс с чеком, статусы, статистика, рассылка."""

from conftest import RECEIPT_PNG, balance, web_login
from fastapi.testclient import TestClient

from donatix import accounts, db, orders, payments, shopbot

TG = 700001


class FakeApi:
    def __init__(self, photo: bytes = b""):
        self.calls: list[tuple[str, dict]] = []
        self.photo = photo
        self.mid = 100

    def __call__(self, method, **p):
        self.calls.append((method, p))
        if method == "sendMessage":
            self.mid += 1
            return {"message_id": self.mid}
        return {}

    def download(self, file_id, max_bytes=0):
        return self.photo

    def last_text(self) -> str:
        return next(p["text"] for m, p in reversed(self.calls) if m in ("sendMessage", "editMessageText"))

    def last_buttons(self) -> list[dict]:
        for m, p in reversed(self.calls):
            if m in ("sendMessage", "editMessageText"):
                return [b for row in (p.get("reply_markup") or {}).get("inline_keyboard", []) for b in row]
        return []

    def button(self, text_part: str) -> str:
        return next(b["callback_data"] for b in self.last_buttons() if text_part in b["text"])


def msg(text: str, **extra):
    return {"update_id": 1, "message": {"chat": {"id": TG, "type": "private"},
                                        "from": {"id": TG, "first_name": "Али"}, "text": text, **extra}}


def press(data: str, mid: int = 101):
    return {"update_id": 1, "callback_query": {"id": "q", "data": data, "from": {"id": TG},
                                               "message": {"message_id": mid,
                                                           "chat": {"id": TG, "type": "private"}}}}


def _bot(config, supplier, api=None):
    return shopbot.ShopBot(config, supplier, api=api or FakeApi())


def _start(bot, conn, lang="ru"):
    bot.handle(conn, msg("/start"))
    bot.handle(conn, press(f"l:{lang}"))
    return shopbot.shop_user(conn, TG)


def _fund(conn, uid, micro=1_000_000):
    with db.tx(conn):
        accounts.post_ledger(conn, uid, micro, "Пополнение")


def test_start_creates_account_and_shows_menu(app, config, conn, supplier):
    bot = _bot(config, supplier)
    su = _start(bot, conn)
    user = accounts.get_user(conn, su["user_id"])
    assert user["status"] == "active" and user["login"] == f"tg{TG}"
    text = bot.api.last_text()
    assert "Али" in text and "Баланс" in text
    styles = {b["text"]: b.get("style") for b in bot.api.last_buttons()}
    assert styles["🎮 Игры"] == "primary" and styles["💰 Баланс"] == "success"
    bot.handle(conn, msg("/start"))                                   # второй раз — тот же аккаунт
    assert conn.execute("SELECT COUNT(*) FROM shop_users").fetchone()[0] == 1


def test_buy_game_by_buttons_saves_player_id_and_counts_in_stats(app, config, conn, supplier):
    bot = _bot(config, supplier)
    su = _start(bot, conn)
    _fund(conn, su["user_id"])
    bot.handle(conn, press("g:games:0"))
    bot.handle(conn, press(bot.api.button("PUBG")))
    assert "PUBG Mobile" in bot.api.last_text() and "смн" in bot.api.last_buttons()[0]["text"]
    bot.handle(conn, press(bot.api.last_buttons()[0]["callback_data"]))
    assert "✍️" in bot.api.last_text()
    bot.handle(conn, msg("5123456789"))
    assert "Проверьте заказ" in bot.api.last_text() and "5123456789" in bot.api.last_text()
    pay = next(b for b in bot.api.last_buttons() if b["callback_data"] == "ok")
    assert pay["style"] == "success"
    before = balance(conn, su["user_id"])
    bot.handle(conn, press("ok"))
    bot.handle(conn, press("ok"))                                     # двойное нажатие — один заказ
    rows = conn.execute("SELECT * FROM orders WHERE user_id = ?", (su["user_id"],)).fetchall()
    assert len(rows) == 1 and rows[0]["source"] == "shopbot" and balance(conn, su["user_id"]) < before
    assert "принят" in next(p["text"] for m, p in bot.api.calls if "принят" in p.get("text", ""))

    # готово — бот сам пишет; повтор — ID уже знает
    orders.complete(conn, rows[0]["id"], {"message": "Зачислено"}, "completed")
    bot.watch(conn, force=True)
    assert "выполнен" in bot.api.last_text() and "Зачислено" in bot.api.last_text()
    bot.handle(conn, press("g:games:0"))
    bot.handle(conn, press(bot.api.button("PUBG")))
    bot.handle(conn, press(bot.api.last_buttons()[0]["callback_data"]))
    bot.handle(conn, press(bot.api.button("💾")))
    assert "Проверьте заказ" in bot.api.last_text()

    s = shopbot.stats(conn, 1)
    assert s["orders"] == 1 and s["revenue"] == rows[0]["total_micro"] and s["new_users"] == 1


def test_stars_ask_quantity(app, config, conn, supplier):
    bot = _bot(config, supplier)
    su = _start(bot, conn)
    _fund(conn, su["user_id"])
    rid = conn.execute("SELECT rowid FROM products WHERE id = 'tg-stars'").fetchone()[0]
    bot.handle(conn, press(f"p:{rid}"))
    bot.handle(conn, msg("@durov"))
    assert "Сколько" in bot.api.last_text()
    bot.handle(conn, press("q:100"))
    assert "× 100" in bot.api.last_text()


def test_not_enough_money_topup_with_receipt_then_buy(app, config, conn, supplier, monkeypatch):
    monkeypatch.setattr("donatix.tgbot.send_receipt", lambda *a, **k: None)
    config.pay_methods = {"alif": "Алиф: +992 90 000 00 00"}
    api = FakeApi(photo=RECEIPT_PNG)
    bot = _bot(config, supplier, api)
    su = _start(bot, conn)
    rid = conn.execute("SELECT rowid FROM products WHERE id = 'topup-pubg-60'").fetchone()
    rid = rid[0] if rid else conn.execute("SELECT rowid FROM products WHERE kind = 'topup' LIMIT 1").fetchone()[0]
    bot.handle(conn, press(f"p:{rid}"))
    bot.handle(conn, msg("5123456789"))
    assert "Не хватает" in api.last_text()
    bot.handle(conn, press("t"))
    bot.handle(conn, press(api.button("Ал")))
    bot.handle(conn, press("ta:100"))
    assert "+992" in api.last_text() and "фото чека" in api.last_text()
    bot.handle(conn, {"update_id": 2, "message": {"chat": {"id": TG, "type": "private"}, "from": {"id": TG},
                                                  "photo": [{"file_id": "f1"}]}})
    assert "Проверяем чек" in api.last_text()
    p = conn.execute("SELECT * FROM payments WHERE user_id = ?", (su["user_id"],)).fetchone()
    assert p["receipt_file"] and p["pay_amount"] == "100.00"
    payments.confirm(conn, config, p["id"], 1)
    bot.watch(conn, force=True)
    assert "Проверьте заказ" in api.last_text()                     # после пополнения — сразу к покупке
    assert any("Баланс пополнен" in pp.get("text", "") for m, pp in api.calls)


def test_tajik_language(app, config, conn, supplier):
    bot = _bot(config, supplier)
    _start(bot, conn, "tj")
    assert "Бозиҳо" in str(bot.api.last_buttons())


def test_deep_link_opens_game(app, config, conn, supplier):
    bot = _bot(config, supplier)
    _start(bot, conn)
    rid = conn.execute("SELECT MIN(rowid) FROM products WHERE category_id = 'free_fire'").fetchone()[0]
    bot.handle(conn, msg(f"/start g{rid}"))
    assert "Free Fire" in bot.api.last_text()


def test_cannot_see_other_users_order(app, config, conn, supplier, shop):
    bot = _bot(config, supplier)
    _start(bot, conn)
    other, _ = orders.create_order(conn, config, supplier, accounts.get_user(conn, shop["id"]),
                                   product_id="tg-stars", quantity=50, fields={"telegram_username": "@x_user"})
    bot.handle(conn, press(f"od:{other['public_id']}"))
    bot.handle(conn, press(f"rp:{other['public_id']}"))
    assert "x_user" not in str(bot.api.calls)


def test_admin_page_and_broadcast(app, config, conn, supplier, monkeypatch):
    config.shop_bot_token = "t"
    bot = _bot(config, supplier)
    _start(bot, conn)
    db.set_setting(conn, "shop.bot_username", "DonatixShopBot")
    admin = TestClient(app)
    web_login(admin, "admin@example.com", "adminpass123")
    page = admin.get("/admin/shopbot").text
    assert "Продажи через бот" in page and "t.me/DonatixShopBot?start=g" in page
    assert "Через бот-магазин" in admin.get("/admin").text
    sent = FakeApi()
    shopbot.broadcast(config, "Скидка!", api=sent).join(5)
    assert [p["chat_id"] for m, p in sent.calls] == [TG]
    bot.handle(conn, press("unsub"))
    sent2 = FakeApi()
    shopbot.broadcast(config, "Ещё", api=sent2).join(5)
    assert sent2.calls == []

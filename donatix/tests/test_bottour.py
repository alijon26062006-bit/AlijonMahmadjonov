"""Турнир друзей в боте-магазине: +1 за нового друга («Я не бот» + канал), −1 за выход, +5 за покупку."""

from datetime import timedelta

from test_shopbot import TG, FakeApi, _bot, msg, press

from donatix import bottour, db, shopbot

FRIEND = 900100
CH = -1001234567890


class TourApi(FakeApi):
    def __init__(self):
        super().__init__()
        self.members: set[int] = set()

    def __call__(self, method, **p):
        if method == "getChatMember":
            self.calls.append((method, p))
            return {"status": "member" if p["user_id"] in self.members or p["user_id"] == 1 else "left"}
        if method == "getChat":
            self.calls.append((method, p))
            return {"id": CH, "title": "Donatix News", "username": "donatix_news"}
        return super().__call__(method, **p)


def _fmsg(text):
    m = msg(text)
    m["message"]["chat"]["id"] = m["message"]["from"]["id"] = FRIEND
    m["message"]["from"]["first_name"] = "Ахмад"
    return m


def _fpress(data):
    p = press(data)
    p["callback_query"]["message"]["chat"]["id"] = p["callback_query"]["from"]["id"] = FRIEND
    return p


def _setup(conn, config, supplier, channel=True):
    api = TourApi()
    bot = _bot(config, supplier, api)
    bot.bot_id = 1
    bottour.set_enabled(conn, True)
    if channel:
        bottour.set_channel(conn, {"chat_id": CH, "title": "Donatix News", "url": "https://t.me/donatix_news"})
    bot.handle(conn, msg("/start"))   # пригласивший уже в боте
    return bot, api


def _pass_captcha(bot, conn):
    want = bot.state[FRIEND]["want"]
    bot.handle(conn, _fpress(f"tc:{want}"))


def _points(conn):
    v = bottour.view(conn, 5, TG)
    return v["me"]["points"] if v["me"] else 0


def test_friend_counts_after_captcha_and_channel_and_leaving_takes_point(app, config, conn, supplier):
    bot, api = _setup(conn, config, supplier)
    assert "Турнир друзей" in str(api.last_buttons())          # кнопка на видном месте
    bot.handle(conn, _fmsg(f"/start t_{TG}"))
    assert "не бот" in api.last_text()
    wrong = (bot.state[FRIEND]["want"] + 1) % len(bottour.CAPTCHA)
    bot.handle(conn, _fpress(f"tc:{wrong}"))
    assert "Не тот значок" in api.last_text() and _points(conn) == 0
    _pass_captcha(bot, conn)
    assert "подпишитесь" in api.last_text() and _points(conn) == 0   # без канала — ещё не засчитан
    bot.handle(conn, _fpress("tsub"))                               # не подписан — балла нет
    assert _points(conn) == 0
    api.members.add(FRIEND)
    bot.handle(conn, _fpress("tsub"))
    assert _points(conn) == 1
    assert any("+1 балл" in p.get("text", "") and p["chat_id"] == TG for m, p in api.calls if m == "sendMessage")
    leave = {"update_id": 9, "chat_member": {"chat": {"id": CH}, "new_chat_member": {"status": "left",
                                                                                     "user": {"id": FRIEND}}}}
    bot.handle(conn, leave)
    assert _points(conn) == 0
    assert any("−1 балл" in p.get("text", "") for m, p in api.calls if m == "sendMessage")


def test_old_user_and_self_invite_not_counted(app, config, conn, supplier):
    bot, api = _setup(conn, config, supplier)
    bot.handle(conn, _fmsg("/start"))                  # уже был в боте
    bot.handle(conn, _fmsg(f"/start t_{TG}"))
    assert "не бот" not in api.last_text() and bottour.friend(conn, FRIEND) is None
    bot.handle(conn, msg(f"/start t_{TG}"))            # себя
    assert bottour.friend(conn, TG) is None


def test_purchase_gives_five_points_and_weekly_prizes(app, config, conn, supplier):
    bot, api = _setup(conn, config, supplier, channel=False)
    bot.handle(conn, _fmsg(f"/start t_{TG}"))
    _pass_captcha(bot, conn)
    assert _points(conn) == 1                          # без канала — +1 сразу после «Я не бот»
    fr = bottour.friend(conn, FRIEND)
    conn.execute("INSERT INTO orders (user_id, product_id, kind, product_name, quantity, unit_price, total_micro, "
                 "cost_micro, status, supplier_idem_key, created_at, updated_at) VALUES (?, 'x', 'topup', 'x', 1, "
                 "'1', 1, 1, 'completed', 'tour1', ?, ?)", (fr["friend_user"], db.now(), db.now()))
    assert _points(conn) == 6
    # итоги прошлой недели: переносим друга на неделю назад
    from donatix.contest import _iso, week_bounds
    start, _ = week_bounds(config.tz_offset)
    old = _iso(start - timedelta(days=3))
    conn.execute("UPDATE bot_tour SET joined_at = ?", (old,))
    conn.execute("UPDATE orders SET created_at = ? WHERE supplier_idem_key = 'tour1'", (old,))
    inviter = shopbot.shop_user(conn, TG)
    before = conn.execute("SELECT balance_micro FROM users WHERE id = ?", (inviter["user_id"],)).fetchone()[0]
    bot.tour_settle(conn)
    after = conn.execute("SELECT balance_micro FROM users WHERE id = ?", (inviter["user_id"],)).fetchone()[0]
    assert after > before
    sent = [p for m, p in api.calls if m == "sendMessage" and p["chat_id"] == TG]
    assert "1 место" in sent[-1]["text"] and sent[-1].get("message_effect_id") == shopbot.EFFECT_PARTY
    bot.tour_settle(conn)                              # второй раз не платит
    assert conn.execute("SELECT balance_micro FROM users WHERE id = ?", (inviter["user_id"],)).fetchone()[0] == after


def test_screen_rules_share_and_premium_badge(app, config, conn, supplier):
    config.shop_admin_ids = str(TG)
    bot, api = _setup(conn, config, supplier)
    bot.handle(conn, press("tour"))
    text = api.last_text()
    assert "после подтверждения «Я не бот»" in text and f"start=t_{TG}" in text
    share = next(b for b in api.last_buttons() if b["text"].startswith("📤"))
    assert share["url"].startswith("https://t.me/share/url?") and "t_" in share["url"]
    # админ присылает премиум-эмодзи — бот сам находит его ID
    bot.handle(conn, press("tab"))
    m = msg("🔥 вот")
    m["message"]["entities"] = [{"type": "custom_emoji", "offset": 0, "length": 2, "custom_emoji_id": "5368324170671202286"}]
    bot.handle(conn, m)
    assert bottour.badge(conn) == {"emoji_id": "5368324170671202286", "emoji": "🔥"}
    bot.handle(conn, msg("/start"))
    tour_btn = next(b for b in api.last_buttons() if "Турнир" in b["text"])
    assert tour_btn.get("icon_custom_emoji_id") == "5368324170671202286"


def test_premium_emoji_refused_falls_back_to_plain(app, config, conn, supplier):
    class NoPremium(TourApi):
        def __call__(self, method, **p):
            if method in ("sendMessage", "editMessageText") and ("tg-emoji" in p.get("text", "") or
                                                                 "icon_custom_emoji_id" in str(p.get("reply_markup"))):
                raise RuntimeError("telegram sendMessage: Bad Request: can't use custom emoji")
            return super().__call__(method, **p)
    api = NoPremium()
    bot = _bot(config, supplier, api)
    bottour.set_enabled(conn, True)
    bottour.set_badge(conn, {"emoji_id": "123", "emoji": "🔥"})
    bot.handle(conn, msg("/start"))
    assert "Турнир" in str(api.last_buttons())
    bot.handle(conn, press("tour"))
    assert "Турнир друзей" in api.last_text() and "tg-emoji" not in api.last_text()


def test_badge_from_sticker():
    b = bottour.badge_from_message({"sticker": {"file_id": "CAAC", "emoji": "🏆", "custom_emoji_id": "77"}})
    assert b == {"sticker": "CAAC", "emoji": "🏆", "emoji_id": "77"}
    assert bottour.badge_from_message({"text": "просто текст"}) is None

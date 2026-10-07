"""Автоплатёж «Душанбе Сити»: уникальные копейки, зачисление по уведомлению банка, при сомнении — админу."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import pytest
from conftest import balance, csrf_of, web_login
from fastapi.testclient import TestClient

from donatix import accounts, bankbot, bankparse, dcbank, payments

CARD = "5058 2700 1234 5678"


def notice(amount: str, kod: str, sender: str = "9990000***1111", card: str = "9999000011115678") -> str:
    return (f"Zachislenie\nSumma {amount} TJS\nKomis 0.00 TJS\nZachislenie {amount} TJS\nData 19:40 15.09.26\n"
            f"Otpravitel {sender}\nKod {kod}\nKarta {card}\nBalans 3 686.07 TJS")


@pytest.fixture
def dc(config, conn):
    config.tg_api_id, config.tg_api_hash, config.bank_bot = 1, "x" * 32, "dc_next_bot"
    payments.save_methods(conn, [{"code": "dc", "title": "Душанбе Сити", "currency": "TJS",
                                  "details": f"Карта {CARD}, Алиджон", "enabled": True, "auto": "dcbank"}])
    from donatix import db
    for kind in ("site", "bot"):   # видео-инструкцию проверяют отдельные тесты
        db.set_setting(conn, f"pay.dc_video_{kind}", "off")
    return config


def _client(app, conn, n=1):
    uid = accounts.create_user(conn, email=f"c{n}@example.com", login=f"client{n}", password="password123",
                               status="active")
    c = TestClient(app)
    token = web_login(c, f"c{n}@example.com", "password123")
    return uid, c, token


def _pay(c, token, tjs="100"):
    return c.post("/panel/balance", data={"csrf": token, "method": "dc", "amount_tjs": tjs}, follow_redirects=False)


def _handle(conn, config, text, mid):
    return dcbank.handle(conn, config, source="dc_next_bot", message_id=mid, text=text)


def test_parser_cases():
    n = bankparse.parse(notice("617.00", "1"))
    assert n.ok and n.amount == 61700 and n.card_tail == "5678"
    assert not bankparse.parse("Spisanie\nSumma 10.00 TJS").ok
    assert not bankparse.parse("Zachislenie\nZachislenie -617.00 TJS").ok
    assert not bankparse.parse("Zachislenie\nSumma 100.00 TJS\nKomis 2.00 TJS").ok
    assert bankparse.parse("Zachislenie\nSumma 100.43 TJS").amount == 10043
    assert not bankparse.parse("Zachislenie\nZachislenie 617.00 TJS abc").ok
    assert bankparse.money("3 686,07") == 368607
    assert not bankparse.parse("Zachislenie\nZachislenie 1.00 TJS\nZachislenie 2.00 TJS").ok
    assert not bankparse.parse("").ok


def test_method_needs_card(conn, config):
    with pytest.raises(payments.PaymentError):
        payments.save_methods(conn, [{"code": "dc", "title": "DC", "details": "без номера", "enabled": True,
                                      "auto": "dcbank"}])


def test_auto_credit_without_receipt(app, dc, conn):
    uid, c, token = _client(app, conn)
    assert "⚡ авто" in c.get("/panel/balance").text
    r = _pay(c, token)
    assert r.headers["location"].endswith("/pay")
    p = conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchone()
    assert p["auto_kind"] == "dcbank" and p["pay_amount"] == "100.01" and p["pay_address"] == "5058270012345678"
    assert "pay.dc.tj" in p["pay_url"] and "s=100.01" in p["pay_url"] and f"%23{p['id']}" in p["pay_url"]
    page = c.get(r.headers["location"]).text
    assert "Пардохт дар «Душанбе Сити»" in page and "100.01" in page and "5058 2700 1234 5678" in page
    assert "Алиджон" in page and "⚡ АВТО" in page
    assert "Открыть оплату" in c.get("/panel/balance").text

    uid2, c2, token2 = _client(app, conn, 2)
    _pay(c2, token2)
    p2 = conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchone()
    assert p2["pay_amount"] == "100.02"                     # второй клиент — свои копейки

    before = balance(conn, uid)
    assert _handle(conn, dc, notice("100.01", "777001"), 1)["status"] == "matched"
    assert conn.execute("SELECT status FROM payments WHERE id = ?", (p["id"],)).fetchone()[0] == "paid"
    assert balance(conn, uid) > before
    assert conn.execute("SELECT status FROM payments WHERE id = ?", (p2["id"],)).fetchone()[0] == "pending"
    # тот же перевод второй раз (другое сообщение, тот же код банка) — дубль
    now = balance(conn, uid)
    assert _handle(conn, dc, notice("100.01", "777001"), 2)["status"] == "duplicate"
    assert _handle(conn, dc, notice("100.01", "777001"), 1)["status"] == "duplicate"
    assert balance(conn, uid) == now
    assert c.get(f"/panel/data/payment/{p['id']}").json()["status"] == "paid"


def test_round_sum_and_ambiguous(app, dc, conn):
    uid, c, token = _client(app, conn)
    _pay(c, token, "50")
    p = conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchone()
    # клиент перевёл 50.00 вместо 50.01 — одна заявка рядом: зачисляем пришедшее
    assert _handle(conn, dc, notice("50.00", "1"), 10)["status"] == "matched"
    paid = conn.execute("SELECT amount_micro FROM payments WHERE id = ?", (p["id"],)).fetchone()[0]
    assert paid < p["amount_micro"]

    uid2, c2, t2 = _client(app, conn, 2)
    uid3, c3, t3 = _client(app, conn, 3)
    _pay(c2, t2, "30")
    _pay(c3, t3, "30")
    b2, b3 = balance(conn, uid2), balance(conn, uid3)
    assert _handle(conn, dc, notice("30.00", "2", sender="1110000***2222"), 11)["status"] == "ambiguous"
    assert (balance(conn, uid2), balance(conn, uid3)) == (b2, b3)
    assert _handle(conn, dc, notice("999.00", "3"), 12)["status"] == "unknown"


def test_old_request_other_card_and_race(app, dc, conn):
    uid, c, token = _client(app, conn)
    _pay(c, token, "70")
    p = conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchone()
    old = (datetime.now(timezone.utc) - timedelta(hours=7)).strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute("UPDATE payments SET created_at = ? WHERE id = ?", (old, p["id"]))
    assert _handle(conn, dc, notice("70.01", "4"), 20)["status"] == "unknown"   # заявка старше окна не участвует

    conn.execute("UPDATE payments SET created_at = ? WHERE id = ?", (datetime.now(timezone.utc)
                 .strftime("%Y-%m-%dT%H:%M:%S"), p["id"]))
    # карта из реквизитов в админке — *5678; уведомление по другой карте (бота-магазина) не наше
    assert _handle(conn, dc, notice("70.01", "51", card="9999000011112222"), 23)["status"] == "other"
    dc.bank_card = "1234"
    assert _handle(conn, dc, notice("70.01", "5"), 21)["status"] == "other"     # чужая карта — не трогаем
    dc.bank_card = ""

    # админ подтвердил заявку по чеку раньше робота — второй раз не начисляем
    conn.execute("UPDATE payments SET receipt_file = 'x.jpg' WHERE id = ?", (p["id"],))
    payments.confirm(conn, dc, p["id"], accounts.get_user(conn, uid)["id"])
    after = balance(conn, uid)
    assert _handle(conn, dc, notice("70.01", "6"), 22)["status"] == "unknown"
    assert balance(conn, uid) == after


def test_receipt_fallback(app, dc, conn):
    uid, c, token = _client(app, conn)
    r = _pay(c, token, "40")
    pid = int(r.headers["location"].split("/")[-2])
    page = c.get(f"/panel/balance/{pid}/pay").text
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    r = c.post(f"/panel/balance/{pid}/receipt", data={"csrf": csrf_of(page)},
               files={"receipt": ("r.png", png, "image/png")}, follow_redirects=False)
    assert r.status_code == 303
    row = conn.execute("SELECT receipt_file, status FROM payments WHERE id = ?", (pid,)).fetchone()
    assert row["status"] == "pending"
    # пришёл ли чек или его отбили проверки — деньги всё равно зачислятся по уведомлению банка
    assert _handle(conn, dc, notice("40.01", "9"), 30)["status"] == "matched"


def test_phone_in_details_does_not_filter_cards(app, config, conn):
    config.tg_api_id, config.tg_api_hash, config.bank_bot = 1, "x" * 32, "dc_next_bot"
    payments.save_methods(conn, [{"code": "dc", "title": "Сити (DC)", "details": "+992102208383",
                                  "enabled": True, "auto": "dcbank"}])
    assert dcbank.our_cards(conn, config) == set()
    from donatix import db
    db.set_setting(conn, "pay.dc_video_site", "off")
    uid, c, token = _client(app, conn)
    _pay(c, token, "20")
    assert _handle(conn, config, notice("20.01", "77"), 40)["status"] == "matched"


def test_without_userbot_it_is_a_normal_method(app, config, conn):
    payments.save_methods(conn, [{"code": "dc", "title": "Душанбе Сити", "details": f"Карта {CARD}",
                                  "enabled": True, "auto": "dcbank"}])
    assert not payments.is_auto(conn, config, "dc")
    uid, c, token = _client(app, conn)
    r = _pay(c, token)
    assert r.headers["location"] == "/panel/balance"          # без чека не создаётся — как обычный перевод


def test_listener_ignores_strangers(caplog):
    class Msg:
        id, message = 1, "Zachislenie 1.00 TJS — личное"

        def __init__(self, sid, name):
            self.sender_id, self.sender = sid, type("S", (), {"username": name})()

    q = asyncio.Queue()
    with caplog.at_level(logging.DEBUG):
        assert not bankbot.accept(Msg(5, "friend"), q, 1996047418, "1996047418")
    assert q.empty() and not caplog.records
    assert bankbot.accept(Msg(1996047418, "dc_next_bot"), q, 1996047418, "1996047418") and q.qsize() == 1
    assert bankbot.accept(Msg(7, "dc_next_bot"), q, 0, "dc_next_bot")
    ids, names = bankbot.wanted("dc_next_bot, 1996047418")
    assert ids == {1996047418} and names == {"dc_next_bot"}
    assert bankbot.accept(Msg(42, None), q, ids, names, sender=type("S", (), {"username": "DC_next_bot"})())
    assert not bankbot.accept(Msg(43, None), q, ids, names, sender=type("S", (), {"username": "x", "bot": True})())


def test_shop_bot_replaces_requisites_with_paid(app, dc, conn, supplier):
    """Бот-магазин: после автозачисления реквизиты заменяются ответом «оплата получена» — даже если
    соединение бота застряло в старой транзакции и не видело подтверждения."""
    from test_shopbot import _bot, _start, msg, press

    from donatix import db

    bot = _bot(dc, supplier)
    _start(bot, conn, "tj")
    bot.handle(conn, press("t"))
    bot.handle(conn, press(bot.api.button("Душанбе")))
    bot.handle(conn, msg("1"))
    shown = next(p for m, p in reversed(bot.api.calls) if "1.01" in (p.get("text") or ""))
    req_mid = bot.api.mid if "message_id" not in shown else shown["message_id"]
    p = conn.execute("SELECT * FROM payments").fetchone()

    conn.execute("BEGIN")                                   # бот держит старый снимок базы
    conn.execute("SELECT status FROM payments WHERE id = ?", (p["id"],)).fetchone()
    other = db.connect(dc.db_path)                          # банк подтверждает из своей службы
    assert _handle(other, dc, notice("1.01", "8801"), 50)["status"] == "matched"
    other.close()

    bot.watch(conn, force=True)
    method, last = bot.api.calls[-1]
    assert method == "editMessageText" and last["message_id"] == req_mid
    assert "Пардохт гирифта шуд" in last["text"] and "1.01" in last["text"]


MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


def _admin(app):
    c = TestClient(app)
    web_login(c, "admin@example.com", "adminpass123")
    return c


def test_video_required_on_site_before_paying(app, dc, conn):
    from donatix import dcvideo
    adm = _admin(app)
    page = adm.get("/admin/pay-settings").text
    assert "Видео-инструкция «Душанбе Сити" in page
    r = adm.post("/admin/dc-video", data={"csrf": csrf_of(page), "kind": "site"},
                 files={"file": ("how.mp4", MP4, "video/mp4")}, follow_redirects=False)
    assert r.status_code == 303 and dcvideo.get(conn, "site")["file"].endswith(".mp4")
    name = dcvideo.get(conn, "site")["file"]
    assert TestClient(app).get(f"/pay-videos/{name}").content == MP4      # видео открывается без входа

    uid, c, token = _client(app, conn)
    page = c.get("/panel/balance").text
    assert 'id="dcv"' in page and "худам ҷавобгар" in page and f"/pay-videos/{name}" in page
    r = _pay(c, token)                                                     # без просмотра оплату не создать
    assert r.headers["location"] == "/panel/balance?m=dc"
    assert conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 0
    r = c.post("/panel/dc-video/ack", data={"csrf": token, "method": "dc"}, follow_redirects=False)
    assert dcvideo.needed(conn, uid, "site")                               # без галочки не засчитано
    c.post("/panel/dc-video/ack", data={"csrf": token, "method": "dc", "agree": "1"})
    assert dcvideo.needed(conn, uid, "site") is None
    assert 'id="dcv"' not in c.get("/panel/balance").text                 # больше не мешает
    r = _pay(c, token)
    assert r.headers["location"].endswith("/pay")
    assert f"/pay-videos/{name}" in c.get(r.headers["location"]).text      # видео снова — по кнопке

    # новое видео — смотреть заново
    page = adm.get("/admin/pay-settings").text
    adm.post("/admin/dc-video", data={"csrf": csrf_of(page), "kind": "site",
                                      "url": "https://youtube.com/shorts/AbCdEf12345"})
    assert dcvideo.needed(conn, uid, "site")["youtube"] == "AbCdEf12345"
    assert not (dcvideo.videos_dir(dc) / name).exists()                    # старый файл удалён


def test_video_required_in_shop_bot(app, dc, conn, supplier):
    from test_shopbot import _bot, _start, msg, press

    from donatix import dcvideo
    dcvideo.set_video(conn, dc, "bot", data=MP4, content_type="video/mp4")
    bot = _bot(dc, supplier)
    sent = []
    bot.api.upload = lambda method, field, path, **p: (sent.append((method, p)) or {"video": {"file_id": "FID1"}})
    su = _start(bot, conn, "tj")
    bot.handle(conn, press("t"))
    bot.handle(conn, press(bot.api.button("Душанбе")))
    assert sent and sent[0][0] == "sendVideo" and "ҷавобгаред" in sent[0][1]["caption"]
    ok = sent[0][1]["reply_markup"]["inline_keyboard"][0][0]
    assert ok["callback_data"] == "dv:ok:dc"
    bot.handle(conn, msg("1"))                                             # сумму без видео не принимаем
    assert conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 0
    bot.handle(conn, press("dv:ok:dc"))
    assert dcvideo.needed(conn, su["user_id"], "bot") is None
    bot.handle(conn, msg("1"))
    assert conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 1
    assert any(b.get("callback_data") == "dv:show" for b in bot.api.last_buttons())
    bot.handle(conn, press("dv:show"))                                     # повтор — по file_id, без загрузки
    assert ("sendVideo", "FID1") in [(m, p.get("video")) for m, p in bot.api.calls]


def test_paid_push_reaches_bot_instantly_and_once(app, dc, conn, supplier, monkeypatch):
    """Подтвердили (автоплатёж, кассир, админ — из любого процесса) — покупатель сразу получает ответ
    на месте реквизитов. Цикл бота второй раз не пишет."""
    from test_shopbot import FakeApi, _bot, _start, msg, press

    from donatix import tgbot
    pushed = FakeApi()
    monkeypatch.setattr(tgbot, "TelegramApi", lambda token: pushed)
    dc.shop_bot_token = "t"
    bot = _bot(dc, supplier)
    _start(bot, conn, "tj")
    bot.handle(conn, press("t"))
    bot.handle(conn, press(bot.api.button("Душанбе")))
    bot.handle(conn, msg("1"))
    req_mid = bot.api.mid
    p = conn.execute("SELECT * FROM payments").fetchone()

    assert _handle(conn, dc, notice(p["pay_amount"], "9901"), 60)["status"] == "matched"
    edits = [c for m, c in pushed.calls if m == "editMessageText"]
    assert len(edits) == 1 and edits[0]["message_id"] == req_mid and "Пардохт гирифта шуд" in edits[0]["text"]

    before = len(bot.api.calls)
    bot.watch(conn, force=True)                                   # бот уже не дублирует
    assert len(bot.api.calls) == before

    # отклонение кассиром — тоже сразу
    bot.handle(conn, press("t"))
    bot.handle(conn, press(bot.api.button("Душанбе")))
    bot.handle(conn, msg("2"))
    p2 = conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchone()
    payments.reject(conn, dc, p2["id"], 1, "перевод не найден")
    assert "перевод не найден" in pushed.last_text()


def test_builtin_animated_guide_by_default(app, dc, conn, supplier):
    """Своё видео не загружено — клиент смотрит встроенную анимацию; бот шлёт встроенный MP4."""
    from test_shopbot import _bot, _start, press

    from donatix import db, dcvideo
    for kind in ("site", "bot"):
        db.set_setting(conn, f"pay.dc_video_{kind}", "")
    guide = TestClient(app).get("/dc-guide")
    assert guide.status_code == 200 and "dcguide:done" in guide.text and "5058 2700 1234 5678" in guide.text
    assert TestClient(app).get("/static/app/dc-guide.mp4").status_code == 200

    uid, c, token = _client(app, conn)
    page = c.get("/panel/balance").text
    assert 'id="dcv-guide"' in page and 'src="/dc-guide"' in page
    assert _pay(c, token).headers["location"] == "/panel/balance?m=dc"
    c.post("/panel/dc-video/ack", data={"csrf": token, "method": "dc", "agree": "1"})
    assert _pay(c, token).headers["location"].endswith("/pay")

    bot = _bot(dc, supplier)
    sent = []
    bot.api.upload = lambda method, field, path, **p: (sent.append(path) or {"video": {"file_id": "B1"}})
    _start(bot, conn, "tj")
    bot.handle(conn, press("t"))
    bot.handle(conn, press(bot.api.button("Душанбе")))
    assert sent == [dcvideo.BUILTIN_FILE]

    adm = _admin(app)
    page = adm.get("/admin/pay-settings").text
    assert "встроенная анимация" in page and "/static/app/dc-guide.mp4" in page
    adm.post("/admin/dc-video", data={"csrf": csrf_of(page), "kind": "site", "off": "1"})
    assert dcvideo.get(conn, "site") is None


def test_cancel_pending_with_receipt_and_in_bot(app, dc, conn, supplier):
    """Заявку в ожидании можно отменить — и на сайте (даже с чеком), и кнопкой в боте."""
    from test_shopbot import _bot, _start, msg, press

    uid, c, token = _client(app, conn)
    r = _pay(c, token, "40")
    pid = int(r.headers["location"].split("/")[-2])
    conn.execute("UPDATE payments SET receipt_file = 'r.png' WHERE id = ?", (pid,))
    c.post(f"/panel/balance/{pid}/cancel", data={"csrf": token})
    assert conn.execute("SELECT status FROM payments WHERE id = ?", (pid,)).fetchone()[0] == "cancelled"
    assert _handle(conn, dc, notice("40.01", "7001"), 70)["status"] == "unknown"   # отменённую не зачисляем

    bot = _bot(dc, supplier)
    _start(bot, conn, "tj")
    bot.handle(conn, press("t"))
    bot.handle(conn, press(bot.api.button("Душанбе")))
    bot.handle(conn, msg("3"))
    p = conn.execute("SELECT * FROM payments ORDER BY id DESC").fetchone()
    assert any(b.get("callback_data") == f"pc:{p['id']}" for b in bot.api.last_buttons())
    bot.handle(conn, press(f"pc:{p['id']}"))
    assert "бекор шуд" in bot.api.last_text()
    assert conn.execute("SELECT status FROM payments WHERE id = ?", (p["id"],)).fetchone()[0] == "cancelled"
    assert conn.execute("SELECT COUNT(*) FROM shop_watch WHERE obj_id = ?", (p["id"],)).fetchone()[0] == 0
    bot.handle(conn, press(f"pc:{p['id']}"))                                        # второй раз — уже нельзя
    assert "мумкин нест" in bot.api.last_text()

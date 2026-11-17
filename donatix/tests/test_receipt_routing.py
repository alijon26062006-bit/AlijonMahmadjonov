"""Чек — хозяину той карты, на которую реально пришли деньги.

Проверяем как живой клиент: заявка на сайте / в мини-приложении → чек → что прочитал ИИ → кому пришёл чек.
ИИ здесь подменён ответами в том виде, в каком он пишет получателя из настоящих чеков Алифа, Душанбе Сити и др.
"""

import pytest

from conftest import RECEIPT, csrf_of, make_client, web_login

from donatix import cashiers, db, paycards, payments, tgbot

FARRUKH, SHAHZOD, MUROD = 777101, 777102, 777103
ADMIN_CHAT = "777"


@pytest.fixture
def cards(conn, app):
    config = app.state.config
    config.pay_methods = {"alif": "Алиф: +992 90 000 00 00 (Али)", "dc": "Душанбе Сити: 9762 0000 0000 0000"}
    config.alert_telegram_chat_id = ADMIN_CHAT
    config.alert_telegram_token = config.alert_telegram_token or "1:x"
    db.set_setting(conn, "cards.rest", "0")
    for tg, name in ((FARRUKH, "Фаррух"), (SHAHZOD, "Шахзод"), (MUROD, "Мурод")):
        cashiers.add(conn, tg, name)
    return {
        "A1": paycards.add(conn, "alif", "Карта 4444 5555 6666 1111\nПолучатель: Фаррух Р.", FARRUKH),
        "A2": paycards.add(conn, "alif", "Карта 5058 2700 1234 2222\nПолучатель: Шахзод М.", SHAHZOD),
        "A3": paycards.add(conn, "alif", "Телефон +992 93 555 44 33\nПолучатель: Бахтиёр К.", 0),
        "D1": paycards.add(conn, "dc", "Корти Милли 9762 0000 1111 3333\nСомон Н.", FARRUKH),
        "D2": paycards.add(conn, "dc", "Телефон +992 900 11 22 44\nМурод", MUROD),
    }


# Как ИИ переписывает получателя из реальных чеков → какая наша карта
CASES = [
    ("alif", "4444 55** **** 1111", "A1"),
    ("alif", "**** 1111", "A1"),
    ("alif", "•••• 2222 Шахзод М.", "A2"),
    ("alif", "5058 27** **** 2222", "A2"),
    ("alif", "Карта получателя: 5058270012342222", "A2"),
    ("alif", "5058 2700 1234 2222", "A2"),
    ("alif", "+992 93 *** 44 33", "A3"),
    ("alif", "93 555 44 33", "A3"),
    ("alif", "+992935554433 Бахтиёр К.", "A3"),
    ("alif", "992 93 555 4433", "A3"),
    ("alif", "Бахтиёр К.", "A3"),
    ("alif", "FARRUKH R. 4444 55** **** 1111", "A1"),
    ("alif", "Кому: Шахзод", "A2"),
    ("alif", "Фаррух Р. +992 93 *** 44 33", "A3"),           # имя одной карты, номер другой — верим номеру
    ("alif", "4444 55** **** 2222", None),                   # начало от одной карты, конец от другой — не гадаем
    ("alif", "**** 9999", None),                             # не наша карта
    ("alif", "", None),
    ("alif", "**** 3333", None),                             # карта другого банка — в этой заявке не наша
    ("dc", "9762 00** **** 3333", "D1"),
    ("dc", "Сомон Н. ****3333", "D1"),
    ("dc", "+992 900 ** 22 44", "D2"),
    ("dc", "900112244", "D2"),
    ("dc", "+992 (900) 11-22-44 Мурод", "D2"),
]


@pytest.mark.parametrize("method,recipient,want", CASES)
def test_recipient_text_finds_right_card(conn, cards, method, recipient, want):
    got = paycards.match(conn, recipient, method)
    assert (got["id"] if got else None) == (cards[want] if want else None), recipient


def _site_topup(app, conn, monkeypatch, cards, method, seen, login):
    """Клиент на сайте: вход → пополнение с чеком. Возвращает (заявка, кому ушёл чек)."""
    from fastapi.testclient import TestClient
    sent = []
    monkeypatch.setattr("donatix.worker.notify_admin_file",
                        lambda cfg, caption, buttons, path, photo: sent.append("admin") or 100)
    monkeypatch.setattr("donatix.cashiers.send_file",
                        lambda cfg, chat, caption, buttons, path, photo: sent.append(int(chat)) or 200)
    monkeypatch.setattr("donatix.payments.read_receipt", lambda config, data, details="": dict(seen))
    make_client(conn, login=login)
    c = TestClient(app)
    web_login(c, f"{login}@example.com", "password123")
    token = csrf_of(c.get("/panel/balance").text)
    r = c.post("/panel/balance", data={"csrf": token, "method": method, "amount_tjs": "100"}, files=RECEIPT,
               follow_redirects=False)
    assert r.status_code == 303
    pid = conn.execute("SELECT MAX(id) FROM payments").fetchone()[0]
    return pid, sent


OWNER = {"A1": FARRUKH, "A2": SHAHZOD, "A3": None, "D1": FARRUKH, "D2": MUROD}


@pytest.mark.parametrize("method,seen,want", [
    ("alif", {"recipient": "5058 27** **** 2222 Шахзод М."}, "A2"),
    ("alif", {"recipient": "+992 93 *** 44 33"}, "A3"),                          # карта владельца — только админу
    ("alif", {"recipient": "", "our_card": "A2"}, "A2"),                          # номер не прочитан, ИИ назвал карту
    ("alif", {"recipient": "**** 1111", "our_card": "A2"}, "A1"),                 # ИИ ошибся — цифры важнее
    ("dc", {"recipient": "9762 00** **** 3333"}, "D1"),
    ("dc", {"recipient": "+992 900 ** 22 44"}, "D2"),
])
def test_client_on_site_receipt_reaches_owner_of_that_card(app, conn, monkeypatch, cards, method, seen, want):
    seen = {**seen, "our_card": cards[seen["our_card"]]} if "our_card" in seen else seen
    pid, sent = _site_topup(app, conn, monkeypatch, cards, method,
                            {"is_receipt": True, "amount": 0, "status": "success", **seen}, f"rt{abs(hash(str(seen))) % 99999}")
    assert conn.execute("SELECT card_id FROM payments WHERE id = ?", (pid,)).fetchone()[0] == cards[want]
    owner = OWNER[want]
    assert sent == (["admin", owner] if owner else ["admin"])       # админ всегда; из кассиров — только хозяин карты


def test_unknown_recipient_keeps_shown_card(app, conn, monkeypatch, cards):
    pid, sent = _site_topup(app, conn, monkeypatch, cards, "alif", {"recipient": "**** 9999"}, "rtunknown")
    shown = conn.execute("SELECT card_id FROM payments WHERE id = ?", (pid,)).fetchone()[0]
    assert shown in (cards["A1"], cards["A2"], cards["A3"])
    owner = {cards["A1"]: FARRUKH, cards["A2"]: SHAHZOD}.get(shown)
    assert sent == (["admin", owner] if owner else ["admin"])


def test_full_story_owner_decides_others_cannot_channel_logs(app, conn, monkeypatch, cards):
    """Шахзоду пришли деньги → чек у Шахзода и админа; Фаррух нажать не может; Шахзод принял → канал-журнал."""
    pid, _ = _site_topup(app, conn, monkeypatch, cards, "alif", {"recipient": "**** 2222"}, "rtstory")
    cashiers.set_channel(conn, "@dx_log")
    posts = []
    monkeypatch.setattr("donatix.cashiers.send_file",
                        lambda cfg, chat, caption, buttons, path, photo: posts.append((chat, caption)) or 300)

    class Now:
        def __init__(self, target, args=(), kwargs=None, **_):
            self.go = lambda: target(*args, **(kwargs or {}))

        def start(self):
            self.go()
    monkeypatch.setattr("donatix.cashiers.threading.Thread", Now)
    calls = []
    bot = tgbot.AdminBot(app.state.config, api=lambda m, **p: calls.append((m, p)) or {})

    def press(chat, data):
        bot.handle(conn, {"update_id": 1, "callback_query": {"id": "c", "data": data, "from": {"id": chat},
                   "message": {"message_id": 200, "chat": {"id": chat, "type": "private"}, "caption": "чек",
                               "photo": [{}]}}})
    press(FARRUKH, f"pay:ok:{pid}")
    assert conn.execute("SELECT status FROM payments WHERE id = ?", (pid,)).fetchone()[0] == "pending"
    press(SHAHZOD, f"pay:ok:{pid}")
    assert conn.execute("SELECT status FROM payments WHERE id = ?", (pid,)).fetchone()[0] == "paid"
    log = [c for chat, c in posts if chat == "@dx_log"]
    assert len(log) == 1 and "Шахзод" in log[0] and "****2222" in log[0] and "Зачислено" in log[0]


def test_mini_app_topup_routes_the_same(app, conn, monkeypatch, cards):
    """Мини-приложение: тот же путь — чек хозяину карты, на которую пришли деньги."""
    import hashlib
    import hmac
    import json
    import time
    from dataclasses import replace
    from urllib.parse import urlencode

    from fastapi.testclient import TestClient
    token = "123:app-token"
    app.state.config = replace(app.state.config, gift_bot_token=token)
    data = {"auth_date": str(int(time.time())), "user": json.dumps({"id": 6601, "first_name": "Клиент"})}
    check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    sent = []
    monkeypatch.setattr("donatix.worker.notify_admin_file", lambda *a, **k: sent.append("admin") or 100)
    monkeypatch.setattr("donatix.cashiers.send_file",
                        lambda cfg, chat, caption, buttons, path, photo: sent.append(int(chat)) or 200)
    monkeypatch.setattr("donatix.payments.read_receipt",
                        lambda config, data, details="": {"recipient": "Мурод +992 900 ** 22 44"})
    c = TestClient(app)
    r = c.post("/tg/api/topup", data={"method": "dc", "amount_tjs": "100"}, files=RECEIPT,
               headers={"X-Tg-Init": urlencode(data)}).json()
    assert r["ok"], r
    pid = conn.execute("SELECT MAX(id) FROM payments").fetchone()[0]
    assert conn.execute("SELECT card_id FROM payments WHERE id = ?", (pid,)).fetchone()[0] == cards["D2"]
    assert sent == ["admin", MUROD]


def test_ai_sees_every_card_labelled(conn, cards):
    text = paycards.all_details(conn, "alif", "Алиф: +992 90 000 00 00")
    for k in ("A1", "A2", "A3"):
        assert f"[карта #{cards[k]}]" in text
    assert f"[карта #{cards['D1']}] (банк dc)" in text                # наши карты другого банка — с пометкой банка
    assert text.index(f"#{cards['A3']}]") < text.index(f"#{cards['D1']}]")   # сначала карты выбранного банка


def test_warning_not_ours_uses_same_matching(conn, cards):
    from donatix import receipt_ai
    ours = paycards.all_details(conn, "alif")
    assert receipt_ai.recipient_matches({"recipient": "5058 27** **** 2222"}, ours) is True
    assert receipt_ai.recipient_matches({"recipient": "+992 93 *** 44 33"}, ours) is True
    assert receipt_ai.recipient_matches({"recipient": "**** 9999"}, ours) is False
    assert receipt_ai.recipient_matches({"recipient": "Бахтиёр"}, ours) is None


def _fake_ai(monkeypatch, answer):
    from donatix import receipt_ai
    monkeypatch.setattr(receipt_ai, "enabled", lambda config: True)
    got = {}

    def read(config, data, ext, transport=None, our_details=""):
        got["details"] = our_details
        return answer
    monkeypatch.setattr(receipt_ai, "read", read)
    return got


def test_live_check_explains_which_cashier_gets_receipt(conn, app, cards, monkeypatch):
    from conftest import RECEIPT_PNG
    got = _fake_ai(monkeypatch, {"bank": "Алиф", "amount": 100, "currency": "TJS",
                                 "recipient": "5058 27** **** 2222 Шахзод М.", "our_card": 0})
    text = paycards.explain(conn, app.state.config, RECEIPT_PNG)
    assert "****2222" in text and "Шахзод" in text and "ничего не записано" in text
    assert f"[карта #{cards['A2']}]" in got["details"] and f"[карта #{cards['D1']}]" in got["details"]   # ИИ видит все карты
    assert conn.execute("SELECT COUNT(*) FROM payments").fetchone()[0] == 0
    _fake_ai(monkeypatch, {"recipient": "**** 9999", "our_card": 0})
    assert "Ни одна наша карта не подошла" in paycards.explain(conn, app.state.config, RECEIPT_PNG)


def test_admin_bot_chek_command(conn, app, cards, monkeypatch):
    from conftest import RECEIPT_PNG
    _fake_ai(monkeypatch, {"recipient": "+992 900 ** 22 44", "our_card": 0})
    calls = []
    bot = tgbot.AdminBot(app.state.config, api=lambda m, **p: calls.append((m, p)) or {})
    bot.api.download = lambda file_id, **k: RECEIPT_PNG
    msg = {"message_id": 5, "chat": {"id": int(ADMIN_CHAT), "type": "private"}, "from": {"id": int(ADMIN_CHAT)}}
    bot.handle(conn, {"update_id": 1, "message": {**msg, "text": "/chek"}})
    bot.handle(conn, {"update_id": 2, "message": {**msg, "photo": [{"file_id": "f"}]}})
    reply = [p["text"] for m, p in calls if m == "sendMessage"][-1]
    assert "****2244" in reply and "Мурод" in reply


# ── ИИ включён: кассиру — только если карта ПОДТВЕРЖДЕНА чеком ──

@pytest.fixture
def ai_on(monkeypatch):
    from donatix import receipt_ai
    monkeypatch.setattr(receipt_ai, "enabled", lambda config: True)


def test_ai_on_unrecognised_receipt_goes_to_admin_only(app, conn, monkeypatch, cards, ai_on):
    """Клиент перевёл на старую сохранённую чужую карту / ИИ не нашёл номер — кассиру показанной карты НЕ шлём."""
    monkeypatch.setattr("donatix.receipt_ai.find_card", lambda *a, **k: None)
    pid, sent = _site_topup(app, conn, monkeypatch, cards, "alif", {"recipient": "**** 9999", "amount": 0}, "aion1")
    assert sent == ["admin"]
    p = conn.execute("SELECT * FROM payments WHERE id = ?", (pid,)).fetchone()
    assert "Кассиру чек не отправлен" in p["receipt_ai"]
    for tg in (FARRUKH, SHAHZOD):                                      # и решить её кассир не может
        assert not cashiers.may_decide(conn, app.state.config, cashiers.get(conn, tg), p)


@pytest.mark.parametrize("recipient,want", [
    ("Гиранда: 5058 27** **** 2222", "A2"),
    ("Қабулкунанда Бахтиёр К. +992 93 *** 44 33", "A3"),
    ("**** 3333", "D1"),                                               # заявка «Алиф», а перевёл на нашу карту DC
])
def test_ai_on_recognised_receipt_goes_to_card_owner(app, conn, monkeypatch, cards, ai_on, recipient, want):
    monkeypatch.setattr("donatix.receipt_ai.find_card", lambda *a, **k: None)
    pid, sent = _site_topup(app, conn, monkeypatch, cards, "alif", {"recipient": recipient, "amount": 0},
                            f"aion{cards[want]}")
    p = conn.execute("SELECT * FROM payments WHERE id = ?", (pid,)).fetchone()
    assert p["card_id"] == cards[want]
    owner = OWNER[want]
    assert sent == (["admin", owner] if owner else ["admin"])
    if owner:
        assert cashiers.may_decide(conn, app.state.config, cashiers.get(conn, owner), p)


def test_second_ai_pass_when_first_read_missed_the_number(app, conn, monkeypatch, cards, ai_on):
    """Первое чтение не нашло номер получателя → второй запрос только про получателя → чек хозяину карты."""
    from donatix import receipt_ai
    calls = []
    monkeypatch.setattr(receipt_ai, "read", lambda config, data, ext, transport=None, our_details="":
                        calls.append("read") or {"is_receipt": True, "recipient": "Шахзод", "our_card": 0, "amount": 0})

    def find(config, data, ext, our_details, transport=None):
        calls.append("find")
        assert f"[карта #{cards['A2']}]" in our_details
        return {"recipient": "Ба корт: 5058 27** **** 2222", "our_card": cards["A2"], "why": "последние 4 цифры"}
    monkeypatch.setattr(receipt_ai, "find_card", find)
    from fastapi.testclient import TestClient
    sent = []
    monkeypatch.setattr("donatix.worker.notify_admin_file", lambda *a, **k: sent.append("admin") or 100)
    monkeypatch.setattr("donatix.cashiers.send_file",
                        lambda cfg, chat, caption, buttons, path, photo: sent.append(int(chat)) or 200)
    make_client(conn, login="twopass")
    c = TestClient(app)
    web_login(c, "twopass@example.com", "password123")
    token = csrf_of(c.get("/panel/balance").text)
    c.post("/panel/balance", data={"csrf": token, "method": "alif", "amount_tjs": "100"}, files=RECEIPT,
           follow_redirects=False)
    pid = conn.execute("SELECT MAX(id) FROM payments").fetchone()[0]
    assert calls == ["read", "find"]
    assert conn.execute("SELECT card_id FROM payments WHERE id = ?", (pid,)).fetchone()[0] == cards["A2"]
    assert sent == ["admin", SHAHZOD]


def test_no_second_pass_when_number_already_clear(conn, app, cards, monkeypatch, ai_on):
    from donatix import receipt_ai
    monkeypatch.setattr(receipt_ai, "read", lambda *a, **k: {"recipient": "**** 1111", "our_card": 0})
    monkeypatch.setattr(receipt_ai, "find_card", lambda *a, **k: pytest.fail("лишний запрос к ИИ"))
    from conftest import RECEIPT_PNG
    seen = payments.read_receipt(app.state.config, RECEIPT_PNG, paycards.all_details(conn, "alif"))
    assert seen["recipient"] == "**** 1111"


def test_prompt_knows_tajik_recipient_words():
    from donatix import receipt_ai
    for word in ("Гиранда", "Қабулкунанда", "Ба корт", "Рақами телефон", "Фиристанда", "Аз корт"):
        assert word in receipt_ai.PROMPT and word in receipt_ai.FIND_PROMPT


# Настоящий чек «Душанбе Сити»: «Қабулкунанда: 992102208383», «Таъминкунанда: DC (по номеру телефона)»
@pytest.mark.parametrize("saved", ["Телефон +992 10 220 83 83", "DC: 102208383", "992102208383 Али",
                                   "Номер: 10 220 8383", "+992-102-20-83-83"])
def test_real_dc_receipt_phone_992_found_whatever_way_we_saved_it(conn, app, saved):
    db.set_setting(conn, "cards.rest", "0")
    cashiers.add(conn, 777201, "Кассир DC")
    ours = paycards.add(conn, "dc", saved, 777201)
    paycards.add(conn, "dc", "Телефон +992 93 555 44 33", 0)            # другая наша карта — не перепутать
    seen = {"bank": "DC (по номеру телефона)", "amount": 9, "recipient": "992102208383"}
    card, why = paycards.which_card(conn, "dc", seen)
    assert card is not None and card["id"] == ours, why
    assert paycards.which_card(conn, "dc", {"recipient": "Қабулкунанда: 992102208383"})[0]["id"] == ours


def test_prompt_has_real_dc_receipt_example():
    from donatix import receipt_ai
    assert "Қабулкунанда: 992102208383" in receipt_ai.PROMPT and "Таъминкунанда" in receipt_ai.FIND_PROMPT

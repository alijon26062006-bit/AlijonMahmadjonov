import json
import re

from conftest import make_client

from donatix import supportbot


class FakeTG:
    def __init__(self):
        self.sent = []

    def __call__(self, method, **kw):
        if method == "sendMessage":
            self.sent.append((str(kw["chat_id"]), kw["text"]))
        if method == "getMe":
            return {"username": "donatix_help_bot"}
        return {}


def _bot(config, chat=None):
    config.alert_telegram_chat_id = "999"
    return supportbot.SupportBot(config, api=FakeTG(), chat=chat or (lambda m: {"content": "ok"}))


def _order(conn, uid, public_id, status, error=None):
    conn.execute("INSERT INTO orders (public_id, user_id, product_id, kind, product_name, quantity, fields_json, "
                 "unit_price, total_micro, cost_micro, status, supplier_idem_key, error, created_at, updated_at) "
                 "VALUES (?, ?, 'ff-1', 'topup', 'Free Fire — 100 Diamonds', 1, '{\"player_id\": \"123\"}', '1', "
                 "10000, 9000, ?, ?, ?, '2026-09-27T10:00:00.000Z', '2026-09-27T10:00:00.000Z')",
                 (public_id, uid, status, "k-" + public_id, error))


def test_login_by_email_code_and_only_own_data(config, conn):
    uid, _ = make_client(conn)
    other, _ = make_client(conn, login="shop2")
    _order(conn, uid, "dx-aaa111", "failed", "Поставщик FazerCards: insufficient balance $0.37")
    _order(conn, other, "dx-bbb222", "completed")
    bot = _bot(config)
    t = supportbot.Tools(bot, conn, 555, "@client")

    assert t.run("get_order", {"order_id": "dx-aaa111"}) == {"error": "not_verified_ask_email"}
    same = t.run("send_login_code", {"email": "nobody@example.com"})
    assert same == t.run("send_login_code", {"email": "shop1@example.com"})   # не выдаём, есть ли такой email
    note = conn.execute("SELECT text FROM notifications WHERE user_id = ? ORDER BY id DESC", (uid,)).fetchone()[0]
    code = re.search(r"(\d{6})", note).group(1)
    assert t.run("verify_login_code", {"code": "000000" if code != "000000" else "111111"})["error"] == "wrong_code"
    assert t.run("verify_login_code", {"code": code}) == {"ok": True, "login": "shop1"}

    mine = t.run("get_order", {"order_id": "DX-AAA111"})
    assert mine["status"] == "не выполнен" and mine["money_returned_to_balance"] is True
    assert mine["failure_reason"] == "temporarily_unavailable" and "💎 100 алмазов" in mine["product"]
    assert "FazerCards" not in json.dumps(mine, ensure_ascii=False)          # поставщик не виден
    assert "cost" not in json.dumps(mine) and "9000" not in json.dumps(mine)  # закупка не видна
    assert t.run("get_order", {"order_id": "dx-bbb222"}) == {"error": "order_not_found_in_this_account"}
    assert t.run("get_my_account", {})["balance_usd"] == "100.0000"


def test_ai_loop_uses_tools_and_remembers(config, conn):
    uid, _ = make_client(conn)
    conn.execute("INSERT INTO support_links (tg_id, user_id, linked_at) VALUES (555, ?, 'x')", (uid,))
    calls = []

    def chat(messages):
        calls.append(messages)
        if len(calls) == 1:
            return {"content": None, "tool_calls": [{"id": "c1", "type": "function",
                    "function": {"name": "get_my_account", "arguments": "{}"}}]}
        tool_msg = messages[-1]
        assert tool_msg["role"] == "tool" and "100.0000" in tool_msg["content"]
        return {"content": "Баланси шумо: $100.0000"}

    bot = _bot(config, chat)
    bot.handle(conn, {"message": {"chat": {"id": 555, "type": "private"}, "from": {"id": 555, "username": "c"},
                                  "text": "Баланси ман чанд аст?"}})
    assert bot.api.sent[-1] == ("555", "Баланси шумо: $100.0000")
    system = calls[0][0]["content"]
    assert "FazerCards" not in system and "таджикски" in system
    hist = conn.execute("SELECT role FROM support_history WHERE tg_id = 555 ORDER BY id").fetchall()
    assert [r[0] for r in hist] == ["user", "assistant"]


def test_escalation_and_admin_reply(config, conn):
    bot = _bot(config)
    t = supportbot.Tools(bot, conn, 555, "@client")
    res = t.run("escalate_to_admin", {"summary": "Заказ dx-1 в обработке 2 часа"})
    assert res["ok"] and bot.api.sent[-1][0] == "999" and "tg555" in bot.api.sent[-1][1]
    alert = bot.api.sent[-1][1]
    bot.handle(conn, {"message": {"chat": {"id": 999, "type": "private"}, "from": {"id": 999},
                                  "text": "Проверили, выполнено", "reply_to_message": {"text": alert}}})
    assert ("555", "👤 Ответ администратора / Ҷавоби админ:\nПроверили, выполнено") in bot.api.sent
    assert conn.execute("SELECT status FROM support_tickets").fetchone()[0] == "answered"


def test_start_and_rate_limit(config, conn):
    bot = _bot(config)
    msg = {"message": {"chat": {"id": 7, "type": "private"}, "from": {"id": 7}, "text": "/start"}}
    bot.handle(conn, msg)
    assert "Салом" in bot.api.sent[-1][1]
    for _ in range(25):
        bot.handle(conn, {"message": {"chat": {"id": 7, "type": "private"}, "from": {"id": 7}, "text": "?"}})
    assert "подождите" in bot.api.sent[-1][1]

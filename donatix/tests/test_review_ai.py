"""ИИ на отзывах: собирает факты по заказу, отвечает по ним, спам скрывает, остальное оставляет админу."""
import json

import httpx
from conftest import make_client
from test_reviews import _order, _pub

from donatix import accounts, review_ai, reviews


def _ai(answer, seen):
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(answer, ensure_ascii=False)}}]})
    return httpx.MockTransport(handler)


def _review(conn, config, text, rating=1):
    uid = make_client(conn, balance="5")[0]
    oid = _order(conn, uid, "completed", 100000)
    conn.execute("UPDATE orders SET fields_json = ?, completed_at = '2026-10-09T10:00:00Z' WHERE id = ?",
                 ('{"player_id": "15858081660"}', oid))
    rid = reviews.add(conn, config, accounts.get_user(conn, uid), _pub(conn, oid), rating, text)
    return uid, oid, rid


def test_facts_include_order_id_and_mentioned_orders(app, config, conn):
    uid, oid, rid = _review(conn, config, "Алмазы не пришли")
    other = _order(conn, uid, "failed", 50000)
    conn.execute("UPDATE reviews SET text = ? WHERE id = ?", (f"и заказ #{other} тоже не пришёл", rid))
    f = review_ai.facts(conn, conn.execute("SELECT * FROM reviews WHERE id = ?", (rid,)).fetchone())
    assert [o["номер"] for o in f["заказы"]] == [_pub(conn, oid), _pub(conn, other)]
    assert f["заказы"][0]["данные_для_пополнения"] == {"player_id": "15858081660"}
    assert "возвращены" in f["заказы"][1]["статус"]


def test_reply_by_facts(app, config, conn):
    config.openai_api_key = "sk-test"
    uid, oid, rid = _review(conn, config, "Алмазы не пришли!!!")
    seen = []
    ans = {"action": "reply", "reason": "жалоба на заказ",
           "reply": f"Салом! Фармоиши {_pub(conn, oid)} 09.10 ба ID 15858081660 расидааст."}
    assert review_ai.process(conn, config, rid, _ai(ans, seen)) == "reply"
    assert "15858081660" in json.dumps(seen[0], ensure_ascii=False)               # ChatGPT получил факты
    r = conn.execute("SELECT * FROM reviews WHERE id = ?", (rid,)).fetchone()
    assert r["reply_text"].startswith("Салом") and r["reply_by"] is None and r["ai_state"] == "reply"
    assert conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND text LIKE 'Магазин ответил%'",
                        (uid,)).fetchone()[0] == 1


def test_spam_hidden_and_other_left_for_admin(app, config, conn):
    config.openai_api_key = "sk-test"
    _, _, spam = _review(conn, config, "заходите на mysite.com дешевле")
    assert review_ai.process(conn, config, spam, _ai({"action": "hide", "reason": "реклама", "reply": ""}, [])) == "hide"
    assert conn.execute("SELECT hidden FROM reviews WHERE id = ?", (spam,)).fetchone()[0] == 1
    conn.execute("UPDATE users SET login = 'second' WHERE login = 'shop1'")
    conn.execute("UPDATE users SET email = 'x@example.com' WHERE email = 'shop1@example.com'")
    _, _, idea = _review(conn, config, "Сделайте скидки побольше", rating=4)
    assert review_ai.process(conn, config, idea, _ai({"action": "skip", "reason": "пожелание", "reply": ""}, [])) == "skip"
    r = conn.execute("SELECT * FROM reviews WHERE id = ?", (idea,)).fetchone()
    assert r["reply_text"] is None and r["hidden"] == 0                            # ответит админ


def test_admin_answered_first_ai_does_nothing(app, config, conn):
    config.openai_api_key = "sk-test"
    _, _, rid = _review(conn, config, "Не пришло")
    admin = conn.execute("SELECT * FROM users WHERE role = 'admin'").fetchone()
    reviews.reply(conn, config, admin, rid, "Проверили — всё пришло")
    seen = []
    assert review_ai.process(conn, config, rid, _ai({"action": "reply", "reply": "другое"}, seen)) == "skip"
    assert seen == [] and conn.execute("SELECT reply_text FROM reviews WHERE id = ?", (rid,)).fetchone()[0].startswith("Проверили")


def test_openai_down_leaves_review(app, config, conn):
    config.openai_api_key = "sk-test"
    _, _, rid = _review(conn, config, "Не пришло")
    down = httpx.MockTransport(lambda r: httpx.Response(500, text="err"))
    assert review_ai.process(conn, config, rid, down) == "error"
    assert conn.execute("SELECT reply_text, hidden FROM reviews WHERE id = ?", (rid,)).fetchone()[0] is None

"""Условия для ботов партнёров: рассылка, ответ владельца, выключение за отказ и молчание."""

from datetime import datetime, timedelta, timezone

from conftest import web_login
from fastapi.testclient import TestClient

from donatix import botterms, bots, db
from donatix.security import seal


def _bot(conn, config, uid=1, username="partner_bot"):
    now = db.now()
    cur = conn.execute("INSERT INTO bots (user_id, token_enc, username, admin_ids, enabled, created_at, updated_at) "
                       "VALUES (?, ?, ?, '111,222', 1, ?, ?)",
                       (uid, seal(config.secret_key, "123456:" + "A" * 35), username, now, now))
    return cur.lastrowid


def _send(conn, config):
    sent = []
    res = botterms.send_all(conn, config, sender=lambda token, chats, body, url: sent.append((token, chats, body, url)) or 1)
    return res, sent


def test_send_to_every_bot_in_tajik_with_buttons(app, config, conn):
    _bot(conn, config)
    _bot(conn, config, username="second_bot")
    (ok, failed), sent = _send(conn, config)
    assert (ok, failed) == (2, 0)
    token, chats, body, url = sent[0]
    assert chats == ["111", "222"] and "@partner_bot" in body and "Реклама" in body and "ҳамаи ботҳои" in body
    assert "/bot-terms/" in url and "{deadline}" not in body


def test_agree_decline_delete_from_page(app, config, conn):
    bid = _bot(conn, config)
    _, sent = _send(conn, config)
    url = sent[0][3].replace(config.base_url, "")
    c = TestClient(app)
    page = c.get(url + "?a=decline")
    assert page.status_code == 200 and "Қабул намекунам" in page.text and "Реклама" in page.text
    # просто открыть ссылку — ничего не меняется
    assert conn.execute("SELECT enabled FROM bots WHERE id = ?", (bid,)).fetchone()[0] == 1
    r = c.post(url, data={"action": "decline"})
    assert "хомӯш" in r.text
    row = conn.execute("SELECT enabled, disabled_reason FROM bots WHERE id = ?", (bid,)).fetchone()
    assert row["enabled"] == 0 and row["disabled_reason"] == "terms"
    assert bots.can_enable(conn, bid)[0] is False          # сам не включит, пока не согласится
    c.post(url, data={"action": "agree"})
    row = conn.execute("SELECT enabled, disabled_reason FROM bots WHERE id = ?", (bid,)).fetchone()
    assert row["enabled"] == 1 and row["disabled_reason"] is None
    c.post(url, data={"action": "delete"})                 # без галочки «мефаҳмам» — не удаляет
    assert conn.execute("SELECT COUNT(*) FROM bots WHERE id = ?", (bid,)).fetchone()[0] == 1
    c.post(url, data={"action": "delete", "sure": "1"})
    assert conn.execute("SELECT COUNT(*) FROM bots WHERE id = ?", (bid,)).fetchone()[0] == 0


def test_silence_disables_after_deadline_and_old_link_dead(app, config, conn):
    bid = _bot(conn, config)
    _, sent = _send(conn, config)
    assert botterms.enforce(conn) == 0
    later = datetime.now(timezone.utc) + timedelta(hours=botterms.DEADLINE_HOURS + 1)
    assert botterms.enforce(conn, later) == 1
    assert conn.execute("SELECT disabled_reason FROM bots WHERE id = ?", (bid,)).fetchone()[0] == "terms"
    _send(conn, config)                                    # новая рассылка — старая ссылка не работает
    assert "кӯҳна" in botterms.answer(conn, config, sent[0][3].rsplit("/", 1)[1], "agree")


def test_admin_sends_from_bots_page(app, config, conn, monkeypatch):
    _bot(conn, config)
    got = []
    monkeypatch.setattr(botterms.send_all, "__defaults__", (lambda *a: got.append(a) or 1,))
    c = TestClient(app)
    token = web_login(c, "admin@example.com", "adminpass123")
    assert "Условия для ботов партнёров" in c.get("/admin/bots").text
    r = c.post("/admin/bots/terms", data={"csrf": token, "text": "Шарт {bot} то {deadline}", "send": "1"})
    assert "Условия отправлены в 1 бот" in r.text and "условия: ⏳ ҷавоб нест" in r.text
    assert got and got[0][2].startswith("Шарт @partner_bot то ")


def test_page_keeps_bold_but_escapes_other_tags(app, config, conn):
    _bot(conn, config)
    botterms.save_text(conn, "<b>Шарт</b> <script>x()</script>\nсатри 2")
    _, sent = _send(conn, config)
    html = TestClient(app).get(sent[0][3].replace(config.base_url, "")).text
    assert "<b>Шарт</b>" in html and "<script>x()" not in html and "сатри 2" in html

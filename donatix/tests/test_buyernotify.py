"""Покупатель с Telegram узнаёт о каждом решении — где бы ни купил. Одно событие — одно сообщение."""
from dataclasses import replace

from conftest import add_receipt, make_client

from donatix import buyernotify, db, orders, payments


def _link(conn, uid, tg_id=7101, lang="ru"):
    conn.execute("INSERT INTO shop_users (tg_id, user_id, name, lang, created_at) VALUES (?, ?, 'A', ?, ?)",
                 (tg_id, uid, lang, db.now()))


def _payment(conn, uid):
    c = conn.execute("INSERT INTO payments (user_id, method, amount_micro, pay_amount, pay_currency, created_at) "
                     "VALUES (?, 'alif', 500000, '545', 'TJS', ?)", (uid, db.now()))
    add_receipt(conn, c.lastrowid)
    return c.lastrowid


def _age(conn, table, col, oid):
    conn.execute(f"UPDATE {table} SET {col} = '2000-01-01T00:00:00.000Z' WHERE id = ?", (oid,))


def test_site_purchase_and_payment_reach_telegram(conn, config, monkeypatch):
    cfg = replace(config, shop_bot_token="T")
    sent = []

    class R:
        status_code = 200
    monkeypatch.setattr(buyernotify.httpx, "post", lambda url, json, timeout: sent.append(json) or R())
    uid, _ = make_client(conn, "tgbuyer", balance="0")
    _link(conn, uid)
    assert buyernotify.tick(conn, cfg) == 0                     # первый запуск: старое не рассылаем
    db.set_setting(conn, buyernotify.SINCE_KEY, "1999-01-01T00:00:00.000Z")

    # пополнение решили (админ/кассир/автоплатёж) — сообщение сразу
    pid = _payment(conn, uid)
    assert payments.confirm(conn, cfg, pid, 1)
    assert len(sent) == 1 and sent[0]["chat_id"] == 7101 and "Оплата получена" in sent[0]["text"]
    _age(conn, "payments", "resolved_at", pid)
    assert buyernotify.tick(conn, cfg) == 0 and len(sent) == 1  # второй раз не пишем

    pid2 = _payment(conn, uid)
    assert payments.reject(conn, cfg, pid2, 1, "Чек не тот")
    assert len(sent) == 2 and "отклонена" in sent[1]["text"]

    # заказ на сайте: выполнен и не выполнен (возврат) — воркер пишет
    def order(status):
        c = conn.execute("INSERT INTO orders (user_id, product_id, kind, product_name, quantity, fields_json, unit_price, "
                         "total_micro, cost_micro, status, supplier_idem_key, source, created_at, updated_at, "
                         "completed_at, public_id, error) VALUES (?, 'p', 'topup', 'Free Fire 100', 1, '{}', '1', 100000, "
                         "90000, ?, ?, 'panel', ?, ?, '2000-01-01T00:00:00.000Z', 'dx-x', 'нет связи')",
                         (uid, status, f"s-{status}", db.now(), db.now()))
        conn.execute("UPDATE orders SET public_id = 'dx-' || id WHERE id = ?", (c.lastrowid,))
        return c.lastrowid
    ok, bad = order("completed"), order("failed")
    assert buyernotify.tick(conn, cfg) == 2
    texts = [s["text"] for s in sent[2:]]
    assert any(f"dx-{ok}" in t and "выполнен" in t for t in texts)
    assert any(f"dx-{bad}" in t and "вернулись на баланс" in t for t in texts)
    assert buyernotify.tick(conn, cfg) == 0                     # повторов нет

    # клиент без Telegram — ничего
    other, _ = make_client(conn, "notg", balance="0")
    assert payments.confirm(conn, cfg, _payment(conn, other), 1) and len(sent) == 4
    assert orders.client_status("attention") == "processing"

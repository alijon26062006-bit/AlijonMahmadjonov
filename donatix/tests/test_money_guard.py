"""Защита денег: атаки из аудита безопасности больше не проходят."""
from datetime import datetime, timezone

from conftest import balance

from donatix import accounts, db, dcbank, orders, payments
from donatix.money import to_micro

CARD = "5058 2700 1234 5678"
PNG1 = b"\x89PNG\r\n\x1a\n" + b"1" * 64
PNG2 = b"\x89PNG\r\n\x1a\n" + b"2" * 64


def _dc(config, conn):
    config.tg_api_id, config.tg_api_hash, config.bank_bot = 1, "x" * 32, "dc_next_bot"
    payments.save_methods(conn, [{"code": "dc", "title": "Душанбе Сити", "currency": "TJS",
                                  "details": f"Карта {CARD}, Алиджон", "enabled": True, "auto": "dcbank"}])


def _user(conn, n="user1"):
    uid = accounts.create_user(conn, email=f"{n}@example.com", login=n, password="password123", status="active")
    return uid, accounts.get_user(conn, uid)


def _notice(amount, kod):
    return (f"Zachislenie\nSumma {amount} TJS\nKomis 0.00 TJS\nZachislenie {amount} TJS\nData 19:40 15.09.26\n"
            f"Otpravitel 9990000***1111\nKod {kod}\nKarta 9999000011115678\nBalans 3 686.07 TJS")


def test_dc_auto_paid_receipt_reuse_is_flagged(app, config, conn):
    """Перевод зачислен автоматически по уведомлению банка, потом тот же чек — ко второй заявке: «ЭТОТ ЧЕК УЖЕ БЫЛ»."""
    _dc(config, conn)
    uid, user = _user(conn)
    with db.tx(conn):
        p1 = payments.create(conn, config, user, "dc", "", amount_tjs="100")
    payments.start_auto(conn, config, p1)
    r1 = conn.execute("SELECT * FROM payments WHERE id=?", (p1,)).fetchone()
    assert r1["pay_amount"] == "100.01"
    res = dcbank.handle(conn, config, source="dc_next_bot", message_id=1, text=_notice("100.01", "555001"))
    assert res["status"] == "matched"
    first = balance(conn, uid)
    assert first > 0

    # вторая заявка на ту же сумму — «хвост» суммы снова свободен
    with db.tx(conn):
        p2 = payments.create(conn, config, user, "dc", "", amount_tjs="100")
    payments.start_auto(conn, config, p2)
    r2 = conn.execute("SELECT * FROM payments WHERE id=?", (p2,)).fetchone()
    assert r2["pay_amount"] == "100.01"
    now_local = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    seen = {"is_receipt": True, "bank": "Душанбе Сити", "amount": 100.01, "currency": "TJS",
            "datetime": now_local, "txn_id": "555001", "recipient": "5058 **** **** 5678", "status": "success",
            "recipient_ok": "yes", "forgery": "real", "signs": []}
    payments.attach_receipt(conn, config, uid, p2, PNG1, seen=seen)
    r2 = conn.execute("SELECT * FROM payments WHERE id=?", (p2,)).fetchone()
    import json
    ai = json.loads(r2["receipt_ai"])
    assert ai["dup_of"] == p1, ai
    assert "ЭТОТ ЧЕК УЖЕ БЫЛ" in __import__("donatix.receipt_ai").receipt_ai.summary(ai, r2["pay_amount"], "TJS")


def test_dc_same_amount_without_txn_is_flagged(app, config, conn):
    """В чеке нет номера операции — ловим по сумме: этот же клиент, та же сумма уже пришла автоматом."""
    _dc(config, conn)
    uid, user = _user(conn)
    with db.tx(conn):
        p1 = payments.create(conn, config, user, "dc", "", amount_tjs="100")
    payments.start_auto(conn, config, p1)
    dcbank.handle(conn, config, source="dc_next_bot", message_id=1, text=_notice("100.01", "555002"))
    with db.tx(conn):
        p2 = payments.create(conn, config, user, "dc", "", amount_tjs="100")
    payments.start_auto(conn, config, p2)
    seen = {"is_receipt": True, "bank": "Душанбе Сити", "amount": 100.01, "currency": "TJS", "datetime": "",
            "txn_id": "", "recipient": "", "status": "success", "recipient_ok": "yes", "forgery": "real", "signs": []}
    payments.attach_receipt(conn, config, uid, p2, PNG1, seen=seen)
    import json
    ai = json.loads(conn.execute("SELECT receipt_ai FROM payments WHERE id=?", (p2,)).fetchone()[0])
    assert ai["dup_of"] == p1


def test_receipt_amount_never_raises_credit(app, config, conn):
    """Сумма из чека больше заявки — заявку НЕ увеличиваем (отредактированный чек на 99 999), админ видит 🚨."""
    config.pay_methods = {"alif": "Алиф: +992 90 000 00 00 (Али)"}
    uid, user = _user(conn)
    with db.tx(conn):
        pid = payments.create(conn, config, user, "alif", "", amount_tjs="10")
    before = conn.execute("SELECT amount_micro FROM payments WHERE id=?", (pid,)).fetchone()[0]
    seen = {"is_receipt": True, "bank": "Alif", "amount": 99999.0, "currency": "TJS", "datetime": "",
            "txn_id": "", "recipient": "", "status": "success", "recipient_ok": "unknown",
            "forgery": "suspicious", "signs": ["x"]}
    payments.attach_receipt(conn, config, uid, pid, PNG2, seen=seen)
    after = conn.execute("SELECT amount_micro, pay_amount FROM payments WHERE id=?", (pid,)).fetchone()
    assert after[0] == before
    import json
    ai = json.loads(conn.execute("SELECT receipt_ai FROM payments WHERE id=?", (pid,)).fetchone()[0])
    assert ai["amount_more"].startswith("99999")


def test_rounding_gift_not_refunded(app, config, conn, supplier):
    uid, user = _user(conn)
    q = orders.quote(config, user, {"base_price": "0.99", "kind": "topup"}, 1)
    total = q["total_micro"]
    with db.tx(conn):
        accounts.post_ledger(conn, uid, total - 100, "seed")
    start = balance(conn, uid)
    supplier.fail_next = "reject_other"
    order, _ = orders.create_order(conn, config, supplier, accounts.get_user(conn, uid),
                                   product_id="topup-pubg-60", fields={"player_id": "123456789"},
                                   source="panel")
    assert order["status"] == "failed"
    assert balance(conn, uid) == start   # копеечное округление при возврате не дарим


def test_mark_fake_allowed_for_dc_receipt(app, config, conn):
    _dc(config, conn)
    uid, user = _user(conn)
    with db.tx(conn):
        pid = payments.create(conn, config, user, "dc", "", amount_tjs="500")
    payments.start_auto(conn, config, pid)
    payments.attach_receipt(conn, config, uid, pid, PNG2, seen=None)   # чек вместо уведомления банка, денег не было
    assert payments.confirm(conn, config, pid, 1)                      # админ зачислил по чеку
    payments.mark_fake(conn, config, pid, 1)                           # поддельный чек — сумма списана обратно
    assert balance(conn, uid) == 0


def test_cashier_cannot_decide_own_shopbot_request(app, config, conn):
    """Заявка с аккаунта бота-магазина, привязанного к Telegram кассира, — у кассира её нет."""
    from donatix import cashiers, tgbot
    tg = 777000111
    uid, user = _user(conn, "kassir")
    conn.execute("INSERT INTO shop_users (tg_id, user_id, created_at) VALUES (?, ?, ?)", (tg, uid, db.now()))
    cashiers.add(conn, tg, "Касса")
    assert uid in tgbot.cashier_own_users(conn, tg)

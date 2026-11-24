"""Случай из жизни (заявка #18243): чек от нейросети, номер операции старого чека, сумма 50 000 при заявке 411."""
import struct
import zlib

import pytest

from donatix import accounts, payments


def _png_with_text(text: bytes) -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"tEXt", b"DigitalSourceType\x00" + text)
            + chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff")) + chunk(b"IEND", b""))


@pytest.fixture
def setup(app, config, conn, monkeypatch):
    monkeypatch.setattr("donatix.worker.notify_admin_file", lambda *a, **k: None)
    sent = []
    monkeypatch.setattr("donatix.worker.notify_admin", lambda cfg, text, *a, **k: sent.append(text))
    config.pay_methods = {"alif": "Алиф: +992 90 000 00 00 (Али)"}
    uid = accounts.create_user(conn, email="f@example.com", login="ussm", password="password123", status="active")
    return uid, accounts.get_user(conn, uid), sent


def _seen(amount):
    return {"is_receipt": True, "bank": "Алиф", "amount": amount, "currency": "TJS", "datetime": "",
            "txn_id": "985793636", "recipient": "+992 90 000 00 00", "status": "success", "recipient_ok": "yes",
            "forgery": "real", "signs": []}


def test_ai_generated_receipt_is_rejected_and_counted_as_fraud(setup, conn, config):
    uid, user, sent = setup
    pid = payments.create(conn, config, user, "alif", "", amount_tjs="411.02")
    body = _png_with_text(b"http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia")
    with pytest.raises(payments.ReceiptRejected) as err:
        payments.attach_receipt(conn, config, uid, pid, body, seen=_seen(411.02))
    assert "нейросет" in str(err.value)
    assert conn.execute("SELECT receipt_file FROM payments WHERE id = ?", (pid,)).fetchone()[0] is None
    assert conn.execute("SELECT fraud_count FROM users WHERE id = ?", (uid,)).fetchone()[0] == 1


def test_receipt_amount_100x_request_is_rejected(setup, conn, config):
    uid, user, _ = setup
    pid = payments.create(conn, config, user, "alif", "", amount_tjs="411.02")
    with pytest.raises(payments.ReceiptRejected) as err:
        payments.attach_receipt(conn, config, uid, pid, b"\x89PNG\r\n\x1a\n" + b"Q" * 80, seen=_seen(50000.0))
    assert "в разы больше" in str(err.value)


def test_decimal_point_misread_is_not_rejected(setup, conn, config):
    uid, user, _ = setup
    pid = payments.create(conn, config, user, "alif", "", amount_tjs="54.50")
    payments.attach_receipt(conn, config, uid, pid, b"\x89PNG\r\n\x1a\n" + b"Z" * 80, seen=_seen(5450.0))   # ИИ потерял запятую
    assert conn.execute("SELECT receipt_file FROM payments WHERE id = ?", (pid,)).fetchone()[0]

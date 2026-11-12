"""Повтор чека: отклоняем ТОЛЬКО уже принятый чек — тот же файл, та же картинка (пересжатая Telegram)
или тот же перевод целиком (номер операции + сумма + минута). Настоящие новые чеки не отклоняем,
даже если ИИ прочитал похожие данные."""

import io

import pytest
from PIL import Image, ImageDraw, ImageFont

from donatix import accounts, payments, receipt_ai

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _picture(amount: str, when: str, op: str, fmt="PNG", scale=1.0, quality=90) -> bytes:
    im = Image.new("RGB", (720, 1400), (255, 255, 255))
    d = ImageDraw.Draw(im)
    try:
        big, small = ImageFont.truetype(FONT, 44), ImageFont.truetype(FONT, 30)
    except OSError:
        big = small = ImageFont.load_default()
    d.rectangle([0, 0, 720, 160], fill=(0, 140, 90))
    d.text((40, 50), "Alif", fill=(255, 255, 255), font=big)
    d.text((220, 460), f"{amount} TJS", fill=(20, 20, 20), font=big)
    for i, (k, v) in enumerate([("Дата", when), ("Получатель", "+992 90 000 00 00"), ("Операция", op)]):
        d.text((40, 600 + i * 90), k, fill=(130, 130, 130), font=small)
        d.text((380, 600 + i * 90), v, fill=(20, 20, 20), font=small)
    if scale != 1.0:
        im = im.resize((int(720 * scale), int(1400 * scale)))
    buf = io.BytesIO()
    im.save(buf, fmt, **({"quality": quality} if fmt == "JPEG" else {}))
    return buf.getvalue()


def _seen(amount: float, when: str, txn: str) -> dict:
    return {"is_receipt": True, "bank": "Алиф", "amount": amount, "currency": "TJS", "datetime": when, "txn_id": txn,
            "recipient": "+992 90 000 00 00", "status": "success", "recipient_ok": "yes", "forgery": "real",
            "signs": []}


@pytest.fixture
def setup(app, config, conn, monkeypatch):
    monkeypatch.setattr("donatix.worker.notify_admin_file", lambda *a, **k: None)
    monkeypatch.setattr("donatix.worker.notify_admin", lambda *a, **k: None)
    config.pay_methods = {"alif": "Алиф: +992 90 000 00 00 (Али)"}
    uid = accounts.create_user(conn, email="r@example.com", login="rcl", password="password123", status="active")
    user = accounts.get_user(conn, uid)

    def pay(body: bytes, seen: dict, keep: bool = False) -> int:
        pid = payments.create(conn, config, user, "alif", "100")
        try:
            payments.attach_receipt(conn, config, uid, pid, body, seen=seen)
        finally:
            if not keep:   # одна заявка на проверке за раз — освобождаем место для следующей
                payments.cancel(conn, uid, pid, config)
        return pid
    first = pay(_picture("100.00", "12.11.2026 14:03", "8812345"), _seen(100.0, "2026-11-12 14:03", "8812345"),
                keep=True)
    payments.confirm(conn, config, first, 1)    # админ принял
    return pay, first


def test_same_picture_recompressed_is_rejected(setup):
    pay, first = setup
    again = _picture("100.00", "12.11.2026 14:03", "8812345", fmt="JPEG", scale=0.75, quality=55)  # как пересжал Telegram
    with pytest.raises(payments.ReceiptUsed) as err:
        pay(again, _seen(100.0, "2026-11-12 14:03", ""))     # ИИ на этот раз не прочитал номер — всё равно ловим
    assert f"#{first}" in str(err.value)


def test_new_real_receipts_are_not_rejected(setup):
    pay, _ = setup
    # тот же банк и шаблон, ИИ прочитал тот же «номер операции» (постоянное поле), но сумма или время другие
    pay(_picture("150.00", "12.11.2026 14:03", "8812345"), _seen(150.0, "2026-11-12 14:03", "8812345"))
    pay(_picture("100.00", "12.11.2026 14:09", "8812399"), _seen(100.0, "2026-11-12 14:09", "8812345"))
    # та же сумма и минута, но номер операции другой — другой перевод
    pay(_picture("100.00", "12.11.2026 14:03", "8812346"), _seen(100.0, "2026-11-12 14:03", "8812346"))


def test_other_screenshot_of_same_transfer_is_rejected(setup):
    pay, first = setup
    other = _picture("100.00", "12.11.2026 14:03", "8812345", scale=0.5)   # другой скрин, но всё совпало
    with pytest.raises(payments.ReceiptUsed):
        pay(other + b"x", _seen(100.0, "2026-11-12 14:03", "8812345"))


def test_image_hash_tolerates_recompression():
    a = _picture("100.00", "12.11.2026 14:03", "8812345")
    b = _picture("100.00", "12.11.2026 14:03", "8812345", fmt="JPEG", scale=0.75, quality=55)
    assert receipt_ai.hash_distance(receipt_ai.image_hash(a), receipt_ai.image_hash(b)) <= receipt_ai.PHASH_SAME
    assert receipt_ai.image_hash(b"%PDF-1.4 ...", "pdf") is None

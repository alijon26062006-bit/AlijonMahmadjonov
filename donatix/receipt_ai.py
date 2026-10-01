"""Чтение чеков ИИ (тот же ключ OpenAI, что у бота поддержки) и защита от повторных чеков.

Когда клиент присылает чек, модель с «зрением» читает: банк, сумму, валюту, дату и время,
номер операции, получателя. Сайт запоминает это у заявки и ищет по базе:
  • тот же номер операции — чек уже был;
  • та же сумма + валюта + время до минуты + банк — тот же перевод, даже если скриншот другой.
Повтор отклоняется сразу, новый чек уходит админу вместе с тем, что прочитал ИИ.

Нет ключа, PDF или ИИ не ответил — заявка всё равно принимается, админ проверяет как раньше.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import sqlite3
from typing import Any

import httpx

from .config import Config

log = logging.getLogger(__name__)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
TIMEOUT = 25
MIME = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}

PROMPT = (
    "Это скриншот или фото банковского чека/перевода (банки Таджикистана: Алиф, Душанбе Сити, Эсхата, "
    "Амонатбонк, Спитамен и др.; также крипто-переводы). Прочитай его и верни ТОЛЬКО JSON:\n"
    '{"is_receipt": true/false, "bank": "название банка или кошелька", "amount": число, '
    '"currency": "TJS|USD|RUB|USDT|…", "datetime": "YYYY-MM-DD HH:MM", '
    '"txn_id": "номер операции/квитанции/транзакции", "recipient": "получатель: номер карты, телефона или имя", '
    '"status": "success|pending|failed|unknown"}\n'
    "Если поля нет на изображении — пустая строка (для amount — 0). Ничего не придумывай."
)


def enabled(config: Config) -> bool:
    return bool(config.openai_api_key)


def read(config: Config, data: bytes, ext: str, transport: httpx.BaseTransport | None = None) -> dict[str, Any] | None:
    """Прочитать чек. None — не получилось (нет ключа, PDF, ошибка) — тогда проверяет только админ."""
    mime = MIME.get(ext)
    if not enabled(config) or mime is None:
        return None
    url = f"data:{mime};base64,{base64.b64encode(data).decode()}"
    body = {
        "model": config.receipt_model, "temperature": 0, "max_tokens": 400,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": url, "detail": "high"}}]}],
    }
    try:
        with httpx.Client(timeout=TIMEOUT, transport=transport) as client:
            resp = client.post(OPENAI_URL, json=body, headers={"Authorization": f"Bearer {config.openai_api_key}"})
        if resp.status_code != 200:
            log.warning("чек: OpenAI %s %s", resp.status_code, resp.text[:200])
            return None
        raw = json.loads(resp.json()["choices"][0]["message"]["content"])
    except Exception:  # noqa: BLE001 — чтение чека не должно мешать пополнению
        log.exception("чек: не прочитан")
        return None
    return clean(raw)


def clean(raw: dict[str, Any]) -> dict[str, Any]:
    """Привести ответ модели к одному виду."""
    def s(key: str) -> str:
        return str(raw.get(key) or "").strip()[:120]
    try:
        amount = round(float(str(raw.get("amount") or 0).replace(" ", "").replace(",", ".")), 2)
    except ValueError:
        amount = 0.0
    return {"is_receipt": bool(raw.get("is_receipt", True)), "bank": s("bank"), "amount": amount,
            "currency": s("currency").upper()[:8], "datetime": s("datetime")[:16], "txn_id": s("txn_id"),
            "recipient": s("recipient"), "status": s("status").lower() or "unknown"}


def txn_key(d: dict[str, Any]) -> str:
    """Номер операции без пробелов и знаков. Короче 5 символов — не надёжен, не используем."""
    key = re.sub(r"[^0-9A-Za-z]", "", d.get("txn_id") or "").upper()
    return key if len(key) >= 5 else ""


def fingerprint(d: dict[str, Any]) -> str:
    """Тот же перевод: сумма + валюта + время до минуты + банк. Без суммы или времени — не считаем."""
    when = re.sub(r"[^0-9]", "", d.get("datetime") or "")
    if not d.get("amount") or len(when) < 12:
        return ""
    bank = re.sub(r"[^a-zа-я0-9]", "", (d.get("bank") or "").lower())
    return f"{d['amount']:.2f}|{d.get('currency') or ''}|{when[:12]}|{bank}"


def duplicate(conn: sqlite3.Connection, payment_id: int, d: dict[str, Any]) -> sqlite3.Row | None:
    """Заявка с тем же чеком (ждёт проверки или уже зачислена)."""
    key, fp = txn_key(d), fingerprint(d)
    if key:
        row = conn.execute("SELECT id, status FROM payments WHERE receipt_txn = ? AND id != ? "
                           "AND status IN ('pending', 'paid')", (key, payment_id)).fetchone()
        if row:
            return row
    if fp:
        return conn.execute("SELECT id, status FROM payments WHERE receipt_fp = ? AND id != ? "
                            "AND status IN ('pending', 'paid')", (fp, payment_id)).fetchone()
    return None


def amount_matches(d: dict[str, Any], pay_amount: Any, pay_currency: str) -> bool | None:
    """Совпадает ли сумма чека с заявкой. None — сравнить нечем."""
    try:
        want = float(str(pay_amount).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if not d.get("amount") or not want:
        return None
    if d.get("currency") and pay_currency and d["currency"] != pay_currency.upper():
        return False
    return abs(d["amount"] - want) <= max(0.01, want * 0.005)


def summary(d: dict[str, Any] | None, pay_amount: Any = None, pay_currency: str = "") -> str:
    """Строка для админа: что прочитал ИИ и совпадает ли сумма."""
    if not d:
        return "🤖 Чек не прочитан автоматически — проверьте вручную."
    parts = [p for p in (d["bank"], f"{d['amount']:g} {d['currency']}".strip() if d["amount"] else "",
                         d["datetime"], f"№ {d['txn_id']}" if d["txn_id"] else "") if p]
    line = "🤖 Чек: " + (" · ".join(parts) or "данных не видно")
    match = amount_matches(d, pay_amount, pay_currency)
    if match is True:
        line += "\n✅ Сумма совпадает с заявкой"
    elif match is False:
        line += f"\n⚠️ Сумма НЕ совпадает с заявкой ({pay_amount} {pay_currency})"
    if not d["is_receipt"]:
        line += "\n⚠️ Похоже, это не чек"
    if d["status"] == "failed":
        line += "\n⚠️ В чеке перевод не прошёл"
    return line

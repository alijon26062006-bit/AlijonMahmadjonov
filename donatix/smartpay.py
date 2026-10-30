"""SmartPay (smartpay.tj): оплата из любого банка Таджикистана — баланс пополняется сам, чек не нужен.

Как идёт оплата:
  1. Клиент создаёт заявку способом с автозачислением «SmartPay» — сайт создаёт инвойс
     (POST /merchant/invoices, order_id = «dx<номер заявки>») и получает payment_link: страница оплаты / QR.
  2. На телефоне — кнопки банков (GET /merchant/banks, кешируем на сутки): нажал свой банк — сайт создаёт
     инвойс с deeplink_bank_id (order_id = «dx<номер>-b<банк>») и сразу открывает приложение банка.
  3. После оплаты SmartPay присылает webhook на /pay/smartpay/webhook. Опроса статуса у SmartPay нет —
     только webhook. Ему верим, только если совпали ОБЕ проверки: заголовок X-Api-Token (64 hex из настроек
     webhook) и подпись HMAC-SHA256 «payment_date|amount|order_id|bank_id|invoice_uuid» секретом webhook.
     Сумма приходит в дирамах и должна ровно совпасть с заявкой. Один платёж — одно зачисление
     (payments.confirm закрывает заявку один раз, payment_id пишется в ext_id — он уникален).
  4. Не оплатили за время жизни инвойса — заявка закрывается сама.

Ключи — только в .env сервера: DONATIX_SMARTPAY_KEY (x-app-token), DONATIX_SMARTPAY_MODE (sandbox|production),
DONATIX_SMARTPAY_HOOK_TOKEN (X-Api-Token webhook), DONATIX_SMARTPAY_HOOK_SECRET (секрет подписи).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from decimal import ROUND_DOWN, Decimal
from typing import Any

import httpx

from . import db
from .config import Config

log = logging.getLogger(__name__)

KIND = "smartpay"
BASES = {"sandbox": "https://sandbox.smartpay.tj/api/merchant", "production": "https://ecomm.smartpay.tj/api/merchant"}
LIFETIME = 1800                    # инвойс живёт 30 минут
MIN_TJS = Decimal("2")             # меньше SmartPay не принимает
BANKS_TTL = 86400                  # список банков — раз в сутки
EXPIRED_NOTE = "SmartPay: время оплаты вышло"
# Если SmartPay не ответил списком — кнопки по документации (DEEPLINK_BANK_ID)
DEFAULT_BANKS = [(8, "Алиф Банк"), (9, "Эсхата"), (2, "Амонатбонк"), (11, "Хумо"), (7, "CBT / Фаврӣ"),
                 (4, "ICB"), (10, "Арванд"), (13, "ССБ"), (15, "Vasl Pay"), (21, "IBT")]
ORDER_RE = re.compile(r"^dx(\d+)(?:-b\d+)?$")


class SmartPayError(Exception):
    pass


def ready(config: Config) -> bool:
    """Ключ API задан — способ «SmartPay» работает автоматически."""
    return bool(config.smartpay_key)


def hook_ready(config: Config) -> bool:
    """Webhook защищён: без токена и секрета уведомлению не верим — баланс не пополнится."""
    return bool(config.smartpay_hook_token and config.smartpay_hook_secret)


def base_url(config: Config) -> str:
    return BASES.get(config.smartpay_mode, BASES["production"])


def _call(config: Config, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Запрос к SmartPay. HTTP почти всегда 200 — успех определяет поле result (проверяет вызывающий)."""
    try:
        r = httpx.request(method, base_url(config) + path, json=body, timeout=20,
                          headers={"x-app-token": config.smartpay_key, "Content-Type": "application/json"})
    except httpx.HTTPError as exc:
        raise SmartPayError(f"SmartPay не отвечает ({exc.__class__.__name__}) — попробуйте ещё раз.") from None
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code != 200:
        detail = data.get("detail") if isinstance(data, dict) else ""
        if isinstance(detail, list):
            detail = "; ".join(str(x) for x in detail)
        if r.status_code in (401, 403):
            log.error("SmartPay: ключ не принят (%s): %s", r.status_code, detail)
            raise SmartPayError("Оплата через SmartPay временно недоступна — выберите другой способ.")
        raise SmartPayError(str(detail or f"SmartPay: ошибка {r.status_code}")[:200])
    return data if isinstance(data, dict) else {}


def health(config: Config) -> str:
    """Проверить ключ: вернёт UUID мерчанта. Ошибка — SmartPayError с причиной."""
    if not ready(config):
        raise SmartPayError("Ключ SmartPay не задан на сервере (DONATIX_SMARTPAY_KEY).")
    data = _call(config, "GET", "/health")
    uuid = str(data.get("merchant_unit_uuid") or "")
    if not uuid:
        raise SmartPayError("SmartPay ответил без UUID мерчанта.")
    return uuid


def banks(conn: sqlite3.Connection, config: Config) -> list[dict[str, Any]]:
    """Банки для кнопок (id, название). Кеш на сутки; не вышло — список из документации."""
    try:
        cached = json.loads(db.get_setting(conn, "smartpay.banks") or "{}")
    except ValueError:
        cached = {}
    if cached.get("at", 0) > time.time() - BANKS_TTL and cached.get("banks"):
        return cached["banks"]
    out: list[dict[str, Any]] = []
    if ready(config):
        try:
            for b in _call(config, "GET", "/banks").get("banks") or []:
                if isinstance(b, dict) and str(b.get("id", "")).isdigit() and b.get("name"):
                    out.append({"id": int(b["id"]), "name": str(b["name"])[:40]})
        except SmartPayError as exc:
            log.warning("SmartPay: список банков: %s", exc)
    if out:
        db.set_setting(conn, "smartpay.banks", json.dumps({"at": time.time(), "banks": out}, ensure_ascii=False))
        return out
    return [{"id": i, "name": n} for i, n in DEFAULT_BANKS]


def order_id(payment_id: int, bank_id: int | None = None) -> str:
    """Наш номер заказа в SmartPay: dx1234 (ссылка/QR) или dx1234-b8 (сразу в приложение банка)."""
    return f"dx{payment_id}" + (f"-b{bank_id}" if bank_id else "")


def _amount(p: sqlite3.Row) -> Decimal:
    return Decimal(p["pay_amount"]).quantize(Decimal("0.01"), rounding=ROUND_DOWN)


def create(conn: sqlite3.Connection, config: Config, payment_id: int, bank_id: int | None = None) -> dict[str, str]:
    """Инвойс на заявку. Повторный запрос с тем же order_id вернёт тот же инвойс (идемпотентность SmartPay)."""
    p = conn.execute("SELECT * FROM payments WHERE id = ?", (payment_id,)).fetchone()
    if p is None:
        raise SmartPayError("Заявка не найдена.")
    amount = _amount(p)
    if amount < MIN_TJS:
        raise SmartPayError(f"Через SmartPay — от {MIN_TJS} сомони.")
    body: dict[str, Any] = {
        "order_id": order_id(payment_id, bank_id), "amount": float(amount),
        "description": f"Пополнение баланса {config.site_name} #{payment_id}", "lifetime": LIFETIME,
        "return_url": f"{config.base_url.rstrip('/')}/panel/balance/{payment_id}/pay",
    }
    if bank_id:
        body["deeplink_bank_id"] = int(bank_id)
    data = _call(config, "POST", "/invoices", body)
    if data.get("result") != 200 or not data.get("payment_link"):
        log.warning("SmartPay: инвойс для #%s не создан: %s", payment_id, data.get("message"))
        raise SmartPayError(str(data.get("message") or "SmartPay не создал счёт — попробуйте ещё раз.")[:200])
    return {"payment_link": str(data["payment_link"]), "deeplink_url": str(data.get("deeplink_url") or ""),
            "invoice_uuid": str(data.get("invoice_uuid") or ""), "smartpay_id": str(data.get("smartpay_id") or "")}


def start(conn: sqlite3.Connection, config: Config, payment_id: int) -> None:
    """Сразу после создания заявки: инвойс и ссылка на оплату (страница SmartPay / QR)."""
    inv = create(conn, config, payment_id)
    conn.execute("UPDATE payments SET auto_kind = ?, pay_url = ?, pay_memo = ? WHERE id = ?",
                 (KIND, inv["payment_link"], inv["smartpay_id"] or None, payment_id))


def bank_link(conn: sqlite3.Connection, config: Config, payment_id: int, bank_id: int) -> str:
    """Кнопка банка: инвойс с диплинком — ссылка, которая открывает приложение банка с суммой."""
    p = conn.execute("SELECT status, auto_kind FROM payments WHERE id = ?", (payment_id,)).fetchone()
    if p is None or p["status"] != "pending" or p["auto_kind"] != KIND:
        raise SmartPayError("Заявка уже закрыта — создайте новую.")
    inv = create(conn, config, payment_id, bank_id)
    return inv["deeplink_url"] or inv["payment_link"]


def sign_link(config: Config, payment_id: int) -> str:
    """Подпись для ссылок кнопок банков: открываются и из бота/мини-приложения, где нет входа на сайт."""
    return hmac.new(config.secret_key.encode(), f"smartpay:{payment_id}".encode(), hashlib.sha256).hexdigest()[:24]


def check_link(config: Config, payment_id: int, sig: str) -> bool:
    return hmac.compare_digest(sign_link(config, payment_id), sig or "")


# ── webhook ──────────────────────────────────────────────────

def _sign_date(raw: Any) -> str:
    """payment_date в подписи — «YYYY-MM-DD HH:MM:SS»: без «T» и без микросекунд."""
    text = str(raw or "").strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return text.replace("T", " ")[:19]


def signature(secret: str, payload: dict[str, Any]) -> str:
    line = (f"{_sign_date(payload.get('payment_date'))}|{payload.get('amount', '')}|{payload.get('order_id', '')}|"
            f"{payload.get('bank_id', '')}|{payload.get('invoice_uuid', '')}")
    return hmac.new(secret.encode(), line.encode(), hashlib.sha256).hexdigest()


def verify(config: Config, token: str, payload: dict[str, Any]) -> bool:
    """Обе проверки: токен из заголовка X-Api-Token и подпись в теле. Не настроено — не верим никому."""
    if not hook_ready(config):
        return False
    if not hmac.compare_digest(str(token or ""), config.smartpay_hook_token):
        return False
    return hmac.compare_digest(str(payload.get("signature") or ""), signature(config.smartpay_hook_secret, payload))


def handle_webhook(conn: sqlite3.Connection, config: Config, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Оплата пришла: проверить, найти заявку, сверить сумму и зачислить ровно один раз."""
    from . import payments
    from .cryptopay import _admin_id, _tell_admin
    from .worker import notify_admin
    if not verify(config, token, payload):
        log.warning("SmartPay webhook: не прошёл проверку (order_id=%s)", str(payload.get("order_id"))[:40])
        return {"status": "forbidden"}
    m = ORDER_RE.match(str(payload.get("order_id") or ""))
    pid = int(m.group(1)) if m else 0
    p = conn.execute("SELECT * FROM payments WHERE id = ? AND auto_kind = ?", (pid, KIND)).fetchone() if pid else None
    if p is None:
        notify_admin(config, f"⚠️ SmartPay: оплата по неизвестному заказу {str(payload.get('order_id'))[:40]} — "
                             f"{payload.get('amount')} дирам, банк {payload.get('bank')}. Проверьте в кабинете SmartPay.")
        return {"status": "unknown_order"}
    pay_ref = f"sp:{payload.get('payment_id') or payload.get('invoice_uuid')}"[:120]
    if conn.execute("SELECT 1 FROM payments WHERE ext_id = ?", (pay_ref,)).fetchone():
        return {"status": "duplicate", "payment_id": pid}
    try:
        got = int(payload.get("amount"))
    except (TypeError, ValueError):
        got = -1
    want = int(_amount(p) * 100)
    if got != want:
        notify_admin(config, f"⚠️ SmartPay: заявка #{pid} — пришло {got / 100:.2f} TJS, а ждали {want / 100:.2f}. "
                             "Автоматически не зачислено — проверьте и зачислите вручную.")
        return {"status": "amount_mismatch", "payment_id": pid}
    if p["status"] == "cancelled" and p["admin_note"] == EXPIRED_NOTE:   # оплатили в последнюю секунду
        conn.execute("UPDATE payments SET status = 'pending', admin_note = NULL, resolved_at = NULL WHERE id = ?", (pid,))
    if not payments.confirm(conn, config, pid, _admin_id(conn), who=f"автоматически · SmartPay ({payload.get('bank') or 'банк'})"):
        notify_admin(config, f"⚠️ SmartPay: оплата {got / 100:.2f} TJS пришла, но заявка #{pid} уже закрыта — "
                             "повторно не зачислено. Проверьте.")
        return {"status": "closed", "payment_id": pid}
    try:
        conn.execute("UPDATE payments SET ext_id = ? WHERE id = ?", (pay_ref, pid))
    except sqlite3.IntegrityError:
        log.warning("SmartPay: платёж %s уже записан у другой заявки", pay_ref)
    _tell_admin(conn, config, pid, f"SmartPay · {payload.get('bank') or 'банк'}")
    return {"status": "ok", "payment_id": pid}


def expire(conn: sqlite3.Connection) -> int:
    """Не оплатили за время жизни инвойса (+5 минут на задержку банка) — заявка закрывается."""
    since = (datetime.now(timezone.utc) - timedelta(seconds=LIFETIME + 300)).strftime("%Y-%m-%dT%H:%M:%S")
    return conn.execute("UPDATE payments SET status = 'cancelled', admin_note = ?, resolved_at = ? "
                        "WHERE auto_kind = ? AND status = 'pending' AND created_at < ?",
                        (EXPIRED_NOTE, db.now(), KIND, since)).rowcount

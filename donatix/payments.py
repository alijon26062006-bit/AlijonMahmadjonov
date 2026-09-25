"""Заявки на пополнение баланса.

Клиент выбирает способ (Алиф, DC, Эсхата, USDT…), сумму и переводит деньги
по реквизитам. Админ видит заявку, сверяет поступление и подтверждает —
баланс зачисляется автоматически, клиенту приходит уведомление.
Сюда же подключаются автоматические способы, когда появится API банка."""

from __future__ import annotations

import json
import re
import secrets
import sqlite3
from decimal import ROUND_DOWN, ROUND_UP, Decimal
from typing import Any

from . import accounts, db
from .config import PAY_METHODS, Config
from .money import MoneyError, fmt, to_decimal, to_micro
from .notify import notify


class PaymentError(ValueError):
    pass


CURRENCIES = ("TJS", "USDT", "USD")

#: Сети USDT: перевод в чужой сети не дойдёт — клиент должен видеть сеть явно
NETWORKS = {
    "TRC20": "Tron (TRC20)",
    "BEP20": "BNB Smart Chain (BEP20)",
    "ERC20": "Ethereum (ERC20)",
    "TON": "TON",
}
#: Варианты в админке: валюта и сеть одним списком
CURRENCY_CHOICES = [("TJS", "TJS (сомони, по курсу)"), ("USD", "USD")] + [
    (f"USDT:{n}", f"USDT · {t}") for n, t in NETWORKS.items()] + [("USDT", "USDT (без сети — Binance Pay и т.п.)")]
_DEFAULT_NETWORK = {"usdt_trc20": "TRC20", "usdt_bep20": "BEP20"}


def guess_network(m: dict[str, Any]) -> str:
    """Сеть способа: указана явно, иначе по коду/названию (старые настройки без поля)."""
    if m.get("currency") != "USDT":
        return ""
    if m.get("network") in NETWORKS:
        return m["network"]
    if "network" in m:
        return ""
    text = f"{m.get('code', '')} {m.get('title', '')}".upper()
    return next((n for n in NETWORKS if n in text), _DEFAULT_NETWORK.get(m.get("code", ""), ""))


def network_note(network: str) -> str:
    if network not in NETWORKS:
        return ""
    return (f"Отправляйте USDT только в сети {NETWORKS[network]}. "
            "Перевод в другой сети не дойдёт, и вернуть его нельзя.")


def _default_methods(conn: sqlite3.Connection, config: Config) -> list[dict[str, Any]]:
    """Первый запуск: стандартные способы с реквизитами из старых настроек или .env."""
    out = []
    for code, (title, currency) in PAY_METHODS.items():
        details = db.get_setting(conn, f"pay.{code}")
        if details is None:
            details = config.pay_methods.get(code, "")
        out.append({"code": code, "title": title, "currency": currency, "details": details.strip(),
                    "enabled": bool(details.strip())})
    return out


def settings(conn: sqlite3.Connection, config: Config) -> dict[str, Any]:
    """Способы оплаты, курс, минимум (в сомони) и порог «мало денег». Всё меняется в админке."""
    raw = db.get_setting(conn, "pay.methods_json")
    all_methods = json.loads(raw) if raw else _default_methods(conn, config)
    for m in all_methods:
        m["network"] = guess_network(m)
        m["choice"] = f"USDT:{m['network']}" if m["network"] else m["currency"]
    rate = Decimal(db.get_setting(conn, "pay.tjs_rate") or config.tjs_rate)
    min_tjs = Decimal(db.get_setting(conn, "pay.min_tjs") or config.pay_min_tjs)
    low = Decimal(db.get_setting(conn, "pay.low_balance_usd") or config.low_balance_usd)
    return {
        "all_methods": all_methods,
        "details": {m["code"]: m["details"] for m in all_methods if m.get("enabled") and m["details"].strip()},
        "tjs_rate": rate, "min_tjs": min_tjs, "low_usd": low,
        "min_usd": (min_tjs / rate).quantize(Decimal("0.01"), rounding=ROUND_UP),
    }


def clean_methods(methods_in: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Способы оплаты из формы/бота → как хранятся: проверенные поля, уникальные коды."""
    clean, seen = [], set()
    for m in methods_in:
        title = str(m.get("title", "")).strip()[:60]
        details = str(m.get("details", "")).strip()[:1000]
        if m.get("delete") or (not title and not details):
            continue
        if not title:
            raise PaymentError("У каждого способа должно быть название.")
        code = str(m.get("code") or "").strip() or "m" + secrets.token_hex(3)
        if code in seen:
            code = "m" + secrets.token_hex(3)
        seen.add(code)
        currency, _, network = str(m.get("currency") or "").partition(":")
        currency = currency if currency in CURRENCIES else "TJS"
        network = network if currency == "USDT" and network in NETWORKS else ""
        icon = str(m.get("icon") or "")
        icon = icon if ICON_NAME_RE.fullmatch(icon) else ""
        auto = str(m.get("auto") or "")
        auto = auto if auto in ("trc20", "binance", "bybit") else ""
        if auto == "trc20":
            from .cryptopay import tron_address
            currency, network = "USDT", "TRC20"
            if not tron_address(details):
                raise PaymentError(f"«{title}»: для автозачисления TRC20 в реквизитах нужен адрес кошелька (T…).")
        elif auto == "bybit":
            currency, network = "USDT", ""
            if not re.search(r"\d{5,12}", details):
                raise PaymentError(f"«{title}»: для автозачисления Bybit в реквизитах нужен ваш Bybit UID (цифры).")
        elif auto == "binance":
            currency, network = "USDT", ""
            details = details or "Оплата через Binance Pay — кнопка появится после ввода суммы"
        clean.append({"code": code, "title": title, "currency": currency, "network": network,
                      "details": details, "enabled": bool(m.get("enabled")), "icon": icon, "auto": auto})
    return clean


def save_methods(conn: sqlite3.Connection, methods_in: list[dict[str, Any]]) -> None:
    """Только способы оплаты (курс и минимум не трогаем) — для админ-бота."""
    db.set_setting(conn, "pay.methods_json", json.dumps(clean_methods(methods_in), ensure_ascii=False))


def save_settings(conn: sqlite3.Connection, config: Config, methods_in: list[dict[str, Any]], tjs_rate: str,
                  min_tjs: str, low_usd: str, *, rate_auto: bool | None = None, margin_pct: str = "") -> None:
    from . import rates
    try:
        rate = to_decimal(tjs_rate.replace(",", "."))
        minimum = to_decimal(min_tjs.replace(",", "."))
        low = to_decimal(low_usd.replace(",", ".") or "0")
        margin = to_decimal(margin_pct.replace(",", ".")) if margin_pct.strip() else rates.margin_pct(conn, config)
    except MoneyError:
        raise PaymentError("Курс, минимум, запас и порог — числа.") from None
    if rate <= 0 or minimum <= 0 or low < 0:
        raise PaymentError("Курс и минимум должны быть больше нуля.")
    if not Decimal("-5") <= margin <= Decimal("20"):
        raise PaymentError("Запас к курсу — от -5 до 20 %.")
    auto = rates.auto_enabled(conn, config) if rate_auto is None else rate_auto
    market = db.get_setting(conn, "pay.rate_market")
    if auto and market:
        rate = rates.apply_margin(Decimal(market), margin)  # курс считает автоматика, поле только показывает
    clean = clean_methods(methods_in)
    with db.tx(conn):
        db.set_setting(conn, "pay.methods_json", json.dumps(clean, ensure_ascii=False))
        db.set_setting(conn, "pay.tjs_rate", str(rate))
        db.set_setting(conn, "pay.min_tjs", str(minimum))
        db.set_setting(conn, "pay.low_balance_usd", str(low))
        db.set_setting(conn, "pay.rate_auto", "1" if auto else "0")
        db.set_setting(conn, "pay.rate_margin_pct", str(margin))
        if auto and not market:
            db.set_setting(conn, "pay.rate_ts", "0")  # взять курс при первом же запросе


def start_auto(conn: sqlite3.Connection, config: Config, payment_id: int) -> None:
    """Автоплатёж по способу заявки (TRC20 / Binance Pay). Не вышло — заявка отменяется и ошибка наверх."""
    from . import cryptopay
    p = conn.execute("SELECT method FROM payments WHERE id = ?", (payment_id,)).fetchone()
    method = next((m for m in settings(conn, config)["all_methods"] if m["code"] == p["method"]), {})
    if not method.get("auto"):
        return
    try:
        cryptopay.start(conn, config, payment_id, method)
    except cryptopay.CryptoPayError as exc:
        conn.execute("UPDATE payments SET status = 'cancelled', admin_note = ?, resolved_at = ? WHERE id = ?",
                     (str(exc)[:300], db.now(), payment_id))
        raise PaymentError(str(exc)) from None


def title_for(conn: sqlite3.Connection, config: Config, code: str) -> str:
    for m in settings(conn, config)["all_methods"]:
        if m["code"] == code:
            return m["title"]
    return PAY_METHODS.get(code, (code,))[0]


def methods(conn: sqlite3.Connection, config: Config) -> list[dict[str, str]]:
    conf = settings(conn, config)
    return [{"code": m["code"], "title": m["title"], "currency": m["currency"], "details": m["details"],
             "icon_url": f"{config.base_url}/pay-icons/{m['icon']}" if m.get("icon") else "",
             "auto": m.get("auto") or "",
             "network": m["network"], "network_title": NETWORKS.get(m["network"], ""),
             "network_note": network_note(m["network"])}
            for m in conf["all_methods"] if m["code"] in conf["details"]]


def pay_amount(tjs_rate: Decimal, currency: str, usd: Decimal) -> tuple[str, str]:
    if currency == "TJS":
        return str((usd * tjs_rate).quantize(Decimal("0.01"), rounding=ROUND_UP)), "TJS"
    return str(usd.quantize(Decimal("0.01"), rounding=ROUND_UP)), currency


def create(conn: sqlite3.Connection, config: Config, user: sqlite3.Row, method: str, amount: str,
           reference: str = "", *, amount_tjs: str = "") -> int:
    """Заявка на пополнение. Сумма — в долларах (amount) или в сомони (amount_tjs, пересчёт по курсу)."""
    conf = settings(conn, config)
    if method not in conf["details"]:
        raise PaymentError("Выберите способ оплаты.")
    try:
        if amount_tjs.strip():
            tjs = to_decimal(amount_tjs.replace(",", ".").strip())
            usd = (tjs / conf["tjs_rate"]).quantize(Decimal("0.0001"), rounding=ROUND_DOWN)
        else:
            usd = to_decimal(amount.replace(",", ".").replace("$", "").strip())
    except MoneyError:
        raise PaymentError("Сумма — число, например 50.") from None
    if usd * conf["tjs_rate"] < conf["min_tjs"] or usd > Decimal("100000"):
        raise PaymentError(f"Минимальная сумма пополнения — {conf['min_tjs']:f} сомони (${conf['min_usd']}).")
    open_n = conn.execute("SELECT COUNT(*) FROM payments WHERE user_id = ? AND status = 'pending'",
                          (user["id"],)).fetchone()[0]
    if open_n >= 3:
        raise PaymentError("У вас уже 3 заявки в ожидании. Дождитесь их проверки.")
    chosen = next(m for m in conf["all_methods"] if m["code"] == method)
    currency = chosen["currency"]
    pay, cur = pay_amount(conf["tjs_rate"], currency, usd)
    if chosen.get("auto") in ("trc20", "bybit"):
        from .cryptopay import CryptoPayError, unique_amount
        try:
            pay, cur = str(unique_amount(conn, usd)), "USDT"  # по «хвосту» суммы узнаём перевод в блокчейне
        except CryptoPayError as exc:
            raise PaymentError(str(exc)) from None
    if amount_tjs.strip() and currency == "TJS":
        # Сумму назвали в сомони — ровно её и переводят, без копейки от пересчёта туда-обратно
        pay = str(to_decimal(amount_tjs.replace(",", ".").strip()).quantize(Decimal("0.01")))
    c = conn.execute(
        "INSERT INTO payments (user_id, method, amount_micro, pay_amount, pay_currency, reference, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user["id"], method, to_micro(usd), pay, cur, reference.strip()[:200] or None, db.now()),
    )
    return int(c.lastrowid)


def confirm(conn: sqlite3.Connection, config: Config, payment_id: int, admin_id: int,
            credit_usd: str | None = None) -> bool:
    """Подтвердить поступление и зачислить баланс. Ровно один раз."""
    with db.tx(conn):
        p = conn.execute("SELECT * FROM payments WHERE id = ? AND status = 'pending'", (payment_id,)).fetchone()
        if p is None:
            return False
        micro = p["amount_micro"]
        if credit_usd:
            try:
                micro = to_micro(credit_usd.replace(",", "."))
            except MoneyError:
                raise PaymentError("Сумма зачисления — число.") from None
            if micro <= 0:
                raise PaymentError("Сумма зачисления должна быть больше нуля.")
        title = title_for(conn, config, p["method"])
        tx_id = accounts.post_ledger(conn, p["user_id"], micro, f"Пополнение: {title}, заявка #{p['id']}",
                                     created_by=admin_id)
        conn.execute("UPDATE payments SET status = 'paid', amount_micro = ?, tx_id = ?, resolved_at = ?, "
                     "resolved_by = ? WHERE id = ?", (micro, tx_id, db.now(), admin_id, payment_id))
        notify(conn, config, p["user_id"], f"Баланс пополнен на ${fmt(micro)} ({title}).", "/panel/transactions")
    return True


def reject(conn: sqlite3.Connection, config: Config, payment_id: int, admin_id: int, reason: str) -> bool:
    p = conn.execute("SELECT * FROM payments WHERE id = ? AND status = 'pending'", (payment_id,)).fetchone()
    if p is None:
        return False
    conn.execute("UPDATE payments SET status = 'rejected', admin_note = ?, resolved_at = ?, resolved_by = ? "
                 "WHERE id = ?", (reason.strip()[:300] or None, db.now(), admin_id, payment_id))
    notify(conn, config, p["user_id"],
           f"Заявка на пополнение #{payment_id} отклонена" + (f": {reason.strip()}" if reason.strip() else "."),
           "/panel/balance")
    return True


def cancel(conn: sqlite3.Connection, user_id: int, payment_id: int) -> None:
    conn.execute("UPDATE payments SET status = 'cancelled', resolved_at = ? "
                 "WHERE id = ? AND user_id = ? AND status = 'pending'", (db.now(), payment_id, user_id))


# ── Чек об оплате ─────────────────────────────────────────────

RECEIPT_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "application/pdf": "pdf"}
MAX_RECEIPT_BYTES = 10 * 1024 * 1024


ICON_NAME_RE = re.compile(r"[a-f0-9]{12}\.(png|jpg|webp)")
ICON_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
MAX_ICON_BYTES = 1024 * 1024


def icons_dir(config: Config):
    from pathlib import Path
    folder = Path(config.db_path).parent / "pay_icons"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_icon(config: Config, data: bytes, content_type: str) -> str:
    """Иконка способа оплаты (логотип банка, USDT): PNG/JPG/WebP до 1 МБ. Возвращает имя файла."""
    # Тип — по содержимому файла: заявленному типу (из формы или Telegram) верить нельзя
    ext = next((e for e in ("png", "jpg", "webp") if _looks_like(data, e)), None)
    if ext is None:
        raise PaymentError("Иконка — картинка PNG, JPG или WebP.")
    if len(data) > MAX_ICON_BYTES:
        raise PaymentError("Иконка больше 1 МБ — возьмите поменьше (хватит 200×200).")
    name = f"{secrets.token_hex(6)}.{ext}"
    (icons_dir(config) / name).write_bytes(data)
    return name


def _looks_like(data: bytes, ext: str) -> bool:
    if ext == "png":
        return data.startswith(b"\x89PNG")
    if ext == "jpg":
        return data.startswith(b"\xff\xd8")
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def receipts_dir(config: Config):
    from pathlib import Path
    return Path(config.db_path).parent / "receipts"


def attach_receipt(conn: sqlite3.Connection, config: Config, user_id: int, payment_id: int,
                   data: bytes, content_type: str) -> str:
    """Сохранить чек к своей заявке в ожидании. Возвращает имя файла."""
    p = conn.execute("SELECT * FROM payments WHERE id = ? AND user_id = ?", (payment_id, user_id)).fetchone()
    if p is None:
        raise PaymentError("Заявка не найдена.")
    if p["status"] != "pending":
        raise PaymentError("Заявка уже обработана.")
    ext = RECEIPT_TYPES.get((content_type or "").split(";")[0].strip().lower())
    if ext is None:
        ext = _sniff(data)
    if ext is None:
        raise PaymentError("Чек — фото (JPG, PNG, WEBP) или PDF.")
    if not data or len(data) > MAX_RECEIPT_BYTES:
        raise PaymentError("Файл чека пустой или больше 10 МБ.")
    folder = receipts_dir(config)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{payment_id}-{secrets.token_hex(6)}.{ext}"
    (folder / name).write_bytes(data)
    conn.execute("UPDATE payments SET receipt_file = ? WHERE id = ?", (name, payment_id))
    return name


def _sniff(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data.startswith(b"%PDF"):
        return "pdf"
    return None


def public(conn: sqlite3.Connection, config: Config, p: sqlite3.Row) -> dict[str, Any]:
    """Заявка для API: без внутренних полей."""
    conf = settings(conn, config)
    details = conf["details"].get(p["method"], "")
    network = next((m["network"] for m in conf["all_methods"] if m["code"] == p["method"]), "")
    return {
        "id": p["id"], "status": p["status"], "method": p["method"],
        "method_title": title_for(conn, config, p["method"]),
        "amount_usd": fmt(p["amount_micro"]), "pay_amount": p["pay_amount"], "pay_currency": p["pay_currency"],
        "details": details if p["status"] == "pending" else "", "receipt": bool(p["receipt_file"]),
        "network": network, "network_note": network_note(network) if p["status"] == "pending" else "",
        "note": p["admin_note"] or "", "created_at": p["created_at"], "resolved_at": p["resolved_at"],
        "auto": p["auto_kind"] or "", "pay_url": (p["pay_url"] or "") if p["status"] == "pending" else "",
        "address": (p["pay_address"] or "") if p["status"] == "pending" else "",
        "auto_note": ("Переведите ровно эту сумму USDT (TRC20) — баланс пополнится сам за 1–3 минуты, чек не нужен."
                      if p["auto_kind"] == "trc20" else
                      "Переведите в Bybit ровно эту сумму USDT по UID (Активы → Перевод → по UID) — "
                      "баланс пополнится сам за 1–3 минуты, чек не нужен."
                      if p["auto_kind"] == "bybit" else
                      "Оплатите по ссылке в Binance — баланс пополнится сам, чек не нужен."
                      if p["auto_kind"] == "binance" else ""),
    }

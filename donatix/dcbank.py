"""Автоплатёж «Душанбе Сити»: перевод на карту, подтверждение по уведомлению банка — без чека и без админа.

Как устроено:
  1. Клиент выбирает способ с автозачислением «dcbank» и сумму в сомони. К сумме добавляются уникальные
     копейки (100 → 100.03): по ним перевод узнаётся одной цифрой. Копейки не случайные, а первые свободные
     среди живых заявок, иначе у двоих совпала бы сумма.
  2. Кнопка «Оплатить в Душанбе Сити» открывает приложение с уже подставленными счётом и суммой.
  3. Банковский бот присылает уведомление «Zachislenie …» в Telegram владельца; юзербот (bankbot.py)
     передаёт текст сюда, в handle().
  4. handle(): СНАЧАЛА запись уведомления (уникальный индекс — повтор не пройдёт), потом разбор, потом
     поиск заявки ровно на эту сумму. Одна — зачисляем той же функцией, что и кнопка админа. Несколько или
     ни одной — НЕ угадываем: решает админ.

Главное правило: при малейшем сомнении — не зачислять, а отдать админу.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import ROUND_DOWN, Decimal
from typing import Any
from urllib.parse import quote

from . import bankparse, db
from .config import Config

log = logging.getLogger(__name__)

KIND = "dcbank"
TITLE = "Автозачисление: Душанбе Сити (уведомление банка)"
PAY_URL = "https://pay.dc.tj/"
#: Хвост: сначала 0.01–0.10, если все заняты — до 0.99
TAIL_FIRST, TAIL_LAST = 10, 99
#: Клиент мог перевести круглую сумму вместо названной — ищем заявку рядом, в пределах 0.10
NEAR = 10


def window_hours(conn: sqlite3.Connection) -> int:
    """Сколько часов заявка ждёт перевод. Старше — уведомление с ней не сравнивается."""
    try:
        return max(1, int(db.get_setting(conn, "pay.dc_window_hours") or 6))
    except ValueError:
        return 6


def receipt_after_min(conn: sqlite3.Connection) -> int:
    """Через сколько минут без совпавших денег клиенту предлагаем прислать чек."""
    try:
        return max(1, int(db.get_setting(conn, "pay.dc_receipt_min") or 5))
    except ValueError:
        return 5


def ready(config: Config) -> bool:
    """Юзербот настроен — без него заявка «dcbank» сама не подтвердится."""
    return bool(config.tg_api_id and config.tg_api_hash and config.bank_bot)


def account_of(details: str) -> str:
    """Счёт/карта для ссылки — первая цепочка из 10+ цифр в реквизитах (пробелы и дефисы не мешают)."""
    for chunk in re.findall(r"\d[\d \-]{8,}\d", details or ""):
        digits = re.sub(r"\D", "", chunk)
        if len(digits) >= 10:
            return digits
    return ""


def cents(value: Any) -> int:
    """'100.03' → 10003. Сравнение сумм — только целыми."""
    try:
        return int((Decimal(str(value)) * 100).to_integral_value(rounding=ROUND_DOWN))
    except Exception:  # noqa: BLE001
        return -1


def amount_text(diram: int) -> str:
    whole, frac = divmod(max(diram, 0), 100)
    return str(whole) if frac == 0 else f"{whole}.{frac:02d}"


def link(account: str, diram: int, comment: str, service: str = "133") -> str:
    """https://pay.dc.tj/?a=СЧЁТ&c=КОММЕНТАРИЙ&f1=УСЛУГА&s=СУММА — приложение откроется с подставленной суммой."""
    digits = re.sub(r"\D", "", account)
    return (f"{PAY_URL}?a={quote(digits)}&c={quote(comment, safe='')}"
            f"&f1={quote(str(service))}&s={quote(amount_text(diram))}")


def _since(hours: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")


def _live(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Живые заявки dcbank: в ожидании и не старше окна."""
    return conn.execute("SELECT * FROM payments WHERE auto_kind = ? AND status = 'pending' AND created_at >= ? "
                        "ORDER BY id", (KIND, _since(window_hours(conn)))).fetchall()


def unique_amount(conn: sqlite3.Connection, tjs: Decimal, codes: list[str] | tuple = ()) -> Decimal:
    """Сумма с первым свободным хвостом. Сравниваем со ВСЕМИ живыми заявками: 10.07 сталкивается
    и с базой 10.00, и с 10.06. codes — способы «Душанбе Сити»: соседняя заявка могла ещё не получить
    auto_kind (его ставят сразу после создания), но сумму она уже заняла."""
    base = cents(tjs.quantize(Decimal("0.01")))
    marks = ",".join("?" * len(codes))
    rows = conn.execute(
        "SELECT pay_amount FROM payments WHERE status = 'pending' AND created_at >= ? AND (auto_kind = ?"
        + (f" OR method IN ({marks})" if codes else "") + ")",
        (_since(window_hours(conn)), KIND, *codes)).fetchall()
    busy = {cents(r["pay_amount"]) for r in rows}
    for tail in range(1, TAIL_LAST + 1):
        if base + tail not in busy:
            return Decimal(base + tail) / 100
    from .payments import PaymentError
    raise PaymentError("Сейчас слишком много заявок на эту сумму — попробуйте через несколько минут.")


def start(conn: sqlite3.Connection, config: Config, payment_id: int, method: dict[str, Any]) -> None:
    """Сразу после создания заявки: запомнить счёт и ссылку на оплату."""
    account = account_of(method.get("details", ""))
    p = conn.execute("SELECT pay_amount FROM payments WHERE id = ?", (payment_id,)).fetchone()
    comment = (db.get_setting(conn, "pay.dc_comment") or "Donatix").strip()[:40]
    url = link(account, cents(p["pay_amount"]), f"{comment} #{payment_id}") if account else ""
    conn.execute("UPDATE payments SET auto_kind = ?, pay_address = ?, pay_url = ? WHERE id = ?",
                 (KIND, account, url, payment_id))


# ── уведомление банка ─────────────────────────────────────────


def handle(conn: sqlite3.Connection, config: Config, *, source: str, message_id: int, text: str) -> dict[str, Any]:
    """Обработать одно уведомление. Вернёт {"status": …, "payment_id": …}."""
    notice = bankparse.parse(text)
    try:
        cur = conn.execute(
            "INSERT INTO bank_notices (source, message_id, op_code, amount, sender, card_tail, bank_time, comment, "
            "seen_at, status, note, body) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'failed', ?, ?)",
            (source, message_id, notice.op_code or None, notice.amount, notice.sender[:64], notice.card_tail[:8],
             notice.bank_time[:32], notice.comment[:64], db.now(), notice.error[:190],
             bankparse.safe_body(text)))
    except sqlite3.IntegrityError:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        log.info("Уведомление %s уже обрабатывали — пропускаю", message_id)
        return {"status": "duplicate"}
    nid = int(cur.lastrowid)

    if config.bank_card and notice.card_tail and notice.card_tail != config.bank_card:
        _close(conn, nid, "other", note=f"другая карта *{notice.card_tail}")
        return {"status": "other"}

    if not notice.ok:
        _tell(config, "🚫 Уведомление банка не разобрал: " + notice.error
              + ".\nДеньги не зачислены — проверьте заявки «Душанбе Сити» руками (админка → Пополнения).")
        return {"status": "failed"}

    live = _live(conn)
    exact = [p for p in live if cents(p["pay_amount"]) == notice.amount]
    if len(exact) == 1:
        return _confirm(conn, config, nid, exact[0], notice)
    if len(exact) > 1:
        return _by_sender(conn, config, nid, exact, notice)
    near = [p for p in live if abs(cents(p["pay_amount"]) - notice.amount) <= NEAR]
    if len(near) == 1:
        return _confirm(conn, config, nid, near[0], notice)
    if len(near) > 1:
        return _by_sender(conn, config, nid, near, notice)

    _close(conn, nid, "unknown", note="заявки на эту сумму нет")
    _tell(config, "❔ Пришла оплата без заявки (Душанбе Сити)\n" + _facts(notice)
          + "\nВозможно, клиент заплатил, не создав заявку, — начислите вручную.")
    return {"status": "unknown"}


def _by_sender(conn, config, nid, waiting, notice) -> dict[str, Any]:
    """Заявок несколько: спасает только знакомый отправитель (уже платил этому клиенту). Иначе — админ."""
    if notice.sender:
        row = conn.execute("SELECT p.user_id FROM bank_notices n JOIN payments p ON p.id = n.payment_id "
                           "WHERE n.sender = ? AND n.status = 'matched' ORDER BY n.id DESC LIMIT 1",
                           (notice.sender,)).fetchone()
        if row is not None:
            his = [p for p in waiting if p["user_id"] == row["user_id"]]
            if len(his) == 1:
                return _confirm(conn, config, nid, his[0], notice)
    _close(conn, nid, "ambiguous", note=f"подходящих заявок: {len(waiting)}")
    _tell(config, "⚠️ Пришла оплата, но заявок несколько — деньги НЕ зачислены, выбирать наугад нельзя.\n"
          + _facts(notice) + "\nЗаявки: " + ", ".join(f"#{p['id']} ({p['pay_amount']} TJS)" for p in waiting[:8])
          + "\nСверьте отправителя и подтвердите нужную в админке.")
    return {"status": "ambiguous"}


def _confirm(conn, config, nid, p, notice) -> dict[str, Any]:
    """Зачислить той же функцией, что и кнопка админа. Пришло не ровно столько — зачисляем пришедшее."""
    from . import payments
    from .cryptopay import _admin_id
    from .money import fmt

    asked = cents(p["pay_amount"])
    credit = None
    if asked != notice.amount and asked > 0:
        credit = str((Decimal(p["amount_micro"]) * notice.amount / asked / 10_000).quantize(Decimal("0.0001")))
    try:
        ok = payments.confirm(conn, config, p["id"], _admin_id(conn), credit, who="автоматически · Душанбе Сити")
    except payments.PaymentError as exc:
        ok, why = False, str(exc)
    else:
        why = "заявку закрыли раньше"
    if not ok:   # закрыл админ/кассир за долю секунды до нас — второй раз не начисляем
        _close(conn, nid, "ambiguous", note=why[:190])
        _tell(config, f"⚠️ Оплата {amount_text(notice.amount)} TJS пришла, но заявка #{p['id']} уже закрыта "
                      "— повторно не зачислено. Проверьте.")
        return {"status": "ambiguous", "payment_id": p["id"]}
    conn.execute("UPDATE payments SET ext_id = COALESCE(ext_id, ?) WHERE id = ?", (notice.op_code or None, p["id"]))
    _close(conn, nid, "matched", payment_id=p["id"],
           note="сумма отличалась от заявки" if credit else "точное совпадение")
    paid = conn.execute("SELECT p.amount_micro, u.login FROM payments p JOIN users u ON u.id = p.user_id "
                        "WHERE p.id = ?", (p["id"],)).fetchone()
    _tell(config, f"💳 Оплата подтверждена автоматически: заявка #{p['id']}, клиент {paid['login']}, "
                  f"пришло {amount_text(notice.amount)} TJS"
                  + (f" (просили {p['pay_amount']})" if credit else "")
                  + f", зачислено ${fmt(paid['amount_micro'])}.\n" + _facts(notice, amount=False))
    log.info("Душанбе Сити: заявка #%s зачислена автоматически", p["id"])
    return {"status": "matched", "payment_id": p["id"]}


def _close(conn, nid: int, status: str, *, payment_id: int | None = None, note: str = "") -> None:
    conn.execute("UPDATE bank_notices SET status = ?, payment_id = ?, note = ? WHERE id = ?",
                 (status, payment_id, note[:190], nid))


def _facts(notice: bankparse.Notice, amount: bool = True) -> str:
    parts = [f"Сумма: {amount_text(notice.amount)} TJS"] if amount else []
    if notice.sender:
        parts.append(f"Отправитель: {notice.sender}")
    if notice.comment:
        parts.append(f"Приписка банка: {notice.comment}")
    if notice.op_code:
        parts.append(f"Код банка: {notice.op_code}")
    parts.append(f"Время банка: {notice.bank_time or '—'}")
    return "\n".join(parts)


def _tell(config: Config, text: str) -> None:
    try:
        from .worker import notify_admin
        notify_admin(config, text)
    except Exception as exc:  # noqa: BLE001 — письмо админу не важнее денег
        log.warning("Не смог написать админу: %s", exc)


def summary(conn: sqlite3.Connection, limit: int = 30) -> dict[str, Any]:
    """Для админки: сколько зачислено само и что требует проверки."""
    counts = {r["status"]: r["n"] for r in conn.execute(
        "SELECT status, COUNT(*) AS n FROM bank_notices GROUP BY status")}
    rows = conn.execute("SELECT * FROM bank_notices ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return {"counts": counts, "rows": rows}

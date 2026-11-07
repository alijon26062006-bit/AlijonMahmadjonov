"""Карта для возврата остатка: если проект когда-нибудь закроется, остаток баланса каждого клиента
переводится на карту (или номер телефона-кошелька), которую он сам указал.

Номер хранится зашифрованным (ключ — из DONATIX_SECRET_KEY, его нет в базе): утечка копии базы
не раскрывает номера. Полный номер видит только админ на странице «Карты для возврата».
Спрашиваем только банк, номер и имя владельца — НИКОГДА не срок действия, CVV, пароль или код из SMS.
"""

from __future__ import annotations

import base64
import hashlib
import re
import sqlite3
from typing import Any

from . import db

ENFORCE = True   # обязательное заполнение (тесты выключают); админ выключает настройкой refund.required = 0

BANKS = ("Алиф", "Душанбе Сити", "Эсхата", "Амонатбонк", "Спитамен Банк", "Арванд", "Международный банк Таджикистана",
         "Хумо", "Ориёнбонк", "Матин", "Тавхидбанк", "Коммерцбанк Таджикистана", "Имон Интернешнл", "Другой банк")
KINDS = {"card": "Номер карты", "phone": "Номер телефона (кошелёк банка)"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS refund_details (       -- куда вернуть остаток баланса, если проект закроется
    user_id     INTEGER PRIMARY KEY,
    bank        TEXT NOT NULL,
    kind        TEXT NOT NULL,                    -- card · phone
    number_enc  TEXT NOT NULL,                    -- номер, зашифрован
    last4       TEXT NOT NULL,                    -- последние 4 цифры — показать клиенту
    holder      TEXT NOT NULL,                    -- имя владельца карты
    source      TEXT NOT NULL DEFAULT 'site',     -- site · bot
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""

EXPLAIN_RU = (
    "Зачем это нужно: если {site} когда-нибудь закроется, мы вернём остаток вашего баланса на эту карту — "
    "каждому его деньги. Закрываться мы не собираемся, это на всякий случай, чтобы ваши деньги никогда не пропали.\n\n"
    "Это безопасно: по номеру карты деньги можно только отправить вам — снять с неё ничего нельзя. "
    "Мы спрашиваем только банк, номер и имя владельца. Мы НИКОГДА не спросим срок действия, CVV-код с обратной "
    "стороны, пароль или код из SMS — если кто-то просит это от имени {site}, это мошенник.\n\n"
    "Номер хранится в зашифрованном виде, его видит только администратор. Изменить карту можно в любой момент."
)
EXPLAIN_TJ = (
    "Барои чӣ: агар {site} рӯзе баста шавад, бақияи баланси шуморо ба ҳамин корт бармегардонем. "
    "Мо танҳо бонк, рақам ва номи соҳибро мепурсем — ҳеҷ гоҳ мӯҳлат, CVV, парол ё рамзи SMS-ро намепурсем."
)


def init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def _fernet(secret: str):
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(hashlib.sha256(("donatix-refund:" + secret).encode()).digest())
    return Fernet(key)


def encrypt(secret: str, number: str) -> str:
    return _fernet(secret).encrypt(number.encode()).decode()


def decrypt(secret: str, token: str) -> str | None:
    try:
        return _fernet(secret).decrypt(token.encode()).decode()
    except Exception:   # ключ сменили — номер не прочитать
        return None


def required(conn: sqlite3.Connection) -> bool:
    # По умолчанию ВЫКЛЮЧЕНО — включает админ в «Карты для возврата», когда решит
    return ENFORCE and db.get_setting(conn, "refund.required", "0") == "1"


def get(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    init(conn)
    return conn.execute("SELECT * FROM refund_details WHERE user_id = ?", (user_id,)).fetchone()


def exempt(user: Any) -> bool:
    """Кого не спрашиваем: админ и гость быстрой покупки (без аккаунта)."""
    if not user or user["role"] in ("admin", "guest"):
        return True
    from .quickbuy import is_guest
    try:
        return bool(is_guest(user))
    except Exception:
        return False


def needed(conn: sqlite3.Connection, user: Any) -> bool:
    return not exempt(user) and required(conn) and get(conn, user["id"]) is None


def clean_number(kind: str, raw: str) -> tuple[str | None, str]:
    """Номер без пробелов или (None, ошибка)."""
    digits = re.sub(r"[\s\-()+]", "", raw or "")
    if not digits.isdigit():
        return None, "Номер — только цифры."
    if kind == "card":
        if not 16 <= len(digits) <= 19:
            return None, "Номер карты — 16 цифр (как на лицевой стороне карты)."
        return digits, ""
    if digits.startswith("992"):
        digits = digits[3:]
    if len(digits) != 9:
        return None, "Номер телефона — 9 цифр после +992, например 90 123 45 67."
    return "+992" + digits, ""


def clean_holder(raw: str) -> tuple[str | None, str]:
    name = re.sub(r"\s+", " ", (raw or "").strip())
    if not 3 <= len(name) <= 80 or not re.fullmatch(r"[A-Za-zА-Яа-яЁёҒғӢӣҚқӮӯҲҳҶҷ' .\-]+", name):
        return None, "Имя владельца — буквами, как на карте или в банке, например «Алиев Алишер»."
    return name, ""


def clean_bank(raw: str) -> tuple[str | None, str]:
    bank = re.sub(r"\s+", " ", (raw or "").strip())[:60]
    if len(bank) < 2:
        return None, "Выберите банк."
    return bank, ""


def save(conn: sqlite3.Connection, secret: str, user_id: int, *, bank: str, kind: str, number: str, holder: str,
         source: str = "site") -> str:
    """Проверяет и сохраняет. Возвращает текст ошибки или пустую строку."""
    if kind not in KINDS:
        return "Выберите: номер карты или номер телефона."
    bank_c, err = clean_bank(bank)
    if bank_c is None:
        return err
    num, err = clean_number(kind, number)
    if num is None:
        return err
    name, err = clean_holder(holder)
    if name is None:
        return err
    init(conn)
    now = db.now()
    conn.execute(
        "INSERT INTO refund_details (user_id, bank, kind, number_enc, last4, holder, source, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET bank = excluded.bank, "
        "kind = excluded.kind, number_enc = excluded.number_enc, last4 = excluded.last4, holder = excluded.holder, "
        "source = excluded.source, updated_at = excluded.updated_at",
        (user_id, bank_c, kind, encrypt(secret, num), num[-4:], name, source, now, now))
    return ""


def masked(row: Any) -> str:
    if row is None:
        return ""
    return ("Карта •••• " if row["kind"] == "card" else "Телефон •••• ") + row["last4"]


def report(conn: sqlite3.Connection, secret: str, only_balance: bool = False) -> list[dict[str, Any]]:
    """Для админа: все клиенты с остатком и куда его вернуть (полный номер)."""
    init(conn)
    where = "u.role != 'admin'" + (" AND u.balance_micro > 0" if only_balance else "")
    rows = []
    for r in conn.execute(
            "SELECT u.id, u.login, u.email, u.balance_micro, r.bank, r.kind, r.number_enc, r.last4, r.holder, "
            f"r.updated_at FROM users u LEFT JOIN refund_details r ON r.user_id = u.id WHERE {where} "
            "ORDER BY (r.user_id IS NULL), u.balance_micro DESC, u.id").fetchall():
        d = dict(r)
        d["number"] = decrypt(secret, r["number_enc"]) if r["number_enc"] else None
        d.pop("number_enc")
        rows.append(d)
    return rows

"""Настройки сайта, которые админ меняет сам — в веб-админке или в админ-боте.

Хранятся в базе и накладываются поверх .env на общий объект Config: наценки,
контакт поддержки, приём новых клиентов, конструктор ботов для клиентов.
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal, InvalidOperation
from typing import Any

from . import cache, db
from .config import TIERS, Config

KIND_KEYS = ("steam_topup", "steam_gift")
KIND_TITLES = {"steam_topup": "Пополнение Steam", "steam_gift": "Steam Гифты"}
TIER_TITLES = {"bronze": "Bronze (по умолчанию)", "silver": "Silver", "gold": "Gold"}


class SettingsError(ValueError):
    pass


def _flag(conn: sqlite3.Connection, key: str, default: bool) -> bool:
    value = db.get_setting(conn, key)
    return default if value in (None, "") else value == "1"


def registration_open(conn: sqlite3.Connection) -> bool:
    return _flag(conn, "site.reg_open", True)


def client_bots_enabled(conn: sqlite3.Connection) -> bool:
    return _flag(conn, "site.client_bots", True)


def max_bots(conn: sqlite3.Connection) -> int:
    try:
        return max(0, int(db.get_setting(conn, "site.max_bots") or 3))
    except ValueError:
        return 3


def load(conn: sqlite3.Connection, config: Config) -> None:
    """Наложить сохранённое на config (при старте и после каждого изменения)."""
    for tier in TIERS:
        value = db.get_setting(conn, f"markup.{tier}")
        if value:
            config.markups[tier] = Decimal(value)
    for kind in KIND_KEYS:
        value = db.get_setting(conn, f"markup.{kind}")
        if value == "-":
            config.kind_markups.pop(kind, None)
        elif value:
            config.kind_markups[kind] = Decimal(value)
    support = db.get_setting(conn, "site.support")
    if support is not None:
        config.support_contact = support
    approval = db.get_setting(conn, "site.require_approval")
    if approval in ("0", "1"):
        config.require_approval = approval == "1"


def view(conn: sqlite3.Connection, config: Config) -> dict[str, Any]:
    return {
        "markups": {t: config.markups.get(t) for t in TIERS},
        "kind_markups": {k: config.kind_markups.get(k) for k in KIND_KEYS},
        "support": config.support_contact,
        "require_approval": config.require_approval,
        "reg_open": registration_open(conn),
        "client_bots": client_bots_enabled(conn),
        "max_bots": max_bots(conn),
    }


def _pct(raw: str, what: str, allow_empty: bool = False) -> str:
    raw = (raw or "").replace(",", ".").replace("%", "").strip()
    if not raw and allow_empty:
        return "-"
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise SettingsError(f"{what}: нужно число, например 8.") from None
    if not Decimal("0") <= value <= Decimal("100"):
        raise SettingsError(f"{what}: от 0 до 100 %.")
    return str(int(value)) if value == value.to_integral() else str(value)


def save(conn: sqlite3.Connection, config: Config, data: dict[str, Any]) -> None:
    values: dict[str, str] = {}
    for tier in TIERS:
        if f"markup_{tier}" in data:
            values[f"markup.{tier}"] = _pct(data[f"markup_{tier}"], f"Наценка {tier}")
    for kind in KIND_KEYS:
        if f"markup_{kind}" in data:
            values[f"markup.{kind}"] = _pct(data[f"markup_{kind}"], KIND_TITLES[kind], allow_empty=True)
    if "support" in data:
        values["site.support"] = str(data["support"]).strip()[:100]
    for key in ("reg_open", "client_bots", "require_approval"):
        if key in data:
            values[f"site.{key}"] = "1" if data[key] in (True, "1", "on") else "0"
    if "max_bots" in data:
        try:
            n = int(str(data["max_bots"]).strip())
        except ValueError:
            raise SettingsError("Лимит ботов — целое число.") from None
        if not 0 <= n <= 50:
            raise SettingsError("Лимит ботов — от 0 до 50.")
        values["site.max_bots"] = str(n)
    with db.tx(conn):
        for key, value in values.items():
            db.set_setting(conn, key, value)
    load(conn, config)
    cache.clear()


def toggle(conn: sqlite3.Connection, config: Config, key: str) -> bool:
    current = view(conn, config)[key]
    save(conn, config, {key: "0" if current else "1"})
    return not current


def bump_markup(conn: sqlite3.Connection, config: Config, tier: str, delta: Decimal) -> Decimal:
    value = max(Decimal("0"), min(Decimal("100"), config.markups[tier] + delta))
    save(conn, config, {f"markup_{tier}": str(value)})
    return config.markups[tier]

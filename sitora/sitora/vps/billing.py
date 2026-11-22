"""Биллинг VPS (раз в 10 минут).

- Продление раз в 30 дней с баланса Sitora по цене, зафиксированной при заказе.
- За 3 дня до продления — сообщение в Telegram, если денег не хватает.
- Не хватило: через 3 дня сервер выключается, на 11-й день — предупреждение,
  через 14 дней — удаление у Hetzner. Пополнил — продлеваем и включаем обратно.
"""
from __future__ import annotations

import asyncio
import logging

from .. import db, shop
from ..money import fmt
from . import live, service
from .hetzner import HetznerError
from .store import Vps, now as _now

log = logging.getLogger(__name__)

DAY = 86400
WARN_BEFORE = 3 * DAY
OFF_AFTER = 3 * DAY
DELETE_AFTER = 14 * DAY
DELETE_WARN = DELETE_AFTER - 3 * DAY
EVERY = 600


async def run_once(v: Vps, now: int | None = None) -> dict:
    now = _now() if now is None else now
    report = {"renewed": 0, "warned": 0, "suspended": 0, "deleted": 0, "resumed": 0}
    conn = v.conn()
    rows = conn.execute("SELECT s.*, u.balance AS balance FROM vps_servers s JOIN users u ON u.id = s.user_id "
                        "WHERE s.state IN ('active', 'suspended')").fetchall()
    conn.close()
    for s in rows:
        try:
            await _one(v, s, now, report)
        except Exception:  # noqa: BLE001 — один сервер не останавливает остальные
            log.exception("VPS-биллинг сервера %s", s["id"])
    conn = v.conn()
    live.cleanup(conn)
    conn.close()
    return report


def _set(v: Vps, sid: int, sql: str, *args) -> None:
    conn = v.conn()
    conn.execute(f"UPDATE vps_servers SET {sql} WHERE id = ?", (*args, sid))
    conn.close()


async def _one(v: Vps, s, now: int, report: dict) -> None:
    sid, uid, price, name = s["id"], s["user_id"], s["price"], s["name"]
    if now < s["paid_until"]:
        if s["paid_until"] - now <= WARN_BEFORE and s["balance"] < price and not s["warned_low"]:
            _set(v, sid, "warned_low = 1")
            await v.tell(uid, f"🖥 Сервер {name}: через 3 дня продление — нужно {fmt(price)} с., на балансе "
                              f"{fmt(s['balance'])} с. Пополните баланс, чтобы сервер не выключился.\n"
                              f"Сервер {name}: баъди 3 рӯз {fmt(price)} с. лозим аст — балансро пур кунед.")
            report["warned"] += 1
        return

    conn = v.conn()
    try:
        with db.tx(conn):
            try:
                shop.move(conn, uid, -price, "vps_renew", f"vps:{sid}")
                conn.execute("UPDATE vps_servers SET paid_until = paid_until + ?, unpaid_since = NULL, warned_low = 0, "
                             "warned_delete = 0 WHERE id = ?", (service.PERIOD, sid))
                ok = True
            except shop.ShopError:
                ok = False
        if not ok and s["unpaid_since"] is None:
            conn.execute("UPDATE vps_servers SET unpaid_since = ? WHERE id = ?", (s["paid_until"], sid))
    finally:
        conn.close()
    if ok:
        report["renewed"] += 1
        if s["state"] == "suspended":
            await _power(v, s, "poweron")
            _set(v, sid, "state = 'active'")
            report["resumed"] += 1
            await v.tell(uid, f"✅ Сервер {name} снова включён — оплата прошла.\nСервер {name} боз фаъол аст.")
        return

    overdue = now - (s["unpaid_since"] or s["paid_until"])
    if overdue >= DELETE_AFTER:
        await service.delete(v, None, sid, reason="неуплата 14 дней")
        report["deleted"] += 1
        await v.tell(uid, f"🗑 Сервер {name} удалён: он не был оплачен 14 дней.\nСервер {name} нест карда шуд.")
        await v.tell_admins(f"🗑 VPS #{sid} (клиент {uid}) удалён за неуплату.")
    elif overdue >= DELETE_WARN and not s["warned_delete"]:
        _set(v, sid, "warned_delete = 1")
        await v.tell(uid, f"⚠️ Сервер {name} удалится через 3 дня вместе с данными. Пополните баланс на "
                          f"{fmt(price)} с.\nСервер {name} баъди 3 рӯз нест мешавад — балансро пур кунед.")
        report["warned"] += 1
    elif overdue >= OFF_AFTER and s["state"] == "active":
        await _power(v, s, "poweroff")
        _set(v, sid, "state = 'suspended'")
        report["suspended"] += 1
        await v.tell(uid, f"⏸ Сервер {name} выключен за неуплату. Пополните баланс на {fmt(price)} с. — он "
                          f"включится сам. Через 14 дней без оплаты сервер удаляется.\n"
                          f"Сервер {name} барои пардохт нашудан хомӯш шуд.")


async def _power(v: Vps, s, act: str) -> None:
    if not s["hetzner_id"]:
        return
    try:
        await v.hz().post(f"/servers/{s['hetzner_id']}/actions/{act}")
    except HetznerError as exc:
        log.warning("VPS %s: %s не прошло: %s", s["id"], act, exc.code)


async def loop(v: Vps) -> None:
    while True:
        try:
            await run_once(v)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            log.exception("VPS-биллинг: непредвиденная ошибка")
        await asyncio.sleep(EVERY)

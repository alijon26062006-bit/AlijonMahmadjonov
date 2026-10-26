"""Обунаи моҳонаи конструктор.

Шарик барои ҳар бот ҳар моҳ пардохт мекунад (нарх дар панели соҳиб иваз
мешавад, аз рӯи нобаёнӣ 50 сомонӣ). То мӯҳлат пардохт шудааст — бот кор
мекунад; мӯҳлат гузашт — бот хомӯш мешавад («обуна тамом шуд») ва пас аз
пардохт боз кор мекунад. Шарик метавонад пардохти худкорро фаъол кунад:
он гоҳ обуна аз ҳисобаш худкор дароз мешавад.

Ботҳои худи соҳиби платформа (админҳо) бепуланд.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from .db import Database, NotEnoughMoney

log = logging.getLogger(__name__)

PRICE_KEY = "constructor_sub_price"
DEFAULT_PRICE = 5000                 # 50 сомонӣ
PERIOD_DAYS = 30
GRACE_DAYS = 3                       # ботҳои пеш аз обуна — 3 рӯз барои пардохт
WARN_DAYS = (3, 1)                   # огоҳӣ пеш аз тамом шудан
MIGRATED_KEY = "constructor_billing_v1"


def price(db: Database) -> int:
    try:
        value = int(db.setting(PRICE_KEY) or DEFAULT_PRICE)
    except ValueError:
        return DEFAULT_PRICE
    return max(0, value)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def paid_until(row) -> datetime | None:
    raw = row["paid_until"] if "paid_until" in row.keys() else None
    if not raw:
        return None
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)


def is_exempt(admin_ids, row) -> bool:
    """Боти соҳиби платформа обуна намехоҳад."""
    return row["owner_id"] in tuple(admin_ids)


def is_paid(row, at: datetime | None = None) -> bool:
    until = paid_until(row)
    return until is not None and until > (at or _now())


def days_left(row, at: datetime | None = None) -> float:
    until = paid_until(row)
    if until is None:
        return 0.0
    return (until - (at or _now())).total_seconds() / 86400


def migrate(db: Database) -> None:
    """Як бор: наценкаи яклухт 0% ва 3 рӯзи ройгон ба ботҳои пеш аз обуна."""
    from . import wholesale

    if db.setting(MIGRATED_KEY) == "1":
        return
    db.set_setting(wholesale.WHOLESALE_MARKUP_KEY, "0")
    grace = (_now() + timedelta(days=GRACE_DAYS)).isoformat(timespec="seconds")
    for row in db.tenants():
        if not row["paid_until"]:
            db.set_tenant(row["id"], paid_until=grace)
    db.set_setting(MIGRATED_KEY, "1")


TRIAL_KEY = "constructor_trial_days"
DEFAULT_TRIAL_DAYS = 3


def trial_days(db: Database) -> int:
    try:
        return max(0, min(int(db.setting(TRIAL_KEY) or DEFAULT_TRIAL_DAYS), 365))
    except ValueError:
        return DEFAULT_TRIAL_DAYS


def trial_available(db: Database, user_id: int) -> bool:
    """Озмоиши ройгон — як бор барои ҳар шарик (нест кардан ва аз нав пайваст кардан намедиҳад)."""
    return trial_days(db) > 0 and db.setting(f"trial_used:{user_id}") != "1"


def start_trial(db: Database, row) -> str:
    """Рӯзҳои ройгон барои боти нав. Огоҳии «3 рӯз монд» фавран намеояд — танҳо 1 рӯз пеш."""
    until = db.pay_subscription(row["id"], 0, trial_days(db), reason="trial")
    db.set_setting(f"trial_used:{row['owner_id']}", "1")
    db.set_tenant(row["id"], sub_notice=f"{until}:{max(WARN_DAYS)}")
    return until


def charge(db: Database, row) -> str:
    """Як моҳ аз ҳисоби шарик. Пул нарасад — ``NotEnoughMoney``."""
    return db.pay_subscription(row["id"], price(db), PERIOD_DAYS)


async def check_all(manager) -> dict[str, int]:
    """Ҳар чанд дақиқа: дароз кардани худкор, огоҳӣ ва хомӯш кардани ботҳои бе пардохт."""
    from .i18n import texts

    db = manager.platform.db
    admins = manager.platform.cfg.admin_ids
    counts: dict[str, int] = {}
    now = _now()

    def bump(key: str) -> None:
        counts[key] = counts.get(key, 0) + 1

    for row in db.tenants():
        if row["status"] not in ("active", "paused") or is_exempt(admins, row):
            continue
        name = row["username"] or str(row["bot_id"])
        cost = price(db)
        if not is_paid(row, now):
            if row["auto_renew"]:
                try:
                    until = charge(db, row)
                except NotEnoughMoney:
                    pass
                else:
                    bump("renewed")
                    await manager.tell(row["owner_id"], texts.sub_renewed(name, cost, until))
                    continue
            db.set_tenant(row["id"], status="expired")
            await manager.stop(row["id"])
            bump("expired")
            await manager.tell(row["owner_id"], texts.sub_expired(name, cost))
            continue

        # Огоҳӣ: як бор 3 рӯз пеш ва як бор 1 рӯз пеш.
        due = [limit for limit in WARN_DAYS if days_left(row, now) <= limit]
        mark = f"{row['paid_until']}:{min(due)}" if due else None
        if mark and row["sub_notice"] != mark:
            db.set_tenant(row["id"], sub_notice=mark)
            user = db.user(row["owner_id"])
            await manager.tell(row["owner_id"], texts.sub_reminder(
                name, paid_until(row), cost, bool(row["auto_renew"]), user.balance if user else 0,
            ))
            bump("warned")
    if counts:
        log.info("Обунаи конструктор: %s", counts)
    return counts

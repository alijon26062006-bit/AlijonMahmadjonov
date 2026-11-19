from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from .config import get_settings
from .models import Setting

MARKUP_KEY = "markup_percent"
SALES_KEY = "sales_enabled"
MAX_ORDER_KEY = "max_order_usd"
DAILY_KEY = "daily_user_usd"


def _get(db: Session, key: str) -> str | None:
    row = db.get(Setting, key)
    return row.value if row is not None else None


def _set(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row is None:
        db.add(Setting(key=key, value=value))
    else:
        row.value = value
    db.commit()


def _dec(db: Session, key: str, default: Decimal) -> Decimal:
    raw = _get(db, key)
    try:
        return Decimal(raw) if raw is not None else default
    except InvalidOperation:
        return default


def get_markup(db: Session) -> Decimal:
    return _dec(db, MARKUP_KEY, get_settings().default_markup_percent)


def set_markup(db: Session, value: Decimal) -> None:
    _set(db, MARKUP_KEY, str(value))


def sales_enabled(db: Session) -> bool:
    return _get(db, SALES_KEY) != "0"


def set_sales_enabled(db: Session, on: bool) -> None:
    _set(db, SALES_KEY, "1" if on else "0")


def get_limits(db: Session) -> dict[str, Decimal]:
    s = get_settings()
    return {"max_order_usd": _dec(db, MAX_ORDER_KEY, s.default_max_order_usd),
            "daily_user_usd": _dec(db, DAILY_KEY, s.default_daily_user_usd)}


def set_limits(db: Session, max_order_usd: Decimal, daily_user_usd: Decimal) -> None:
    _set(db, MAX_ORDER_KEY, str(max_order_usd))
    _set(db, DAILY_KEY, str(daily_user_usd))

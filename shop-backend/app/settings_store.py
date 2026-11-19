from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from .config import get_settings
from .models import Setting

MARKUP_KEY = "markup_percent"


def get_markup(db: Session) -> Decimal:
    row = db.get(Setting, MARKUP_KEY)
    if row is not None:
        try:
            return Decimal(row.value)
        except InvalidOperation:
            pass
    return get_settings().default_markup_percent


def set_markup(db: Session, value: Decimal) -> None:
    row = db.get(Setting, MARKUP_KEY)
    if row is None:
        db.add(Setting(key=MARKUP_KEY, value=str(value)))
    else:
        row.value = str(value)
    db.commit()

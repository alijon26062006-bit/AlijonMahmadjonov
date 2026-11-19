"""All balance changes go through here, inside the caller's DB transaction.

The user row is locked (SELECT … FOR UPDATE) so two requests can't spend the same money twice.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import LedgerEntry, User
from .money import q4


class InsufficientFunds(Exception):
    pass


def lock_user(db: Session, user_id: int) -> User:
    # populate_existing: re-read the row even if this session already loaded the user earlier,
    # otherwise a stale balance from memory would be used (double-spend bug).
    return db.execute(select(User).where(User.id == user_id).with_for_update()
                      .execution_options(populate_existing=True)).scalar_one()


def credit(db: Session, user: User, amount: Decimal, reason: str, ref: str | None = None,
           note: str | None = None) -> LedgerEntry:
    amount = q4(amount)
    if amount <= 0:
        raise ValueError("amount must be positive")
    user.balance = q4(user.balance + amount)
    e = LedgerEntry(user_id=user.id, kind="credit", reason=reason, amount=amount,
                    balance_after=user.balance, ref=ref, note=note)
    db.add(e)
    return e


def debit(db: Session, user: User, amount: Decimal, reason: str, ref: str | None = None,
          note: str | None = None) -> LedgerEntry:
    amount = q4(amount)
    if amount <= 0:
        raise ValueError("amount must be positive")
    if user.balance < amount:
        raise InsufficientFunds()
    user.balance = q4(user.balance - amount)
    e = LedgerEntry(user_id=user.id, kind="debit", reason=reason, amount=amount,
                    balance_after=user.balance, ref=ref, note=note)
    db.add(e)
    return e

"""Ҳолатҳои гуфтугӯ (FSM)."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class Buy(StatesGroup):
    waiting_target = State()   # @username ё ID-и бозигар
    confirming = State()       # тасдиқи ниҳоӣ


class Topup(StatesGroup):
    waiting_amount = State()   # маблағи дилхоҳ
    waiting_receipt = State()  # интизори чек/скриншот


class Admin(StatesGroup):
    waiting_user = State()
    waiting_plus = State()
    waiting_minus = State()
    waiting_price = State()
    waiting_broadcast = State()

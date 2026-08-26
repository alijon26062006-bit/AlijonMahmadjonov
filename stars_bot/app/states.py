"""FSM-состояния оформления заказа."""
from aiogram.fsm.state import State, StatesGroup


class Purchase(StatesGroup):
    recipient = State()   # ждём @username получателя
    confirm = State()     # показали сводку, ждём подтверждения
    receipt = State()     # заказ создан, ждём скриншот чека

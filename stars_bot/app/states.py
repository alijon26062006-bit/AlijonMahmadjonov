"""FSM-состояния диалогов."""
from aiogram.fsm.state import State, StatesGroup


class Buy(StatesGroup):
    quantity = State()    # ждём количество звёзд
    recipient = State()   # ждём @username получателя
    confirm = State()     # показали сводку, ждём подтверждения


class Deposit(StatesGroup):
    amount = State()      # ждём сумму пополнения
    receipt = State()     # ждём скриншот чека


class Promo(StatesGroup):
    code = State()


class Calc(StatesGroup):
    query = State()


class Support(StatesGroup):
    subject = State()     # первое сообщение тикета
    reply = State()       # дописка в открытый тикет


class Panel(StatesGroup):
    value = State()       # ждём новое значение настройки


class Cast(StatesGroup):
    content = State()     # ждём сообщение для рассылки
    buttons = State()     # ждём список кнопок
    confirm = State()     # готово к отправке


class PromoNew(StatesGroup):
    data = State()        # ждём «КОД сумма лимит»

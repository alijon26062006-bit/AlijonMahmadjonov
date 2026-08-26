"""FSM-состояния диалогов."""
from aiogram.fsm.state import State, StatesGroup


class Buy(StatesGroup):
    quantity = State()          # ждём количество звёзд
    recipient = State()         # ждём @username получателя
    check_recipient = State()   # показали имя аккаунта, ждём «да, это он»
    confirm = State()           # показали сводку, ждём подтверждения
    promo = State()             # ждём промокод на скидку


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
    emoji = State()       # ждём новый значок
    period = State()      # ждём даты для отчёта
    user_search = State() # ждём ID или юзернейм клиента
    adjust = State()      # ждём сумму правки баланса
    link = State()        # ждём название рекламной ссылки


class Cast(StatesGroup):
    content = State()     # ждём сообщение для рассылки
    buttons = State()     # ждём список кнопок
    confirm = State()     # готово к отправке


class PromoNew(StatesGroup):
    data = State()        # ждём «КОД сумма лимит» (старый однострочный ввод)
    # Пошаговое создание промокода на скидку
    code = State()        # ждём сам код
    percent = State()     # ждём процент скидки
    limit = State()       # ждём число активаций
    confirm = State()     # показали сводку, ждём «Сохранить»

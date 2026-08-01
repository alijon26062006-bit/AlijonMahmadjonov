from aiogram.fsm.state import State, StatesGroup


class CrudStates(StatesGroup):
    """Универсальные состояния CRUD-конструктора админ-панели."""
    add_value = State()   # пошаговый ввод полей при создании
    edit_value = State()  # ввод нового значения поля


class AdminStates(StatesGroup):
    broadcast_text = State()
    broadcast_confirm = State()
    track_number = State()
    track_user = State()
    order_search = State()
    track_search = State()

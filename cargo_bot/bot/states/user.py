from aiogram.fsm.state import State, StatesGroup


class CalcStates(StatesGroup):
    delivery_type = State()
    category = State()
    weight = State()
    volume = State()


class OrderStates(StatesGroup):
    name = State()
    phone = State()
    product_url = State()
    description = State()
    weight = State()
    volume = State()
    comment = State()


class TrackStates(StatesGroup):
    number = State()

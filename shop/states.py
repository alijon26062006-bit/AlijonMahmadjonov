"""Ҳолатҳои гуфтугӯ (FSM)."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class Buy(StatesGroup):
    waiting_target = State()   # @username ё ID-и бозигар
    confirming = State()       # тасдиқи ниҳоӣ


class Topup(StatesGroup):
    waiting_amount = State()   # маблағи дилхоҳ
    waiting_receipt = State()  # интизори чек/скриншот


class Review(StatesGroup):
    waiting_text = State()


class Admin(StatesGroup):
    waiting_user = State()
    waiting_plus = State()
    waiting_minus = State()
    waiting_price = State()
    waiting_broadcast = State()
    waiting_partner = State()
    waiting_partner_price = State()
    waiting_channel = State()
    waiting_review_channel = State()
    waiting_whatsapp = State()
    waiting_group_title = State()
    waiting_card = State()
    waiting_holder = State()
    waiting_alif = State()
    waiting_rate = State()
    waiting_markup = State()
    waiting_api_markup = State()
    # конструктор (соҳиб)
    waiting_access = State()
    waiting_c_markup = State()
    waiting_max_bots = State()
    waiting_sub_price = State()
    # боти шарик
    waiting_partner_markup = State()
    waiting_operator = State()
    waiting_support = State()
    waiting_product_title = State()
    waiting_low_balance = State()
    waiting_bc_media = State()
    waiting_bc_text = State()
    waiting_bc_button = State()


class Constructor(StatesGroup):
    waiting_token = State()       # боти нав
    waiting_new_token = State()   # токени нав барои боти мавҷуда

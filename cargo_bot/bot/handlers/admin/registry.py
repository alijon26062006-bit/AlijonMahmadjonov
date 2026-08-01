"""Реестр сущностей админ-панели.

Каждая сущность описывается декларативно: модель + список полей.
Универсальный CRUD-движок (crud.py) по этому описанию строит списки,
карточки, добавление, редактирование, удаление и вкл/выкл — поэтому
новые управляемые справочники добавляются парой строк.
"""
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable

from bot.models import (
    Admin, Category, Coefficient, Contact, Currency, DeliveryType, ExchangeRate,
    ExtraService, Faq, Setting, Tariff, Warehouse,
)


@dataclass
class Field:
    name: str
    label: str
    ftype: str = "str"  # str | text | int | dec | bool | fk | choice | currency
    required: bool = True
    fk: str | None = None  # ключ сущности для fk-выбора
    choices: list[tuple[str, str]] = dc_field(default_factory=list)  # (значение, подпись)
    hint: str = ""


@dataclass
class Entity:
    key: str
    title: str
    title_one: str
    model: type
    fields: list[Field]
    order_by: list[Any] = dc_field(default_factory=list)
    row: Callable[[Any], str] = str
    can_add: bool = True
    can_delete: bool = True
    per_page: int = 8

    @property
    def has_active(self) -> bool:
        return "is_active" in self.model.__table__.columns


ENTITIES: dict[str, Entity] = {}


def _reg(entity: Entity) -> None:
    ENTITIES[entity.key] = entity


_reg(Entity(
    key="trf", title="💰 Тарифы", title_one="Тариф", model=Tariff,
    order_by=[Tariff.delivery_type_id, Tariff.id],
    fields=[
        Field("name", "Название"),
        Field("delivery_type_id", "Тип доставки", ftype="fk", fk="dtp"),
        Field("category_id", "Категория товара", ftype="fk", fk="cat", required=False,
              hint="Пропустить = общий тариф для всех категорий"),
        Field("price_per_kg", "Стоимость за 1 кг", ftype="dec"),
        Field("min_order_cost", "Минимальная стоимость заказа", ftype="dec"),
        Field("min_weight", "Минимальный оплачиваемый вес, кг", ftype="dec"),
        Field("currency_code", "Валюта расчёта", ftype="currency"),
        Field("delivery_time", "Срок доставки", required=False, hint="Например: 7–12 дней"),
    ],
))

_reg(Entity(
    key="dtp", title="🚚 Типы доставки", title_one="Тип доставки", model=DeliveryType,
    order_by=[DeliveryType.sort_order],
    fields=[
        Field("name", "Название"),
        Field("emoji", "Эмодзи", required=False),
        Field("sort_order", "Порядок сортировки", ftype="int"),
    ],
))

_reg(Entity(
    key="cat", title="🗂 Категории товаров", title_one="Категория", model=Category,
    order_by=[Category.sort_order],
    fields=[
        Field("name", "Название"),
        Field("sort_order", "Порядок сортировки", ftype="int"),
    ],
))

_reg(Entity(
    key="cur", title="💱 Валюты", title_one="Валюта", model=Currency,
    order_by=[Currency.id],
    fields=[
        Field("code", "Код (например USD)"),
        Field("name", "Название"),
        Field("symbol", "Символ", required=False),
        Field("is_base", "Базовая валюта?", ftype="bool"),
    ],
))

_reg(Entity(
    key="rate", title="📈 Курсы валют", title_one="Курс валюты", model=ExchangeRate,
    order_by=[ExchangeRate.currency_id],
    fields=[
        Field("currency_id", "Валюта", ftype="fk", fk="cur"),
        Field("rate", "Курс к TJS (1 валюта = X TJS)", ftype="dec"),
    ],
))

_reg(Entity(
    key="cof", title="🧮 Коэффициенты", title_one="Коэффициент", model=Coefficient,
    order_by=[Coefficient.code, Coefficient.id],
    fields=[
        Field("name", "Название"),
        Field("code", "Тип", ftype="choice", choices=[
            ("volumetric", "Объёмный вес (кг/м³)"),
            ("density", "Плотный груз (множитель цены)"),
            ("custom", "Другой"),
        ]),
        Field("delivery_type_id", "Тип доставки", ftype="fk", fk="dtp", required=False,
              hint="Пропустить = для всех типов"),
        Field("category_id", "Категория", ftype="fk", fk="cat", required=False,
              hint="Пропустить = для всех категорий"),
        Field("value", "Значение", ftype="dec"),
    ],
))

_reg(Entity(
    key="svc", title="➕ Доп. услуги / скидки / наценки", title_one="Услуга/скидка",
    model=ExtraService, order_by=[ExtraService.kind, ExtraService.id],
    fields=[
        Field("name", "Название"),
        Field("kind", "Вид", ftype="choice", choices=[
            ("fee", "Сбор (упаковка, страховка...)"),
            ("discount", "Скидка"),
            ("markup", "Наценка"),
        ]),
        Field("calc_type", "Способ расчёта", ftype="choice", choices=[
            ("fixed", "Фиксированная сумма"),
            ("percent", "% от стоимости"),
            ("per_kg", "Сумма за каждый кг"),
        ]),
        Field("value", "Значение", ftype="dec"),
        Field("delivery_type_id", "Тип доставки", ftype="fk", fk="dtp", required=False,
              hint="Пропустить = для всех типов"),
        Field("category_id", "Категория", ftype="fk", fk="cat", required=False,
              hint="Пропустить = для всех категорий"),
    ],
))

_reg(Entity(
    key="faq", title="❓ FAQ", title_one="Вопрос", model=Faq,
    order_by=[Faq.sort_order],
    fields=[
        Field("question", "Вопрос"),
        Field("answer", "Ответ", ftype="text"),
        Field("sort_order", "Порядок сортировки", ftype="int"),
    ],
))

_reg(Entity(
    key="whs", title="📍 Склады", title_one="Склад", model=Warehouse,
    order_by=[Warehouse.sort_order],
    fields=[
        Field("name", "Название"),
        Field("address", "Адрес", ftype="text"),
        Field("note", "Примечание", ftype="text", required=False),
        Field("sort_order", "Порядок сортировки", ftype="int"),
    ],
))

_reg(Entity(
    key="cnt", title="☎ Контакты", title_one="Контакт", model=Contact,
    order_by=[Contact.sort_order],
    fields=[
        Field("title", "Название (Телефон, Telegram...)"),
        Field("value", "Значение", ftype="text"),
        Field("sort_order", "Порядок сортировки", ftype="int"),
    ],
))

_reg(Entity(
    key="adm", title="👮 Администраторы", title_one="Администратор", model=Admin,
    order_by=[Admin.id],
    fields=[
        Field("tg_id", "Telegram ID", ftype="int"),
        Field("name", "Имя", required=False),
    ],
))

_reg(Entity(
    key="set", title="⚙️ Настройки", title_one="Настройка", model=Setting,
    order_by=[Setting.key],
    fields=[
        Field("key", "Ключ"),
        Field("value", "Значение", ftype="text"),
        Field("description", "Описание", ftype="text", required=False),
    ],
))

"""Начальное наполнение БД демо-данными.

Все значения — примеры, редактируются администратором из админ-панели.
Сид выполняется только если таблицы пустые.
"""
import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import (
    Category, Coefficient, Contact, Currency, DeliveryType, ExchangeRate,
    ExtraService, Faq, Setting, Tariff, Warehouse,
)

DEFAULT_SETTINGS = {
    "rounding_mode": ("up", "Округление итога: none | up | down | nearest"),
    "rounding_step": ("1", "Шаг округления, напр. 1, 0.5, 10"),
    "order_statuses": (
        json.dumps(["Новая", "В обработке", "Подтверждена", "Выкуплена", "Отменена", "Завершена"],
                   ensure_ascii=False),
        "Статусы заявок (JSON-список)",
    ),
    "track_statuses": (
        json.dumps(["Получен на складе", "Проверяется", "Упакован", "Отправлен", "В пути",
                    "Прибыл", "Проходит таможню", "Готов к выдаче", "Выдан"], ensure_ascii=False),
        "Статусы грузов (JSON-список)",
    ),
    "welcome_text": (
        "👋 Добро пожаловать в бот карго-доставки Китай → Таджикистан!\n"
        "Выберите действие в меню ниже.",
        "Приветственное сообщение /start",
    ),
}


async def seed(session: AsyncSession) -> None:
    count = await session.scalar(select(func.count(DeliveryType.id)))
    if count:
        # каталоги уже есть — досеиваем только недостающие настройки
        for key, (value, descr) in DEFAULT_SETTINGS.items():
            if not await session.scalar(select(Setting).where(Setting.key == key)):
                session.add(Setting(key=key, value=value, description=descr))
        await session.commit()
        return

    dt_avia = DeliveryType(name="Авиа", emoji="✈️", sort_order=1)
    dt_auto = DeliveryType(name="Авто", emoji="🚛", sort_order=2)
    dt_sea = DeliveryType(name="Море", emoji="🚢", sort_order=3)
    dt_rail = DeliveryType(name="Железная дорога", emoji="🚂", sort_order=4)
    session.add_all([dt_avia, dt_auto, dt_sea, dt_rail])

    cat_names = ["Одежда", "Обувь", "Электроника", "Телефоны", "Бытовая техника",
                 "Косметика", "Плотный груз", "Объёмный груз", "Другое"]
    cats = [Category(name=n, sort_order=i) for i, n in enumerate(cat_names, 1)]
    session.add_all(cats)

    tjs = Currency(code="TJS", name="Сомони", symbol="смн", is_base=True)
    usd = Currency(code="USD", name="Доллар США", symbol="$")
    cny = Currency(code="CNY", name="Юань", symbol="¥")
    session.add_all([tjs, usd, cny])
    await session.flush()

    session.add_all([
        ExchangeRate(currency_id=tjs.id, rate=1),
        ExchangeRate(currency_id=usd.id, rate=10.9),
        ExchangeRate(currency_id=cny.id, rate=1.5),
    ])

    # Коэффициенты объёмного веса (кг за 1 м³)
    session.add_all([
        Coefficient(name="Объёмный вес: Авиа", code="volumetric",
                    delivery_type_id=dt_avia.id, value=167),
        Coefficient(name="Объёмный вес: Авто", code="volumetric",
                    delivery_type_id=dt_auto.id, value=200),
        Coefficient(name="Объёмный вес: Море", code="volumetric",
                    delivery_type_id=dt_sea.id, value=100),
        Coefficient(name="Объёмный вес: ЖД", code="volumetric",
                    delivery_type_id=dt_rail.id, value=150),
        Coefficient(name="Множитель: плотный груз", code="density",
                    category_id=cats[6].id, value=1.2),
    ])

    cat_by_name = {c.name: c for c in cats}
    demo_tariffs = [
        ("Авиа / Одежда", dt_avia, "Одежда", 5.5, 10, 1, "USD", "7–12 дней"),
        ("Авиа / Обувь", dt_avia, "Обувь", 6.0, 10, 1, "USD", "7–12 дней"),
        ("Авиа / Электроника", dt_avia, "Электроника", 8.0, 15, 1, "USD", "7–12 дней"),
        ("Авиа / Общий", dt_avia, None, 6.5, 10, 1, "USD", "7–12 дней"),
        ("Авто / Одежда", dt_auto, "Одежда", 3.2, 5, 1, "USD", "18–25 дней"),
        ("Авто / Общий", dt_auto, None, 3.8, 5, 1, "USD", "18–25 дней"),
        ("Море / Общий", dt_sea, None, 2.0, 5, 5, "USD", "35–50 дней"),
        ("ЖД / Общий", dt_rail, None, 2.8, 5, 3, "USD", "25–35 дней"),
    ]
    for name, dt, cat_name, price, min_cost, min_w, cur, time_ in demo_tariffs:
        session.add(Tariff(
            name=name, delivery_type_id=dt.id,
            category_id=cat_by_name[cat_name].id if cat_name else None,
            price_per_kg=price, min_order_cost=min_cost, min_weight=min_w,
            currency_code=cur, delivery_time=time_,
        ))

    session.add_all([
        ExtraService(name="Упаковка", kind="fee", calc_type="fixed", value=2),
        ExtraService(name="Страховка", kind="fee", calc_type="percent", value=1, is_active=False),
        ExtraService(name="Оформление", kind="fee", calc_type="fixed", value=1, is_active=False),
    ])

    session.add_all([
        Faq(question="Сколько идёт доставка?",
            answer="Авиа — 7–12 дней, Авто — 18–25 дней, ЖД — 25–35 дней, Море — 35–50 дней.",
            sort_order=1),
        Faq(question="Как оплатить?",
            answer="Оплата при получении груза на складе в Душанбе: наличными или переводом.",
            sort_order=2),
    ])

    session.add(Warehouse(
        name="Склад в Гуанчжоу",
        address="Guangzhou, Baiyun District, ... (укажите адрес в админ-панели)",
        note="Указывайте ваш код клиента на каждой коробке.",
        sort_order=1,
    ))

    session.add_all([
        Contact(title="Телефон", value="+992 00 000 0000", sort_order=1),
        Contact(title="Telegram менеджера", value="@manager", sort_order=2),
        Contact(title="Адрес офиса", value="г. Душанбе, ул. ... ", sort_order=3),
    ])

    for key, (value, descr) in DEFAULT_SETTINGS.items():
        session.add(Setting(key=key, value=value, description=descr))

    await session.commit()

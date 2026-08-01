from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [b(text="📊 Статистика", callback_data="adm:stats"),
         b(text="📦 Заявки", callback_data="adm:orders:1")],
        [b(text="💰 Тарифы", callback_data="e:trf:list:1"),
         b(text="🧮 Коэффициенты", callback_data="e:cof:list:1")],
        [b(text="🚚 Типы доставки", callback_data="e:dtp:list:1"),
         b(text="🗂 Категории", callback_data="e:cat:list:1")],
        [b(text="💱 Валюты", callback_data="e:cur:list:1"),
         b(text="📈 Курсы валют", callback_data="e:rate:list:1")],
        [b(text="➕ Доп. услуги / скидки", callback_data="e:svc:list:1"),
         b(text="⚙️ Настройки", callback_data="e:set:list:1")],
        [b(text="❓ FAQ", callback_data="e:faq:list:1"),
         b(text="📍 Склады", callback_data="e:whs:list:1")],
        [b(text="☎ Контакты", callback_data="e:cnt:list:1"),
         b(text="👮 Администраторы", callback_data="e:adm:list:1")],
        [b(text="👥 Пользователи", callback_data="adm:users:1"),
         b(text="🔎 Треки", callback_data="adm:tracks:1")],
        [b(text="📣 Рассылка", callback_data="adm:broadcast"),
         b(text="📤 Экспорт", callback_data="adm:export")],
        [b(text="🧾 История расчётов", callback_data="adm:calcs:1"),
         b(text="📜 Журнал изменений", callback_data="adm:logs:1")],
    ])


def back_to_admin() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")],
    ])


def paginate_kb(prefix: str, page: int, pages: int,
                extra_rows: list[list[InlineKeyboardButton]] | None = None) -> InlineKeyboardMarkup:
    """Клавиатура пагинации: prefix должен принимать номер страницы в конце."""
    rows = list(extra_rows or [])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}:{page - 1}"))
    if pages > 1:
        nav.append(InlineKeyboardButton(text=f"{page}/{pages}", callback_data="noop"))
    if page < pages:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"{prefix}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀️ Админ-меню", callback_data="adm:menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

"""Все тексты бота в одном месте."""

START = (
    "🛍 <b>{shop}</b>\n{tagline}\n\n"
    "Открывайте каталог кнопкой ниже — вход уже под вашим аккаунтом, "
    "регистрироваться не нужно."
)
OPEN_SHOP = "🛍 Открыть магазин"

MENU_SHOP = "🛍 Каталог"
MENU_ORDERS = "📦 Мои заказы"
MENU_HELP = "ℹ️ Помощь"
MENU_ADMIN = "🛠 Товары"
MENU_PANEL = "📊 Панель"

HELP = (
    "<b>Как заказать</b>\n\n"
    "1. Откройте каталог и выберите товар\n"
    "2. Укажите размер и положите в корзину\n"
    "3. Оформите заказ: имя, телефон, город, адрес\n"
    "4. Мы свяжемся и пришлём реквизиты для оплаты\n\n"
    "Вопросы — просто напишите в этот чат."
)

NOT_ADMIN = (
    "Этот раздел только для владельца магазина.\n\n"
    "Ваш Telegram-id: <code>{tg_id}</code>"
)

WHOAMI = ("<b>Ваш профиль</b>\n\n"
          "Telegram-id: <code>{tg_id}</code>\n"
          "Имя: {name}\n"
          "Username: {username}\n"
          "Права: {role}")

ORDER_NEW_ADMIN = (
    "🆕 <b>Заказ №{number}</b>\n\n"
    "{items}\n"
    "Товары: {goods} {sign}\n"
    "Доставка: {delivery_label} — {delivery} {sign}\n"
    "<b>Итого: {total} {sign}</b>\n\n"
    "👤 {name}\n📞 {phone}\n📍 {place}{comment}"
)

ORDER_CREATED_BUYER = (
    "✅ <b>Заказ №{number} принят</b>\n\n"
    "{items}\n<b>Итого: {total} {sign}</b>\n\n"
    "Мы свяжемся с вами для подтверждения."
)

PAYMENT_INFO = (
    "\n\n💳 <b>Оплата</b>\nKaspi: <code>{phone}</code>\nПолучатель: {name}\n"
    "В комментарии укажите номер заказа {number}."
)

ORDER_STATUS_BUYER = {
    "confirmed": "✅ Заказ №{number} подтверждён. Ждём оплату.",
    "paid": "💰 Оплата по заказу №{number} получена. Готовим к отправке.",
    "shipped": "📦 Заказ №{number} отправлен.{tracking}",
    "done": "🎉 Заказ №{number} получен. Спасибо за покупку!",
    "canceled": "❌ Заказ №{number} отменён.",
}

PANEL = (
    "📊 <b>{shop}</b>\n\n"
    "<b>Товары</b>\n"
    "   в продаже — {active}\n"
    "   закончились — {out}\n"
    "   черновики — {draft}\n"
    "   скрыты — {hidden}\n"
    "   всего единиц на складе — {units}\n\n"
    "<b>Заказы</b>\n"
    "   новые — {new}\n"
    "   в работе — {in_work}\n"
    "   выполнено — {done}\n"
    "   отменено — {canceled}\n"
    "   за сутки — {today}, за неделю — {week}\n\n"
    "<b>Деньги</b>\n"
    "   за неделю — {revenue_week} {sign}\n"
    "   всего — {revenue_total} {sign}\n"
    "   средний чек — {average} {sign}\n\n"
    "{low}"
)
LOW_STOCK_HEAD = "<b>Заканчивается</b>\n"
LOW_STOCK_EMPTY = "<i>Товары на исходе не найдены.</i>"

ORDERS_EMPTY = "У вас пока нет заказов. Откройте каталог — там много хорошего."
